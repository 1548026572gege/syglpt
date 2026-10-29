# -*- coding: utf-8 -*-
"""实验预约管理模块（3.3）：教师提交预约、管理员审核、状态跟踪、日历视图"""
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from models import db, Reservation
from auth import login_required, role_required, log_action

bp = Blueprint("reservations", __name__, url_prefix="/api/reservations")

STATUS = {"待审核", "已通过", "已驳回", "已完成", "已取消"}


def _parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


@bp.get("")
@login_required
def list_reservations():
    status = request.args.get("status", "").strip()
    q = Reservation.query
    # 教师只能看自己的预约，管理员看全部
    if g.current_user.role == "teacher":
        q = q.filter(Reservation.teacher_id == g.current_user.id)
    if status:
        q = q.filter(Reservation.status == status)
    items = q.order_by(Reservation.start_time.desc()).all()
    return jsonify({"code": 0, "data": [r.to_dict() for r in items]})


@bp.get("/calendar")
@login_required
def calendar():
    """日历视图数据：按月返回已通过的预约"""
    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    q = Reservation.query.filter(Reservation.status == "已通过",
                                 db.func.strftime("%Y-%m", Reservation.start_time) == month) \
        if db.get_engine().name == "sqlite" else \
        Reservation.query.filter(Reservation.status == "已通过",
                                 db.func.date_format(Reservation.start_time, "%Y-%m") == month)
    events = [{
        "id": r.id, "title": f"{r.experiment_name}（{r.lab_name}）",
        "date": r.start_time.strftime("%Y-%m-%d") if r.start_time else "",
        "start": r.start_time.strftime("%H:%M") if r.start_time else "",
        "end": r.end_time.strftime("%H:%M") if r.end_time else "",
        "teacher": r.teacher.name if r.teacher else "",
    } for r in q.order_by(Reservation.start_time).all()]
    return jsonify({"code": 0, "data": events})


@bp.post("")
@role_required("teacher", "admin", "sysadmin")
def create_reservation():
    data = request.get_json(force=True, silent=True) or {}
    start, end = _parse_dt(data.get("start_time")), _parse_dt(data.get("end_time"))
    if not data.get("lab_name") or not data.get("experiment_name") or not start or not end:
        return jsonify({"code": 400, "msg": "实验室、实验名称、起止时间不能为空"}), 400
    if end <= start:
        return jsonify({"code": 400, "msg": "结束时间必须晚于开始时间"}), 400
    # 时间冲突校验：同一实验室已通过的预约不能重叠
    conflict = Reservation.query.filter(
        Reservation.lab_name == data["lab_name"],
        Reservation.status.in_(["待审核", "已通过"]),
        Reservation.start_time < end, Reservation.end_time > start).first()
    if conflict:
        return jsonify({"code": 400,
                        "msg": f"该时段与已有预约冲突（{conflict.experiment_name} "
                               f"{conflict.start_time.strftime('%m-%d %H:%M')}）"}), 400
    r = Reservation(teacher_id=g.current_user.id, lab_name=data["lab_name"],
                    experiment_name=data["experiment_name"],
                    class_name=data.get("class_name", ""),
                    student_count=data.get("student_count"), group_count=data.get("group_count"),
                    start_time=start, end_time=end, remark=data.get("remark", ""))
    db.session.add(r)
    db.session.commit()
    log_action("提交实验预约", f"{r.experiment_name} @ {r.lab_name}")
    return jsonify({"code": 0, "msg": "预约已提交，等待管理员审核", "data": r.to_dict()})


