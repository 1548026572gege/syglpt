# -*- coding: utf-8 -*-
"""端到端冒烟回归（P3）：使用临时 SQLite + Flask test_client，不读写生产数据。

运行：
    python test/tests/e2e_smoke.py
退出码 0 表示全部通过，1 表示存在失败项。
"""
import io
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = tempfile.mkdtemp(prefix="bio_e2e_")

# 必须在导入 app/config 之前设置环境变量
os.environ.update({
    "DATABASE_URL": "sqlite:///" + os.path.join(TMP_DIR, "e2e.db"),
    "SECRET_KEY": "e2e-secret-key-0123456789abcdefghij",
    "JWT_SECRET": "e2e-jwt-key-0123456789abcdefghijkl",
    "ADMIN_INIT_PASSWORD": "Admin123456",
    "TEACHER_INIT_PASSWORD": "Teach123456",
})
sys.path.insert(0, TEST_DIR)

from openpyxl import Workbook, load_workbook  # noqa: E402

from app import app  # noqa: E402
from models import db  # noqa: E402

client = app.test_client()
PASSED = 0
FAILED = []
UPLOADED = []
CTX = {}
FMT = "%Y-%m-%d %H:%M"


def check(name, cond, detail=""):
    """记录一条断言结果"""
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}" + (f"（{detail}）" if detail else ""))


def H(token):
    return {"Authorization": "Bearer " + token} if token else {}


def login(username, password):
    r = client.post("/api/login", json={"username": username, "password": password})
    if r.status_code == 200 and r.get_json().get("code") == 0:
        return r.get_json()["data"]["token"]
    return None


def xlsx_headers(data):
    ws = load_workbook(io.BytesIO(data)).active
    return [c.value for c in ws[1]]


def upload(url, token, filename, content):
    return client.post(url, headers=H(token),
                       data={"file": (io.BytesIO(content), filename)},
                       content_type="multipart/form-data")


def future(days=3, hour=9):
    d = datetime.now() + timedelta(days=days)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


# ---------------- 各模块回归 ----------------

def test_pages():
    check("登录页可访问", client.get("/").status_code == 200)
    for name in ("dashboard", "instruments", "reservations", "borrows", "repairs", "losses",
                 "purchases", "reports", "notices", "catalog", "users", "stats", "logs", "plans"):
        check(f"页面 /page/{name}", client.get(f"/page/{name}").status_code == 200)
    check("非法页面返回 404", client.get("/page/not-exist").status_code == 404)


def test_auth():
    admin = login("admin", "Admin123456")
    check("管理员登录成功", admin is not None)
    CTX["admin"] = admin
    check("错误密码登录失败",
          client.post("/api/login", json={"username": "admin", "password": "bad"}).status_code == 400)
    check("未登录访问仪器接口 401", client.get("/api/instruments").status_code == 401)
    check("伪造 Token 401", client.get("/api/instruments", headers=H("fake.token.value")).status_code == 401)

    t1 = login("teacher", "Teach123456")
    check("教师登录成功", t1 is not None)
    CTX["t1"] = t1
    check("教师访问账号管理 403", client.get("/api/users", headers=H(t1)).status_code == 403)
    check("教师访问统计报表 403", client.get("/api/stats/report", headers=H(t1)).status_code == 403)

    # P1：改密后旧 Token 失效，新 Token 可用
    r = client.put("/api/password", headers=H(t1),
                   json={"old_password": "Teach123456", "new_password": "Teach654321"})
    check("修改密码成功", r.status_code == 200 and r.get_json()["data"].get("token"))
    new_t1 = r.get_json()["data"]["token"]
    check("旧 Token 改密后失效", client.get("/api/profile", headers=H(t1)).status_code == 401)
    check("新 Token 可继续使用", client.get("/api/profile", headers=H(new_t1)).status_code == 200)
    check("旧密码无法登录",
          client.post("/api/login", json={"username": "teacher", "password": "Teach123456"}).status_code == 400)
    CTX["t1"] = new_t1

    # 创建第二个教师与系统管理员
    r = client.post("/api/users", headers=H(admin),
                    json={"username": "e2e_t2", "name": "测试教师二", "password": "Test123456", "role": "teacher"})
    check("管理员新建教师", r.status_code == 200)
    t2 = login("e2e_t2", "Test123456")
    check("新教师可登录", t2 is not None)
    CTX["t2"] = t2
    r = client.post("/api/users", headers=H(admin),
                    json={"username": "e2e_sys", "name": "测试系统管理员", "password": "Sys123456", "role": "sysadmin"})
    check("管理员新建系统管理员", r.status_code == 200)
    sys_token = login("e2e_sys", "Sys123456")
    users = client.get("/api/users", headers=H(sys_token)).get_json()["data"]
    check("系统管理员看不到在线状态字段", all("online" not in u for u in users))

    # 在线状态 + 离线上报（P2）：登录本身不写活跃时间，需一次鉴权请求
    check("心跳接口可用", client.post("/api/heartbeat", headers=H(t2)).status_code == 200)
    users = client.get("/api/users", headers=H(admin)).get_json()["data"]
    t2_item = next((u for u in users if u["username"] == "e2e_t2"), None)
    check("内置 admin 可看到在线状态", t2_item is not None and "online" in t2_item)
    check("活跃教师显示在线", t2_item and t2_item["online"] is True)
    check("离线上报接口", client.post("/api/offline", headers=H(t2)).status_code == 200)
    users = client.get("/api/users", headers=H(admin)).get_json()["data"]
    t2_item = next((u for u in users if u["username"] == "e2e_t2"), None)
    check("离线上报后显示离线", t2_item and t2_item["online"] is False)
    check("心跳后恢复在线",
          client.post("/api/heartbeat", headers=H(t2)).status_code == 200 and
          next(u for u in client.get("/api/users", headers=H(admin)).get_json()["data"]
               if u["username"] == "e2e_t2")["online"] is True)

    # P1：有关联数据的账号禁止删除（报告在报告模块创建，最后统一删除）
    CTX["sys_token"] = sys_token


