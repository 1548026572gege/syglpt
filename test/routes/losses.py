# -*- coding: utf-8 -*-
"""仪器损耗管理模块（3.7）：损耗登记、统计查询"""
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from models import db, LossRecord, Instrument
from auth import login_required, role_required, log_action

bp = Blueprint("losses", __name__, url_prefix="/api/losses")


@bp.get("")
@login_required
def list_losses():
    kw = request.args.get("kw", "").strip()
    q = LossRecord.query.join(Instrument, LossRecord.instrument_id == Instrument.id)
    if kw:
        q = q.filter(db.or_(Instrument.name.contains(kw), Instrument.code.contains(kw)))
    items = q.order_by(LossRecord.id.desc()).all()
    return jsonify({"code": 0, "data": [r.to_dict() for r in items]})


@bp.post("")
@role_required("admin", "sysadmin")
def create_loss():
    data = request.get_json(force=True, silent=True) or {}
    ins = db.session.get(Instrument, int(data.get("instrument_id") or 0))
    if not ins:
        return jsonify({"code": 404, "msg": "仪器不存在"}), 404
    qty = int(data.get("quantity") or 1)
    if qty < 1 or qty > (ins.quantity or 0):
        return jsonify({"code": 400, "msg": f"损耗数量需在 1~{ins.quantity} 之间"}), 400
    ins.quantity -= qty
    if ins.quantity == 0:
        ins.status = "损耗"
    r = LossRecord(instrument_id=ins.id, quantity=qty, reason=data.get("reason", ""),
                   responsible=data.get("responsible", ""), handler_id=g.current_user.id)
    db.session.add(r)
    db.session.commit()
    log_action("登记仪器损耗", f"{ins.code} {ins.name} x{qty}")
    return jsonify({"code": 0, "msg": "损耗登记成功", "data": r.to_dict()})


@bp.delete("/<int:lid>")
@role_required("admin", "sysadmin")
def delete_loss(lid):
    r = db.session.get(LossRecord, lid)
    if not r:
        return jsonify({"code": 404, "msg": "记录不存在"}), 404
    ins = db.session.get(Instrument, r.instrument_id)
    if ins:
        ins.quantity = (ins.quantity or 0) + r.quantity
        if ins.status == "损耗" and ins.quantity > 0:
            ins.status = "正常"
    db.session.delete(r)
    db.session.commit()
    log_action("删除损耗记录", f"#{lid}（已回补库存）")
    return jsonify({"code": 0, "msg": "删除成功"})