@bp.put("/<int:rid>")
@login_required
def update_reservation(rid):
    """编辑预约：教师可编辑自己的预约（待审核/已驳回，改后重置为待审核）；管理员可编辑所有未结束的预约"""
    r = db.session.get(Reservation, rid)
    if not r:
        return jsonify({"code": 404, "msg": "预约不存在"}), 404
    is_admin = g.current_user.role in ("admin", "sysadmin")
    if not is_admin and r.teacher_id != g.current_user.id:
        return jsonify({"code": 403, "msg": "只能编辑自己的预约"}), 403
    if r.status in ("已完成", "已取消"):
        return jsonify({"code": 400, "msg": "已结束的预约不能编辑"}), 400
    data = request.get_json(force=True, silent=True) or {}
    lab = data.get("lab_name") or r.lab_name
    name = data.get("experiment_name") or r.experiment_name
    start = _parse_dt(data.get("start_time")) or r.start_time
    end = _parse_dt(data.get("end_time")) or r.end_time
    if not lab or not name or not start or not end:
        return jsonify({"code": 400, "msg": "实验室、实验名称、起止时间不能为空"}), 400
    if end <= start:
        return jsonify({"code": 400, "msg": "结束时间必须晚于开始时间"}), 400
    # 时间冲突校验（排除自身）
    conflict = Reservation.query.filter(
        Reservation.id != r.id,
        Reservation.lab_name == lab,
        Reservation.status.in_(["待审核", "已通过"]),
        Reservation.start_time < end, Reservation.end_time > start).first()
    if conflict:
        return jsonify({"code": 400,
                        "msg": f"该时段与已有预约冲突（{conflict.experiment_name} "
                               f"{conflict.start_time.strftime('%m-%d %H:%M')}）"}), 400
    r.lab_name, r.experiment_name = lab, name
    r.start_time, r.end_time = start, end
    if "class_name" in data:
        r.class_name = data["class_name"]
    if "student_count" in data:
        r.student_count = data.get("student_count")
    if "group_count" in data:
        r.group_count = data.get("group_count")
    if "remark" in data:
        r.remark = data.get("remark")
    if not is_admin:
        r.status = "待审核"   # 教师修改后需重新审核
        r.review_comment = ""
    db.session.commit()
    log_action("编辑实验预约", f"#{r.id} {r.experiment_name} @ {r.lab_name}")
    return jsonify({"code": 0, "msg": "保存成功", "data": r.to_dict()})


@bp.delete("/<int:rid>")
@login_required
def delete_reservation(rid):
    """删除预约：教师只能删除自己的待审核/已驳回预约；管理员可删除任意预约"""
    r = db.session.get(Reservation, rid)
    if not r:
        return jsonify({"code": 404, "msg": "预约不存在"}), 404
    is_admin = g.current_user.role in ("admin", "sysadmin")
    if not is_admin and r.teacher_id != g.current_user.id:
        return jsonify({"code": 403, "msg": "只能删除自己的预约"}), 403
    if not is_admin and r.status not in ("待审核", "已驳回"):
        return jsonify({"code": 400, "msg": "仅待审核或已驳回的预约可删除，已通过的请走取消流程"}), 400
    info = f"#{r.id} {r.experiment_name} @ {r.lab_name}（{r.teacher.name if r.teacher else ''}）"
    db.session.delete(r)
    db.session.commit()
    log_action("删除实验预约", info)
    return jsonify({"code": 0, "msg": "删除成功"})


@bp.put("/<int:rid>/review")
@role_required("admin", "sysadmin")
def review_reservation(rid):
    r = db.session.get(Reservation, rid)
    if not r:
        return jsonify({"code": 404, "msg": "预约不存在"}), 404
    if r.status != "待审核":
        return jsonify({"code": 400, "msg": "仅待审核的预约可以审核"}), 400
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")  # approve / reject / adjust
    if action == "approve":
        r.status = "已通过"
    elif action == "reject":
        r.status = "已驳回"
    elif action == "adjust":
        start, end = _parse_dt(data.get("start_time")), _parse_dt(data.get("end_time"))
        if not start or not end or end <= start:
            return jsonify({"code": 400, "msg": "调整时间无效"}), 400
        r.start_time, r.end_time = start, end
        r.status = "已通过"
    else:
        return jsonify({"code": 400, "msg": "无效的审核操作"}), 400
    r.review_comment = data.get("comment", "")
    r.reviewer_id = g.current_user.id
    db.session.commit()
    log_action("审核实验预约", f"#{r.id} {r.experiment_name} -> {r.status}")
    return jsonify({"code": 0, "msg": "审核完成", "data": r.to_dict()})


@bp.put("/<int:rid>/cancel")
@login_required
def cancel_reservation(rid):
    r = db.session.get(Reservation, rid)
    if not r:
        return jsonify({"code": 404, "msg": "预约不存在"}), 404
    if g.current_user.role == "teacher" and r.teacher_id != g.current_user.id:
        return jsonify({"code": 403, "msg": "只能取消自己的预约"}), 403
    if r.status in ("已完成", "已取消"):
        return jsonify({"code": 400, "msg": "该预约已结束，无法取消"}), 400
    r.status = "已取消"
    db.session.commit()
    log_action("取消实验预约", f"#{r.id} {r.experiment_name}")
    return jsonify({"code": 0, "msg": "已取消"})


@bp.put("/<int:rid>/complete")
@role_required("admin", "sysadmin")
def complete_reservation(rid):
    r = db.session.get(Reservation, rid)
    if not r:
        return jsonify({"code": 404, "msg": "预约不存在"}), 404
    if r.status != "已通过":
        return jsonify({"code": 400, "msg": "仅已通过的预约可标记完成"}), 400
    r.status = "已完成"
    db.session.commit()
    log_action("完成实验预约", f"#{r.id} {r.experiment_name}")
    return jsonify({"code": 0, "msg": "已标记完成"})