def test_users_and_classes():
    admin, t1 = CTX["admin"], CTX["t1"]
    check("重复用户名拦截", client.post("/api/users", headers=H(admin),
          json={"username": "admin", "name": "x", "password": "123456"}).status_code == 400)
    check("缺字段创建拦截", client.post("/api/users", headers=H(admin), json={"username": "x"}).status_code == 400)
    classes = client.get("/api/classes", headers=H(admin)).get_json()["data"]
    check("班级库非空", len(classes) > 0)
    users = client.get("/api/users", headers=H(admin)).get_json()["data"]
    teacher_id = next(u["id"] for u in users if u["username"] == "teacher")
    check("班级绑定非法值拦截", client.put(f"/api/users/{teacher_id}/classes", headers=H(admin),
          json={"classes": ["不存在的班级"]}).status_code == 400)
    check("班级绑定合法值", client.put(f"/api/users/{teacher_id}/classes", headers=H(admin),
          json={"classes": ["2501"]}).status_code == 200)


def test_instruments():
    admin, t1 = CTX["admin"], CTX["t1"]
    r = client.post("/api/instruments", headers=H(admin), json={
        "state_code": "E2E0001", "subject": "生物", "category_code": "SW-E2E-001",
        "name": "E2E测试显微镜", "spec": "1600倍", "unit": "台", "category": "光学仪器",
        "quantity": 20, "price": 100, "location": "生物实验室A-101", "status": "正常"})
    check("新增仪器", r.status_code == 200, r.get_json().get("msg"))
    ins = r.get_json()["data"]
    CTX["ins"] = ins
    check("重复内部编号拦截", client.post("/api/instruments", headers=H(admin),
          json={"category_code": "SW-E2E-001", "code": ins["code"], "name": "重复"}).status_code == 400)
    check("教师新增仪器 403", client.post("/api/instruments", headers=H(t1),
          json={"category_code": "SW-E2E-002", "name": "越权"}).status_code == 403)
    data = client.get("/api/instruments", headers=H(t1)).get_json()["data"]
    check("仪器列表返回总金额", "total_amount" in data and data["total_amount"] > 0)
    check("教师可查看仪器", len(data["list"]) >= 1)

    tpl = client.get("/api/instruments/template", headers=H(admin))
    check("仪器模板下载", tpl.status_code == 200 and "器材名称" in xlsx_headers(tpl.data))

    wb = Workbook()
    ws = wb.active
    ws.append(["国资编号", "学科", "分类代码", "器材名称", "规格", "单位", "数量", "单价",
               "存放位置", "状态", "金额", "备注"])
    ws.append(["E2E0002", "生物", "SW-E2E-003", "E2E导入试管架", "20孔", "个", 5, 30,
               "A-102", "正常", 150, ""])
    ws.append(["E2E0003", "生物", "", "E2E导入镊子", "不锈钢", "把", 10, 8, "A-103", "正常", 80, ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    r = client.post("/api/instruments/import", headers=H(admin),
                    data={"file": (io.BytesIO(buf.getvalue()), "ins.xlsx")},
                    content_type="multipart/form-data")
    check("仪器模板导入 2 条", r.status_code == 200 and r.get_json()["data"]["ok"] == 2)

    exp = client.get("/api/instruments/export", headers=H(admin))
    check("仪器台账导出", exp.status_code == 200 and "器材名称" in xlsx_headers(exp.data))

    data = client.get("/api/instruments?kw=E2E导入", headers=H(admin)).get_json()["data"]["list"]
    ids = [i["id"] for i in data]
    check("按关键字检索导入数据", len(ids) == 2)
    if ids:
        check("批量删除导入仪器",
              client.post("/api/instruments/batch-delete", headers=H(admin), json={"ids": ids}).status_code == 200)


def test_catalog():
    admin, t1 = CTX["admin"], CTX["t1"]
    tpl = client.get("/api/catalog/import-template", headers=H(admin))
    headers = xlsx_headers(tpl.data)
    check("配备目录模板含学科列", "学科" in headers)
    check("配备目录模板仅一个数量列", headers.count("数量") == 1)

    r = client.post("/api/catalog/import", headers=H(admin),
                    data={"file": (io.BytesIO(tpl.data), "catalog.xlsx")},
                    content_type="multipart/form-data")
    check("模板导入成功", r.status_code == 200 and r.get_json()["data"]["imported"] == 2)

    # P2：行级错误反馈
    wb = Workbook()
    ws = wb.active
    ws.title = "化学"
    ws.append(["学科", "分类代码", "器材名称", "规格", "单位", "数量", "单价", "必配或者选配", "金额", "备注"])
    ws.append(["化学", "C001", "E2E化学烧杯", "50ml", "个", 10, 5, "必配", "", ""])
    ws.append(["化学", "C002", "", "", "", 1, 1, "必配", "", ""])
    ws.append(["化学", "C003", "E2E化学试管", "", "", "abc", 3, "选配", "", ""])
    ws.append(["化学", "C004", "E2E化学滴管", "", "", 2, "x", "选配", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/catalog/import", headers=H(admin),
                    data={"file": (io.BytesIO(buf.getvalue()), "catalog2.xlsx")},
                    content_type="multipart/form-data")
    body = r.get_json()["data"]
    check("导入异常行仍按容错规则入库", r.status_code == 200 and body["imported"] == 3, str(body))
    check("行级错误：名称为空", any("名称为空" in e for e in body["errors"]))
    check("行级错误：数量非整数", any("不是整数" in e for e in body["errors"]))
    check("行级错误：单价非数字", any("不是数字" in e for e in body["errors"]))
    items = client.get("/api/catalog?subject=化学", headers=H(admin)).get_json()["data"]["list"]
    check("按学科筛选配备目录", len(items) >= 2)
    subjects = client.get("/api/catalog", headers=H(admin)).get_json()["data"]["subjects"]
    check("学科下拉包含生物与化学", "生物" in subjects and "化学" in subjects)
    if items:
        check("删除配备目录记录", client.delete(f"/api/catalog/{items[0]['id']}", headers=H(admin)).status_code == 200)
    check("教师导入配备目录 403",
          upload("/api/catalog/import", t1, "catalog.xlsx", tpl.data).status_code == 403)


def test_plans_notices():
    admin, t1 = CTX["admin"], CTX["t1"]
    r = client.post("/api/plans", headers=H(admin), json={
        "grade": "高一", "experiment_name": "E2E观察细胞", "category": "分组",
        "location": "生物实验室1", "planned_time": "2026-11-10"})
    check("新增实验计划", r.status_code == 200)
    check("非法类别拦截", client.post("/api/plans", headers=H(admin), json={
        "grade": "高一", "experiment_name": "x", "category": "其他",
        "location": "生物实验室1"}).status_code == 400)
    check("教师修改他人计划 403", client.put(f"/api/plans/{r.get_json()['data']['id']}", headers=H(t1),
          json={"experiment_name": "篡改"}).status_code == 403)

    wb = Workbook()
    ws = wb.active
    ws.append(["年级", "实验名称", "类别", "实验地点", "计划时间"])
    ws.append(["高一", "E2E计划导入A", "演示", "生物实验室2", "2026-11-12"])
    ws.append(["高一", "E2E计划导入B", "错误类别", "生物实验室2", "2026-11-12"])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/plans/import", headers=H(admin),
                    data={"file": (io.BytesIO(buf.getvalue()), "plans.xlsx")},
                    content_type="multipart/form-data")
    body = r.get_json()["data"]
    check("实验计划导入 1 成功 1 跳过", r.status_code == 200 and body["imported"] == 1 and body["skipped"] == 1)
    check("计划导入错误提示", any("类别" in e for e in body["errors"]))
    check("实验计划导出", client.get("/api/plans/export", headers=H(admin)).status_code == 200)

    r = client.post("/api/notices", headers=H(admin), json={
        "title": "E2E实验通知", "subject": "生物学", "classes": "高一(1)班",
        "teacher_name": "张老师", "lab_name": "生物实验室A", "experiment_time": "2026-11-12 10:00",
        "instruments": "显微镜", "content": "请提前准备"})
    check("创建通知单", r.status_code == 200)
    check("通知单标题必填", client.post("/api/notices", headers=H(admin), json={}).status_code == 400)
    check("教师编辑他人通知单 403", client.put(f"/api/notices/{r.get_json()['data']['id']}", headers=H(t1),
          json={"title": "篡改"}).status_code == 403)
    check("通知单导出", client.get("/api/notices/export", headers=H(admin)).status_code == 200)


def test_reservations():
    admin, t1, t2 = CTX["admin"], CTX["t1"], CTX["t2"]
    start = future(3, 9)
    end = start + timedelta(hours=2)
    body = {"lab_name": "E2E实验室", "experiment_name": "E2E预约实验", "class_name": "高一(1)班",
            "student_count": 40, "group_count": 10,
            "start_time": start.strftime(FMT), "end_time": end.strftime(FMT)}
    r = client.post("/api/reservations", headers=H(t1), json=body)
    check("教师提交预约", r.status_code == 200, r.get_json().get("msg"))
    rid = r.get_json()["data"]["id"]
    check("结束早于开始拦截", client.post("/api/reservations", headers=H(t1), json={
        **body, "start_time": end.strftime(FMT), "end_time": start.strftime(FMT)}).status_code == 400)
    check("同实验室时段冲突拦截", client.post("/api/reservations", headers=H(t1), json={
        **body, "experiment_name": "冲突实验"}).status_code == 400)

    r = client.put(f"/api/reservations/{rid}/review", headers=H(admin),
                   json={"action": "approve", "comment": "同意"})
    check("管理员审核通过", r.status_code == 200 and r.get_json()["data"]["status"] == "已通过")
    month = start.strftime("%Y-%m")
    events = client.get(f"/api/reservations/calendar?month={month}", headers=H(admin)).get_json()["data"]
    check("日历显示已通过预约", any(e["id"] == rid for e in events))
    check("教师只能看到自己的预约", rid not in [x["id"] for x in
          client.get("/api/reservations", headers=H(t2)).get_json()["data"]])
    check("标记完成", client.put(f"/api/reservations/{rid}/complete", headers=H(admin)).status_code == 200)
    check("已完成预约不可编辑", client.put(f"/api/reservations/{rid}", headers=H(admin),
          json={"remark": "x"}).status_code == 400)
    check("已完成预约不可取消", client.put(f"/api/reservations/{rid}/cancel", headers=H(admin)).status_code == 400)

    r = client.post("/api/reservations", headers=H(t1), json={
        **body, "experiment_name": "E2E待删除预约", "start_time": future(6, 9).strftime(FMT),
        "end_time": future(6, 11).strftime(FMT)})
    check("删除预约", client.delete(f"/api/reservations/{r.get_json()['data']['id']}",
          headers=H(t1)).status_code == 200)


def test_borrow_repair_loss():
    admin, t1 = CTX["admin"], CTX["t1"]
    ins = CTX["ins"]
    r = client.post("/api/borrows", headers=H(t1), json={
        "instrument_id": ins["id"], "quantity": 2, "purpose": "E2E借用",
        "expect_return_time": (datetime.now() + timedelta(days=5)).strftime(FMT)})
    check("教师申请借用", r.status_code == 200)
    bid = r.get_json()["data"]["id"]
    check("超库存借用拦截", client.post("/api/borrows", headers=H(t1), json={
        "instrument_id": ins["id"], "quantity": 999}).status_code == 400)
    check("仪器不存在 404", client.post("/api/borrows", headers=H(t1),
          json={"instrument_id": 999999, "quantity": 1}).status_code == 404)

    before = client.get("/api/instruments", headers=H(admin)).get_json()["data"]["list"]
    qty_before = next(i["quantity"] for i in before if i["id"] == ins["id"])
    check("确认借出", client.put(f"/api/borrows/{bid}/lend", headers=H(admin)).status_code == 200)
    after = client.get("/api/instruments", headers=H(admin)).get_json()["data"]["list"]
    qty_after = next(i["quantity"] for i in after if i["id"] == ins["id"])
    check("借出后库存扣减", qty_after == qty_before - 2, f"{qty_before}->{qty_after}")
    check("归还登记", client.put(f"/api/borrows/{bid}/return", headers=H(admin),
          json={"return_status": "完好"}).status_code == 200)
    after = client.get("/api/instruments", headers=H(admin)).get_json()["data"]["list"]
    check("归还后库存恢复", next(i["quantity"] for i in after if i["id"] == ins["id"]) == qty_before)
    check("重复归还拦截", client.put(f"/api/borrows/{bid}/return", headers=H(admin),
          json={"return_status": "完好"}).status_code == 400)

    r = client.post("/api/borrows", headers=H(t1),
                    json={"instrument_id": ins["id"], "quantity": 1, "purpose": "待驳回"})
    check("驳回借用申请", client.put(f"/api/borrows/{r.get_json()['data']['id']}/reject",
          headers=H(admin)).status_code == 200)

    r = client.post("/api/repairs", headers=H(t1), json={"instrument_id": ins["id"], "fault_desc": "E2E故障"})
    check("上报维修", r.status_code == 200)
    repid = r.get_json()["data"]["id"]
    after = client.get("/api/instruments", headers=H(admin)).get_json()["data"]["list"]
    check("维修中状态联动", next(i["status"] for i in after if i["id"] == ins["id"]) == "维修中")
    check("非法维修状态拦截", client.put(f"/api/repairs/{repid}", headers=H(admin),
          json={"status": "随便"}).status_code == 400)
    check("完成维修", client.put(f"/api/repairs/{repid}", headers=H(admin),
          json={"status": "已完成", "cost": 120, "repair_result": "已修复"}).status_code == 200)
    after = client.get("/api/instruments", headers=H(admin)).get_json()["data"]["list"]
    check("维修完成后仪器恢复正常", next(i["status"] for i in after if i["id"] == ins["id"]) == "正常")

    qty_before = next(i["quantity"] for i in after if i["id"] == ins["id"])
    r = client.post("/api/losses", headers=H(admin),
                    json={"instrument_id": ins["id"], "quantity": 1, "reason": "E2E损耗"})
    check("登记损耗", r.status_code == 200)
    check("损耗后库存扣减", client.get("/api/instruments", headers=H(admin)).get_json()["data"]
          and qty_before - 1 == next(i["quantity"] for i in
          client.get("/api/instruments", headers=H(admin)).get_json()["data"]["list"] if i["id"] == ins["id"]))
    check("教师登记损耗 403", client.post("/api/losses", headers=H(t1),
          json={"instrument_id": ins["id"], "quantity": 1}).status_code == 403)
    check("删除损耗记录回补库存", client.delete(f"/api/losses/{r.get_json()['data']['id']}",
          headers=H(admin)).status_code == 200)


def test_purchases():
    admin, t1 = CTX["admin"], CTX["t1"]
    r = client.post("/api/purchases", headers=H(t1), json={
        "instrument_name": "E2E采购显微镜", "category_code": "SW-E2E-100",
        "model": "XSP-02", "quantity": 3, "budget": 900, "reason": "补充"})
    check("教师保存采购草稿", r.status_code == 200 and r.get_json()["data"]["status"] == "草稿")
    pid = r.get_json()["data"]["id"]
    check("教师直接审批 403", client.put(f"/api/purchases/{pid}", headers=H(t1),
          json={"status": "已审批"}).status_code == 403)
    check("草图提交", client.put(f"/api/purchases/{pid}", headers=H(t1),
          json={"status": "已提交"}).status_code == 200)
    check("跳过审批拦截", client.put(f"/api/purchases/{pid}", headers=H(admin),
          json={"status": "已采购"}).status_code == 400)
    check("管理员审批", client.put(f"/api/purchases/{pid}", headers=H(admin),
          json={"status": "已审批"}).status_code == 200)
    check("标记已采购", client.put(f"/api/purchases/{pid}", headers=H(admin),
          json={"status": "已采购"}).status_code == 200)
    r = client.put(f"/api/purchases/{pid}/receive", headers=H(admin), json={"location": "E2E库位"})
    check("采购入库生成台账", r.status_code == 200 and r.get_json()["data"]["instrument_id"])
    new_ins_id = r.get_json()["data"]["instrument_id"]
    check("重复入库拦截", client.put(f"/api/purchases/{pid}/receive", headers=H(admin)).status_code == 400)
    check("已入库申请不可删除", client.delete(f"/api/purchases/{pid}", headers=H(admin)).status_code == 400)
    check("清理入库仪器", client.delete(f"/api/instruments/{new_ins_id}", headers=H(admin)).status_code == 200)


def test_stats():
    admin, t1 = CTX["admin"], CTX["t1"]
    data = client.get("/api/stats/overview", headers=H(admin)).get_json()["data"]
    check("概览返回核心指标", all(k in data for k in ("instrument_total", "reservation_total", "report_total")))
    report = client.get("/api/stats/report", headers=H(admin)).get_json()["data"]
    check("报表含 8 类数据", all(k in report for k in ("instrument_status", "instrument_category",
          "top_borrowed", "reservation_by_lab", "reservation_status", "repair_status",
          "loss_by_instrument", "purchase_summary")))
    check("报表返回学科下拉", "生物" in report["subjects"])

    for cat in ("instrument_status", "instrument_category", "top_borrowed", "reservation_by_lab",
                "reservation_status", "repair_status", "loss_by_instrument", "purchase_summary"):
        r = client.get(f"/api/stats/export?type={cat}", headers=H(admin))
        check(f"分类导出 {cat}", r.status_code == 200 and b"PK" in r.data[:4])
    check("非法分类导出 400", client.get("/api/stats/export?type=bad", headers=H(admin)).status_code == 400)
    check("教师导出 403", client.get("/api/stats/export?type=instrument_status", headers=H(t1)).status_code == 403)

    # P2：日期与学科筛选
    r = client.get("/api/stats/export?type=instrument_status&start_date=2099-01-01&end_date=2099-12-31",
                   headers=H(admin))
    check("未来区间导出仅表头", r.status_code == 200 and
          load_workbook(io.BytesIO(r.data)).active.max_row == 1)
    check("非法日期 400", client.get("/api/stats/export?type=instrument_status&start_date=2099-13-45",
          headers=H(admin)).status_code == 400)
    check("开始晚于结束 400", client.get("/api/stats/export?type=instrument_status"
          "&start_date=2099-12-31&end_date=2099-01-01", headers=H(admin)).status_code == 400)
    check("学科筛选导出", client.get("/api/stats/export?type=instrument_status&subject=生物",
          headers=H(admin)).status_code == 200)

    logs = client.get("/api/logs", headers=H(admin)).get_json()["data"]
    check("操作日志已记录", len(logs) > 0)
    check("教师查看日志 403", client.get("/api/logs", headers=H(t1)).status_code == 403)


def test_reports():
    admin, t1, t2 = CTX["admin"], CTX["t1"], CTX["t2"]
    r = client.post("/api/reports", headers=H(t1), json={
        "experiment_name": "E2E实验报告", "class_name": "高一(1)班",
        "instruments_used": "显微镜", "content": "观察细胞", "result": "成功"})
    check("登记实验报告", r.status_code == 200)
    repid = r.get_json()["data"]["id"]
    check("实验名称必填", client.post("/api/reports", headers=H(t1), json={}).status_code == 400)
    check("本人可编辑报告", client.put(f"/api/reports/{repid}", headers=H(t1),
          json={"result": "观察成功"}).status_code == 200)
    check("他人编辑报告 403", client.put(f"/api/reports/{repid}", headers=H(t2),
          json={"result": "篡改"}).status_code == 403)

    # P1：附件文件头校验
    real_pdf = b"%PDF-1.4\n% E2E test pdf\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    r = upload(f"/api/reports/{repid}/attachment", t1, "report.pdf", real_pdf)
    check("真实 PDF 附件上传", r.status_code == 200)
    name = r.get_json()["data"]["attachment"]
    UPLOADED.append(os.path.join(TEST_DIR, "uploads", name))
    check("伪造 PDF 拦截", upload(f"/api/reports/{repid}/attachment", t1,
          "fake.pdf", b"not a pdf").status_code == 400)
    check("空文件拦截", upload(f"/api/reports/{repid}/attachment", t1, "empty.pdf", b"").status_code == 400)
    check("非法扩展名拦截", upload(f"/api/reports/{repid}/attachment", t1, "x.exe", b"MZ").status_code == 400)

    check("单份报告导出", client.get(f"/api/reports/{repid}/export", headers=H(t1)).status_code == 200)
    tpl = client.get("/api/reports/import-template", headers=H(t1))
    check("报告导入模板", tpl.status_code == 200 and "实验名称*" in xlsx_headers(tpl.data))

    wb = Workbook()
    ws = wb.active
    ws.append(["实验名称", "实际使用时间", "参与班级", "使用仪器", "实验结果"])
    ws.append(["E2E导入报告A", "2026-11-10 09:00", "高二(1)班", "显微镜", "成功"])
    ws.append(["", "2026-11-10 09:00", "高二(1)班", "显微镜", "空名称"])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/reports/import", headers=H(t1),
                    data={"file": (io.BytesIO(buf.getvalue()), "reports.xlsx")},
                    content_type="multipart/form-data")
    body = r.get_json()["data"]
    check("报告批量导入 1 成功 1 跳过", r.status_code == 200 and body["ok"] == 1 and body["skip"] == 1)
    check("报告汇总导出", client.get("/api/reports/export", headers=H(t1)).status_code == 200)

    # 关联数据保护：t2 的报告使其无法被删除
    r = client.post("/api/reports", headers=H(t2), json={"experiment_name": "E2E关联报告"})
    CTX["t2_report"] = r.get_json()["data"]["id"]
    users = client.get("/api/users", headers=H(admin)).get_json()["data"]
    t2_id = next(u["id"] for u in users if u["username"] == "e2e_t2")
    check("存在关联数据时禁止删除账号", client.delete(f"/api/users/{t2_id}", headers=H(admin)).status_code == 400)

    check("删除报告", client.delete(f"/api/reports/{repid}", headers=H(t1)).status_code == 200)
    check("清理 t2 报告", client.delete(f"/api/reports/{CTX['t2_report']}", headers=H(admin)).status_code == 200)
    check("清理 t2 账号", client.delete(f"/api/users/{t2_id}", headers=H(admin)).status_code == 200)

    sys_id = next(u["id"] for u in client.get("/api/users", headers=H(admin)).get_json()["data"]
                  if u["username"] == "e2e_sys")
    check("清理系统管理员账号", client.delete(f"/api/users/{sys_id}", headers=H(admin)).status_code == 200)


def test_sqlite_pragmas():
    """P2：WAL 与写锁等待已生效"""
    with app.app_context():
        mode = db.session.execute(db.text("PRAGMA journal_mode")).scalar()
        timeout = db.session.execute(db.text("PRAGMA busy_timeout")).scalar()
    check("SQLite 已开启 WAL", str(mode).lower() == "wal", str(mode))
    check("busy_timeout=30000", int(timeout or 0) >= 30000, str(timeout))


def cleanup():
    for path in UPLOADED:
        try:
            os.remove(path)
        except OSError:
            pass
    shutil.rmtree(TMP_DIR, ignore_errors=True)


def main():
    tests = [test_pages, test_auth, test_users_and_classes, test_instruments, test_catalog,
             test_plans_notices, test_reservations, test_borrow_repair_loss, test_purchases,
             test_stats, test_reports, test_sqlite_pragmas]
    for fn in tests:
        try:
            fn()
        except Exception as e:  # 单个模块异常不影响其他模块，计入失败
            FAILED.append(f"{fn.__name__} 异常：{type(e).__name__}: {e}")
    cleanup()

    print("=" * 60)
    print(f"通过 {PASSED} 项，失败 {len(FAILED)} 项")
    for item in FAILED:
        print("  [FAIL] " + item)
    print("=" * 60)
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
