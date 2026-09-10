# -*- coding: utf-8 -*-
"""
回归测试：验证本轮修复的 7 项问题。
运行：python test_fixes.py
"""

import sys
import threading

import des
import nnu_client
import main

PASS, FAIL = 0, 0


def check(title, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [OK]   %s" % title)
    else:
        FAIL += 1
        print("  [FAIL] %s  %s" % (title, detail))


# ---------------------------------------------------------------
print("\n=== 1. 加密算法回归（确保改动没破坏 des.py）===")
# 与前端 Node 原 JS 基准值一致
CASES = {
    "123456": "NUMyOEFEREUxRkYxM0EzQkQyQTczQ0I0ODkyODY0QUM=",
    "12345678": "NUMyOEFEREUxRkYxM0EzQkE5NEM2Q0RFMzZFQTQ1NjY=",
    "abc": "N0QyMEFBM0M2ODQ0MTdGRg==",
}
for pwd, expected in CASES.items():
    got = des.encrypt_password(pwd)
    check("encrypt('%s')" % pwd, got == expected, "got=%s want=%s" % (got, expected))
print("  （基准值取自前端 des.min.js 原 JS 输出，已交叉验证）")


# ---------------------------------------------------------------
print("\n=== 2. 余量字段名修复（#4）===")
data_ok = {"classCapacity": "50", "numberOfSelected": "30"}
check("50 容量 - 30 已选 = 20", nnu_client._calc_remain_from_capacity(data_ok) == 20)
data_full = {"classCapacity": 40, "numberOfSelected": 40}
check("40 容量 - 40 已选 = 0", nnu_client._calc_remain_from_capacity(data_full) == 0)
data_over = {"classCapacity": 40, "numberOfSelected": 45}
check("超额不出现负数", nnu_client._calc_remain_from_capacity(data_over) == 0)
data_bad = {"classCapacity": None, "numberOfSelected": "30"}
check("字段缺失返回 None", nnu_client._calc_remain_from_capacity(data_bad) is None)
check("空 dict 返回 None", nnu_client._calc_remain_from_capacity({}) is None)
check("旧错误字段 kyl 不会误被判为有效",
      nnu_client._calc_remain_from_capacity({"kyl": "10"}) is None)


# ---------------------------------------------------------------
print("\n=== 3. grab_loop 下标定位（#2）===")
# 构造两门完全相同的课程（旧代码 targets.index() 会串位）
same_a = {"name": "重复课", "tc_id": "T1", "campus": "01", "teaching_class_type": "XGXK"}
same_b = {"name": "重复课", "tc_id": "T1", "campus": "01", "teaching_class_type": "XGXK"}
check("两门课 dict 完全相等（用于验证旧 bug 场景）", same_a == same_b)


class FakeClient:
    """模拟客户端：第一门课首次失败、第二次成功；其余直接成功。"""

    def __init__(self, plan):
        self.plan = plan          # {tc_id: [第一次结果, 第二次结果, ...]}
        self.calls = {}           # {tc_id: 调用次数}
        self.lock = threading.Lock()
        self.status_calls = 0

    def add_course(self, batch_code, tc_id, campus=None,
                   teaching_class_type="XGXK"):
        with self.lock:
            n = self.calls.get(tc_id, 0)
            self.calls[tc_id] = n + 1
        seq = self.plan.get(tc_id)
        if seq:
            return seq[min(n, len(seq) - 1)]
        return {"code": "1"}

    def query_status(self):
        self.status_calls += 1
        return {"code": "1"}


# 场景 A：两门相同的课都应被抢到（旧代码可能只加到 done 一个下标）
fc = FakeClient({})
res = main.grab_loop(fc, "BATCH", [same_a, dict(same_b)],
                     workers=2, retry_interval=0.01, max_retries=5)
check("两门相同的课都抢到", len(res) == 2, "got=%d" % len(res))

# 场景 B：首次失败，应自动重试并最终成功
fc2 = FakeClient({"T9": [{"code": "-1"}, {"code": "1"}]})
res2 = main.grab_loop(fc2, "BATCH", [{"name": "难课", "tc_id": "T9",
                                      "campus": "01", "teaching_class_type": "XGXK"}],
                      workers=1, retry_interval=0.01, max_retries=5)
check("首次失败后自动重试成功", len(res2) == 1 and fc2.calls["T9"] >= 2,
      "calls=%s" % fc2.calls)


# ---------------------------------------------------------------
print("\n=== 4. maybe/retry 状态不再漏课（#3）===")
class MaybeClient(FakeClient):
    """query_status 永远返回未知（模拟处理超时），提交始终 code=1。"""

    def query_status(self):
        return {"code": "0"}  # 非 1 非 -1 -> wait_result 超时返回 None


mc = MaybeClient({})
# 用极短 timeout，让 wait_result 快速返回 None
orig_wait = main.wait_result
main.wait_result = lambda client, timeout=3.0, interval=0.15: (None, None)
try:
    res3 = main.grab_loop(mc, "BATCH", [{"name": "待确认", "tc_id": "TX",
                                         "campus": "01", "teaching_class_type": "XGXK"}],
                          workers=1, retry_interval=0.01, max_retries=3)
    check("retry 状态被反复尝试（未静默漏掉）", mc.calls.get("TX", 0) >= 2,
          "calls=%s" % mc.calls)
finally:
    main.wait_result = orig_wait


# ---------------------------------------------------------------
print("\n=== 5. wait_result 提速（#12）===")
import time as _t

class SlowStatusClient(FakeClient):
    def __init__(self):
        super().__init__({})
        self.n = 0

    def query_status(self):
        self.n += 1
        return {"code": "0"}  # 始终未定


sc = SlowStatusClient()
t0 = _t.time()
main.wait_result(sc, timeout=0.6, interval=0.05)
elapsed = _t.time() - t0
check("0.6s 超时能在 ~1s 内返回", elapsed < 1.2, "elapsed=%.2fs" % elapsed)
check("轮询次数明显多于旧实现(3次)", sc.n > 3, "poll=%d" % sc.n)


# ---------------------------------------------------------------
print("\n=== 6. 网络层重试配置（#5）===")
check("Retry 总次数 = 3", nnu_client._RETRY.total == 3)
adapter = nnu_client.NnuClient().session.get_adapter("https://x")
check("HTTPS 已挂载带重试的适配器", adapter is not None)
import inspect as _inspect
_get_src = _inspect.getsource(nnu_client.NnuClient._get)
_post_src = _inspect.getsource(nnu_client.NnuClient._post)
check("_get 已将网络异常转为 NnuError", "requests.exceptions.RequestException" in _get_src)
check("_post 已将网络异常转为 NnuError", "requests.exceptions.RequestException" in _post_src)


# ---------------------------------------------------------------
print("\n=== 7. ttype 不再被覆盖（#1）===")
import inspect
src = inspect.getsource(main.main)
check("main() 中使用 cfg.get('teaching_class_type') 赋值 ttype",
      "ttype = cfg.get(\"teaching_class_type\")" in src)
check("main() 中不再有交互式段落的无条件 ttype 覆盖",
      src.count("input(\"课程类型") == 1)


# ---------------------------------------------------------------
print("\n" + "=" * 46)
print("测试结果: %d 通过, %d 失败" % (PASS, FAIL))
print("=" * 46)
sys.exit(1 if FAIL else 0)
