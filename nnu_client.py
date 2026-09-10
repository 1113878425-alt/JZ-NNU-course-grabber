# -*- coding: utf-8 -*-
"""
南京师范大学选课系统 HTTP 客户端
封装登录、课程查询、选课/退课、余量查询等接口。
"""

import time
import json
import requests

import des

BASE_URL = "https://xsxk.nnu.edu.cn:443/xsxkapp"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


class NnuError(Exception):
    """选课系统业务异常。"""


class NnuClient:
    def __init__(self, timeout=10):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        })
        self.timeout = timeout
        self.token = None          # 登录凭证
        self.student = None        # 学生信息 dict（含 code/name/campus/electiveBatch 等）
        self.number = None         # 学号
        self.campus_code = None    # 校区代码

    # ---------------- 通用 ----------------
    def _get(self, url, params=None, auth=True):
        headers = {}
        if auth and self.token:
            headers["token"] = self.token
        r = self.session.get(url, params=params, headers=headers,
                             timeout=self.timeout, verify=False)
        return self._parse(r)

    def _post(self, url, data=None, auth=True):
        headers = {}
        if auth and self.token:
            headers["token"] = self.token
        r = self.session.post(url, data=data, headers=headers,
                              timeout=self.timeout, verify=False)
        return self._parse(r)

    @staticmethod
    def _parse(resp):
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            raise NnuError("接口返回非 JSON 数据（可能是网络异常或已掉线）")

    def _check(self, resp):
        """检查业务返回码，成功返回 True。"""
        if resp is None:
            return False
        code = str(resp.get("code"))
        if code == "1":
            return True
        if code == "302":
            raise NnuError("登录已失效（token 过期），请重新登录")
        return False

    # ---------------- 登录 ----------------
    def get_vcode(self):
        """获取验证码 token 与类型，返回 (vtoken, vode)。"""
        url = BASE_URL + "/sys/xsxkapp/student/4/vcode.do"
        resp = self._get(url, params={"timestamp": int(time.time() * 1000)}, auth=False)
        if not self._check(resp):
            raise NnuError("获取验证码失败: %s" % resp.get("msg", "未知错误"))
        data = resp.get("data") or {}
        return data.get("token"), str(data.get("vode", "1"))

    def get_vcode_image(self, vtoken):
        """下载验证码图片，返回 bytes。"""
        url = BASE_URL + "/sys/xsxkapp/student/vcode/image.do"
        r = self.session.get(url, params={"vtoken": vtoken},
                             timeout=self.timeout, verify=False)
        r.raise_for_status()
        return r.content

    def login(self, username, password, verify_code, vtoken):
        """登录。返回 (学号, token)。"""
        url = BASE_URL + "/sys/xsxkapp/student/check/login.do"
        params = {
            "timestrap": int(time.time() * 1000),
            "loginName": username,
            "loginPwd": des.encrypt_password(password),
            "verifyCode": verify_code,
            "vtoken": vtoken,
        }
        resp = self._get(url, params=params, auth=False)
        code = str(resp.get("code"))
        if code == "1":
            data = resp.get("data") or {}
            self.number = data.get("number")
            self.token = data.get("token")
            return self.number, self.token
        # 常见错误码
        err_map = {
            "2": "登录名或密码不正确",
            "3": "验证码不正确",
            "4": "在线人数超过上限，请稍后再试",
            "6": "账户处于不可使用状态，请先激活",
        }
        raise NnuError(err_map.get(code, resp.get("msg") or "登录失败（code=%s）" % code))

    def load_student_info(self):
        """登录后拉取学生信息（含学号/校区/可选批次）。"""
        if not self.number or not self.token:
            raise NnuError("尚未登录")
        url = BASE_URL + "/sys/xsxkapp/student/%s.do" % self.number
        resp = self._get(url, params={"timestamp": int(time.time() * 1000)})
        if not self._check(resp):
            raise NnuError("获取学籍信息失败: %s" % resp.get("msg", ""))
        self.student = resp.get("data") or {}
        # 校区代码：优先取 campus.code
        campus = self.student.get("campus") or {}
        self.campus_code = campus.get("code", "")
        return self.student

    def get_elective_batches(self):
        """返回可选批次列表（electiveBatchList）。"""
        if not self.student:
            self.load_student_info()
        return self.student.get("electiveBatchList") or []

    # ---------------- 课程查询 ----------------
    def _build_query(self, batch_code, teaching_class_type, content="",
                     page_number=0, page_size=20, campus=None):
        data = {
            "studentCode": self.number,
            "campus": campus or self.campus_code,
            "electiveBatchCode": batch_code,
            "isMajor": "1",
            "teachingClassType": teaching_class_type,
            "checkConflict": "",
            "checkCapacity": "",
            "queryContent": content,
        }
        query_str = json.dumps({
            "data": data,
            "pageSize": str(page_size),
            "pageNumber": str(page_number),
            "order": "",
        }, ensure_ascii=False)
        return {"querySetting": query_str}

    def query_courses(self, batch_code, teaching_class_type="XGXK",
                      content="", page_number=0, page_size=20, campus=None):
        """查询课程列表，返回 (dataList, totalCount)。"""
        url = BASE_URL + "/sys/xsxkapp/elective/publicCourse.do"
        if teaching_class_type in ("FANKC", "FAWKC", "CXKC"):
            url = BASE_URL + "/sys/xsxkapp/elective/programCourse.do"
        data = self._build_query(batch_code, teaching_class_type, content,
                                 page_number, page_size, campus)
        resp = self._post(url, data=data)
        if not self._check(resp):
            raise NnuError("查询课程失败: %s" % resp.get("msg", ""))
        return resp.get("dataList") or [], resp.get("totalCount", 0)

    def query_all_courses(self, batch_code, teaching_class_type="XGXK",
                          page_size=100, max_pages=20):
        """分页拉取某批次全部课程，返回完整列表（用于检索兜底）。"""
        all_data = []
        for page in range(max_pages):
            data_list, total = self.query_courses(
                batch_code, teaching_class_type, content="",
                page_number=page, page_size=page_size)
            if not data_list:
                break
            all_data.extend(data_list)
            # 已拿满，或最后一页数据不足一页，说明已拉完
            if total and len(all_data) >= int(total):
                break
            if len(data_list) < page_size:
                break
        return all_data

    def query_capacity(self, tc_id, capacity_suffix=None):
        """查询教学班实时余量。"""
        url = BASE_URL + "/sys/xsxkapp/elective/teachingclass/capacity.do"
        params = {"tcId": tc_id, "xh": self.number}
        if capacity_suffix:
            params["capacitySuffix"] = capacity_suffix
        resp = self._get(url, params=params)
        if not self._check(resp):
            raise NnuError("查询余量失败: %s" % resp.get("msg", ""))
        return resp.get("data") or {}

    # ---------------- 选课 / 退课 ----------------
    def _build_add_param(self, batch_code, tc_id, campus=None,
                         teaching_class_type="XGXK", need_book="0",
                         test_tcid=None):
        inner = {
            "operationType": "1",
            "studentCode": self.number,
            "electiveBatchCode": batch_code,
            "teachingClassId": tc_id,
            "isMajor": "1",
            "campus": campus or self.campus_code,
            "teachingClassType": teaching_class_type,
        }
        if need_book != "":
            inner["needBook"] = need_book
        if test_tcid:
            inner["testTeachingClassID"] = test_tcid
        add_str = json.dumps({"data": inner}, ensure_ascii=False)
        return {"addParam": add_str}

    def add_course(self, batch_code, tc_id, campus=None,
                   teaching_class_type="XGXK", need_book="0", test_tcid=None):
        """提交选课（operationType=1）。返回响应 dict。"""
        url = BASE_URL + "/sys/xsxkapp/elective/volunteer.do"
        data = self._build_add_param(batch_code, tc_id, campus,
                                     teaching_class_type, need_book, test_tcid)
        resp = self._post(url, data=data)
        return resp

    def _build_del_param(self, batch_code, tc_id):
        inner = {
            "operationType": "2",
            "studentCode": self.number,
            "electiveBatchCode": batch_code,
            "teachingClassId": tc_id,
            "isMajor": "1",
        }
        del_str = json.dumps({"data": inner}, ensure_ascii=False)
        return {"deleteParam": del_str}

    def delete_course(self, batch_code, tc_id):
        """退课（operationType=2）。"""
        url = BASE_URL + "/sys/xsxkapp/elective/volunteer.do"
        data = self._build_del_param(batch_code, tc_id)
        resp = self._post(url, data=data)
        return resp

    def query_status(self):
        """查询选课操作处理结果。"""
        url = BASE_URL + "/sys/xsxkapp/elective/studentstatus.do"
        resp = self._post(url, data={"studentCode": self.number})
        return resp

    def query_chosen(self, batch_code):
        """查询当前批次已选课程。"""
        url = BASE_URL + "/sys/xsxkapp/elective/volunteered.do"
        resp = self._get(url, params={
            "timestamp": int(time.time() * 1000),
            "studentCode": self.number,
            "electiveBatchCode": batch_code,
        })
        return resp

    def check_can_choose(self, tc_id, batch_code):
        """判断某教学班是否可选中。"""
        url = BASE_URL + "/sys/xsxkapp/util/canchoose.do"
        resp = self._get(url, params={
            "xh": self.number,
            "jxbid": tc_id,
            "xklcdm": batch_code,
            "timestamp": int(time.time() * 1000),
        })
        return resp
