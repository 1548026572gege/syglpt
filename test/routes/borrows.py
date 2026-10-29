# -*- coding: utf-8 -*-
"""仪器借用管理模块（3.5）：借用申请、借出登记、归还登记、逾期提醒"""
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from models import db, BorrowRecord, Instrument
from auth import login_required, role_required, log_action

bp = Blueprint("borrows", __name__, url_prefix="/api/borrows")


def _parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


@bp.get("")
@login_required
def list_borrows():
    status = request.args.get("status", "").strip()
    overdue = request.args.get("overdue", "")
    q = BorrowRecord.query
    if g.current_user.role == "teacher":
        q = q.filter(BorrowRecord.teacher_id == g.current_user.id)
    if status:
        q = q.filter(BorrowRecord.status == status)
    items = q.order_by(BorrowRecord.id.desc()).all()
    result = [b.to_dict() for b in items]
    if overdue == "1":
        result = [b for b in result if b["overdue"]]
    return jsonify({"code": 0, "data": result})


@bp.post("")
@role_required("teacher", "admin", "sysadmin")
def apply_borrow():
    data = request.get_json(force=True, silent=True) or {}
    ins = db.session.get(Instrument, int(data.get("instrument_id") or 0))
    if not ins:
        return jsonify({"code": 404, "msg": "仪器不存在"}), 404
    if ins.status != "正常":
        return jsonify({"code": 400, "msg": f"该仪器当前状态为「{ins.status}」，不可借用"}), 400
    qty = int(data.get("quantity") or 1)
    if qty < 1 or qty > (ins.quantity or 1):
        return jsonify({"code": 400, "msg": f"借用数量需在 1~{ins.quantity} 之间"}), 400
    expect = _parse_dt(data.get("expect_return_time"))
    b = BorrowRecord(instrument_id=ins.id, teacher_id=g.current_user.id, quantity=qty,
                     purpose=data.get("purpose", ""), expect_return_time=expect)
    db.session.add(b)
    db.session.commit()
    log_action("申请仪器借用", f"{ins.code} {ins.name} x{qty}")
    return jsonify({"code": 0, "msg": "借用申请已提交", "data": b.to_dict()})


@bp.put("/<int:bid>/lend")
@role_required("admin", "sysadmin")
def lend(bid):
    """管理员确认借出"""
    b = db.session.get(BorrowRecord, bid)
    if not b:
        return jsonify({"code": 404, "msg": "借用记录不存在"}), 404
    if b.status != "申请中":
        return jsonify({"code": 400, "msg": "仅申请中的记录可确认借出"}), 400
    ins = db.session.get(Instrument, b.instrument_id)
    if not ins or (ins.quantity or 0) < b.quantity:
        return jsonify({"code": 400, "msg": "仪器库存不足"}), 400
    ins.quantity -= b.quantity
    if ins.quantity == 0:
        ins.status = "借出"
    b.status = "已借出"
    b.borrow_time = datetime.now()
    db.session.commit()
    log_action("确认借出仪器", f"{ins.code} {ins.name} x{b.quantity} -> {b.teacher.name}")
    return jsonify({"code": 0, "msg": "已确认借出"})


@bp.put("/<int:bid>/reject")
@role_required("admin", "sysadmin")
def reject(bid):
    b = db.session.get(BorrowRecord, bid)
    if not b:
        return jsonify({"code": 404, "msg": "借用记录不存在"}), 404
    if b.status != "申请中":
        return jsonify({"code": 400, "msg": "仅申请中的记录可驳回"}), 400
    b.status = "已驳回"
    db.session.commit()
    log_action("驳回借用申请", f"#{b.id}")
    return jsonify({"code": 0, "msg": "已驳回"})


@bp.put("/<int:bid>/return")
@role_required("admin", "sysadmin")
def return_back(bid):
    """归还登记"""
    b = db.session.get(BorrowRecord, bid)
    if not b:
        return jsonify({"code": 404, "msg": "借用记录不存在"}), 404
    if b.status != "已借出":
        return jsonify({"code": 400, "msg": "仅已借出的记录可归还登记"}), 400
    data = request.get_json(force=True, silent=True) or {}
    ins = db.session.get(Instrument, b.instrument_id)
    ins.quantity = (ins.quantity or 0) + b.quantity
    if ins.status == "借出":
        ins.status = "正常"
    b.status = "已归还"
    b.return_time = datetime.now()
    b.return_status = data.get("return_status", "完好")
    db.session.commit()
    log_action("仪器归还登记", f"{ins.code} {ins.name} x{b.quantity} 状态:{b.return_status}")
    return jsonify({"code": 0, "msg": "归还登记完成"})
