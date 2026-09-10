# -*- coding: utf-8 -*-
"""
南京师范大学选课抢课脚本 —— 主程序
功能：人工验证码登录 -> 选批次 -> 配置目标课程 -> 定时/监控/立即抢课（多线程并发）。
"""

import os
import sys
import time
import json
import getpass
import datetime
import threading
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

from nnu_client import NnuClient, NnuError, BASE_URL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
VCODE_PATH = os.path.join(HERE, "vcode.png")


def log(msg):
    print("[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg))


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log("配置文件读取失败，忽略: %s" % e)
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def input_credentials(cfg):
    username = cfg.get("username") or input("请输入学号: ").strip()
    password = cfg.get("password") or getpass.getpass("请输入密码(输入不回显): ")
    return username, password


def do_login(client, username, password):
    """登录，循环处理验证码（人工输入）。"""
    while True:
        vtoken, vode = client.get_vcode()
        if vode != "1":
            log("当前为点选式验证码，脚本暂不支持自动处理。")
            log("请先用浏览器登录一次，或稍后再试（多数情况下为普通验证码）。")
            raise NnuError("点选式验证码，暂不支持")

        img = client.get_vcode_image(vtoken)
        with open(VCODE_PATH, "wb") as f:
            f.write(img)
        # 用系统默认图片查看器打开验证码
        try:
            os.startfile(VCODE_PATH)
        except Exception:
            log("验证码图片已保存到: %s （请手动打开查看）" % VCODE_PATH)

        code = input("请输入验证码(看不清直接回车刷新): ").strip()
        if not code:
            continue
        try:
            number, token = client.login(username, password, code, vtoken)
            log("登录成功！学号: %s" % number)
            return number, token
        except NnuError as e:
            log("登录失败: %s" % e)
            if "验证码" in str(e):
                continue
            # 密码错误等，让用户重输
            if input("是否重试登录？(y/n): ").strip().lower() != "y":
                raise


def choose_batch(client):
    batches = client.get_elective_batches()
    if not batches:
        raise NnuError("当前没有可选的选课轮次")
    print("\n可选选课轮次:")
    for i, b in enumerate(batches):
        print("  [%d] %s  类型:%s  可跨校区:%s  可冲突:%s" % (
            i + 1, b.get("name", b.get("code", "?")), b.get("batchType", "?"),
            b.get("sfkkxq", "?"), b.get("sfkct", "?")))
    if len(batches) == 1:
        return batches[0]
    idx = input("选择轮次编号(默认1): ").strip()
    try:
        i = int(idx) - 1 if idx else 0
        return batches[i]
    except Exception:
        return batches[0]


# ---------------- 课程检索与匹配 ----------------
# 课程字段名（驼峰，已从前端源码核实）
F_TEACHING_CLASS_ID = "teachingClassID"      # 教学班ID（抢课提交用）
F_COURSE_NUMBER = "courseNumber"             # 课程号
F_COURSE_NAME = "courseName"                 # 课程名称
F_TEACHER_NAME = "teacherName"               # 教师（格式 名字|教师号|主页，多人逗号分隔）
F_TEACHING_PLACE = "teachingPlace"           # 时间地点
F_CLASS_CAPACITY = "classCapacity"           # 容量
F_FIRST_VOLUNTEER = "numberOfFirstVolunteer"  # 已选(第一志愿)人数


def parse_teacher_names(teacher_name):
    """解析 teacherName 字段，返回干净的名字列表。"""
    if not teacher_name:
        return []
    names = []
    for seg in str(teacher_name).split(","):
        seg = seg.strip()
        if not seg:
            continue
        name = seg.split("|")[0].strip()
        if name:
            names.append(name)
    return names


def calc_remain(item):
    """计算余量 = 容量 - 已选人数；无法计算返回 '?'。"""
    cap = item.get(F_CLASS_CAPACITY)
    chosen = item.get(F_FIRST_VOLUNTEER)
    try:
        cap = int(cap) if cap not in (None, "") else 0
        chosen = int(chosen) if chosen not in (None, "") else 0
        return max(0, cap - chosen)
    except (TypeError, ValueError):
        return "?"


def match_course(item, name="", teacher="", number=""):
    """本地过滤：课程名/老师/课程号均做包含匹配。"""
    cn = str(item.get(F_COURSE_NAME) or "")
    tn = str(item.get(F_TEACHER_NAME) or "")
    num = str(item.get(F_COURSE_NUMBER) or "")
    if name and name not in cn:
        return False
    if number and number not in num:
        return False
    if teacher and teacher not in tn:
        return False
    return True


def search_courses(client, batch_code, ttype, name="", teacher="", number=""):
    """综合检索：先用关键词直接检索并本地过滤；空结果时拉全量兜底。"""
    keyword = number or name or teacher
    candidates = []
    if keyword:
        try:
            candidates, _ = client.query_courses(batch_code, ttype, content=keyword, page_size=50)
        except NnuError as e:
            log("关键词检索失败: %s，改用全量检索" % e)
            candidates = []
    if not candidates and keyword:
        log("关键词未命中，拉取全量课程本地匹配...")
        try:
            candidates = client.query_all_courses(batch_code, ttype)
        except NnuError as e:
            log("全量检索失败: %s" % e)
            candidates = []
    return [c for c in candidates if match_course(c, name, teacher, number)]


def show_course_list(courses):
    """展示匹配的教学班列表（含已满标注）。"""
    print("\n匹配到 %d 个教学班:" % len(courses))
    for i, c in enumerate(courses):
        name = c.get(F_COURSE_NAME) or "?"
        number = c.get(F_COURSE_NUMBER) or "?"
        teachers = "/".join(parse_teacher_names(c.get(F_TEACHER_NAME))) or "-"
        place = c.get(F_TEACHING_PLACE) or "-"
        cap = c.get(F_CLASS_CAPACITY)
        remain = calc_remain(c)
        tc_id = c.get(F_TEACHING_CLASS_ID) or "?"
        flag = "  【已满】" if isinstance(remain, int) and remain <= 0 else ""
        print("  [%d] %s | 课程号:%s | 教师:%s | %s | 余量:%s/%s | 教学班ID:%s%s" % (
            i + 1, name, number, teachers, place, remain,
            cap if cap not in (None, "") else "?", tc_id, flag))


def select_teaching_classes(courses):
    """让用户手动勾选要抢的教学班（可多选，逗号分隔）。返回选中的 item 列表。"""
    sel = input("  选择教学班编号(可多选，如 1,3；留空跳过该课程): ").strip()
    if not sel:
        return []
    picked, seen = [], set()
    for s in sel.replace("，", ",").split(","):
        s = s.strip()
        if not s:
            continue
        try:
            idx = int(s) - 1
        except ValueError:
            continue
        if 0 <= idx < len(courses) and idx not in seen:
            seen.add(idx)
            picked.append(courses[idx])
    return picked


def add_target_interactive(client, batch_code, ttype):
    """逐个添加目标课程：询问课程名/老师/课程号 → 检索 → 手动勾选 → 循环。"""
    targets = []
    print("\n开始添加要抢的课程（课程名/老师/课程号至少填一项）")
    while True:
        print("\n" + "-" * 46)
        name = input("  课程名(可留空): ").strip()
        teacher = input("  老师(可留空): ").strip()
        number = input("  课程号(可留空): ").strip()
        if not name and not teacher and not number:
            if targets:
                print("  未输入任何信息，结束添加。")
                break
            print("  至少输入课程名/老师/课程号中的一项。")
            continue

        cond = " ".join([x for x in [name, teacher, number] if x])
        log("正在检索「%s」..." % cond)
        results = search_courses(client, batch_code, ttype, name, teacher, number)
        if not results:
            print("  未找到匹配课程，请核对后重新输入。")
            continue

        show_course_list(results)
        picked = select_teaching_classes(results)
        if not picked:
            print("  已跳过该课程。")
        else:
            for c in picked:
                targets.append({
                    "name": c.get(F_COURSE_NAME) or cond,
                    "tc_id": c.get(F_TEACHING_CLASS_ID),
                    "campus": client.campus_code,
                    "teaching_class_type": ttype,
                })
            print("  已添加 %d 个教学班。" % len(picked))

        more = input("  继续添加下一门？(y/n，默认 n): ").strip().lower()
        if more != "y":
            break
    return targets


def wait_result(client, timeout=3.0):
    """提交后轮询处理结果。返回 (成功?, resp)。"""
    for _ in range(int(timeout * 2)):
        try:
            resp = client.query_status()
        except NnuError:
            return None, None
        code = str(resp.get("code"))
        if code == "1":
            return True, resp
        if code == "-1":
            return False, resp
        time.sleep(0.5)
    return None, None


def grab_loop(client, batch_code, targets, workers=5, retry_interval=0.3,
              max_retries=300, stop_event=None):
    """多线程并发抢课。返回成功列表。"""
    success = []
    done = set()  # 已抢到的课程下标

    def attempt(target):
        try:
            resp = client.add_course(
                batch_code, target["tc_id"],
                campus=target.get("campus"),
                teaching_class_type=target.get("teaching_class_type", "XGXK"))
            code = str(resp.get("code"))
            if code == "1":
                ok, r2 = wait_result(client)
                if ok:
                    return ("success", target, resp.get("msg") or "")
                elif ok is None:
                    return ("maybe", target, "已提交，处理中")
                else:
                    return ("fail", target, "处理失败，可能名额已满或冲突")
            return ("fail", target, resp.get("msg") or "提交失败(code=%s)" % code)
        except NnuError as e:
            return ("fail", target, str(e))

    retries = 0
    while not stop_event.is_set() and len(done) < len(targets) and retries < max_retries:
        pending = [t for i, t in enumerate(targets) if i not in done]
        with ThreadPoolExecutor(max_workers=min(workers, len(pending))) as pool:
            futures = [pool.submit(attempt, t) for t in pending]
            for f in as_completed(futures):
                status, target, msg = f.result()
                idx = targets.index(target)
                if status == "success":
                    log("✔ 抢课成功: %s (%s)" % (target["name"], target["tc_id"]))
                    success.append(target)
                    done.add(idx)
                elif status == "maybe":
                    log("? %s 已提交待确认" % target["name"])
                else:
                    pass  # 失败静默，继续重试
        retries += 1
        if len(done) < len(targets):
            time.sleep(retry_interval)
    return success


def monitor_mode(client, batch_code, targets, interval=2, max_workers=5):
    """余量监控捡漏：轮询余量，有余量立即抢。"""
    log("进入余量监控模式（Ctrl+C 退出）...")
    stop = threading.Event()
    try:
        while not stop.is_set():
            for t in targets:
                try:
                    cap = client.query_capacity(t["tc_id"])
                    remain = cap.get("remainingCapacity", cap.get("kyl", "?"))
                    log("监控 %s: 当前余量=%s" % (t["name"], remain))
                    try:
                        if int(remain) > 0:
                            log("发现余量，立即抢 %s ..." % t["name"])
                            grab_loop(client, batch_code, [t], workers=max_workers,
                                      retry_interval=0.2, max_retries=20, stop_event=stop)
                    except (TypeError, ValueError):
                        pass
                except NnuError as e:
                    log("余量查询失败: %s" % e)
            time.sleep(interval)
    except KeyboardInterrupt:
        log("已停止监控")
    return []


def timer_grab(client, batch_code, targets, start_time, workers, retry_interval, max_retries):
    """定时到点抢课。"""
    try:
        target_dt = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        log("开始时间格式错误，应为 YYYY-MM-DD HH:MM:SS")
        return []
    # 提前 0.3 秒预热，到点立即开抢
    wait = (target_dt - datetime.datetime.now()).total_seconds() - 0.3
    if wait > 0:
        log("定时抢课已就绪，目标时间 %s（等待 %.1f 秒）..." % (start_time, wait))
        time.sleep(max(0, wait))
    log("到点！开始抢课...")
    return grab_loop(client, batch_code, targets, workers, retry_interval, max_retries)


def main():
    print("=" * 56)
    print("  南京师范大学选课抢课脚本")
    print("  提示：请遵守学校选课规定，理性使用，注意账号安全")
    print("=" * 56)

    cfg = load_config()
    username, password = input_credentials(cfg)

    client = NnuClient()
    do_login(client, username, password)
    client.load_student_info()
    log("学籍信息加载完成，姓名: %s" % client.student.get("name", "?"))

    batch = choose_batch(client)
    batch_code = batch.get("code")
    log("当前轮次: %s (code=%s)" % (batch.get("name", ""), batch_code))

    # 目标课程确定
    ttype = cfg.get("teaching_class_type") or "XGXK"
    cfg_targets = cfg.get("targets") or []
    # config 已预填教学班ID则直接使用，否则交互式检索添加
    if cfg_targets and all(t.get("tc_id") for t in cfg_targets):
        log("使用 config.json 中预填的目标课程")
        targets = [{
            "name": t.get("name", ""),
            "tc_id": t.get("tc_id"),
            "campus": t.get("campus") or client.campus_code,
            "teaching_class_type": t.get("teaching_class_type", ttype),
        } for t in cfg_targets]
    else:
        ttype = input("课程类型(XGXK=校公选课/FANKC=方案内，默认XGXK): ").strip() or "XGXK"
        targets = add_target_interactive(client, batch_code, ttype)
    if not targets:
        log("没有有效的目标课程，退出")
        return
    print("\n目标课程:")
    for t in targets:
        print("  - %s  (教学班ID=%s)" % (t["name"], t["tc_id"]))

    if input("\n是否确认开始抢课？(y/n): ").strip().lower() != "y":
        log("已取消")
        return

    g = cfg.get("grab", {})
    mode = g.get("mode") or input("抢课模式(timer=定时/monitor=监控/now=立即，默认now): ").strip() or "now"
    workers = int(g.get("max_workers", 5))
    retry_interval = float(g.get("retry_interval", 0.3))
    max_retries = int(g.get("max_retries", 300))

    if mode == "timer":
        start_time = g.get("start_time") or input("抢课开始时间(YYYY-MM-DD HH:MM:SS): ").strip()
        success = timer_grab(client, batch_code, targets, start_time, workers, retry_interval, max_retries)
    elif mode == "monitor":
        success = monitor_mode(client, batch_code, targets, interval=int(g.get("monitor_interval", 2)), max_workers=workers)
    else:
        success = grab_loop(client, batch_code, targets, workers, retry_interval, max_retries)

    if success:
        print("\n🎉 抢课成功 %d 门：" % len(success))
        for t in success:
            print("   - %s" % t["name"])
    else:
        print("\n本轮未抢到课程（可能名额已满或已停止）")
    log("程序结束")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("已中断")
    except NnuError as e:
        log("错误: %s" % e)
    except Exception as e:
        log("异常: %s" % e)
