# -*- coding: utf-8 -*-
"""仪器维修管理模块（3.6）：故障上报、维修记录、状态跟踪"""
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from models import db, RepairRecord, Instrument
from auth import login_required, role_required, log_action

bp = Blueprint("repairs", __name__, url_prefix="/api/repairs")

STATUS = {"报修中", "维修中", "已完成", "报废"}


@bp.get("")
@login_required
def list_repairs():
    status = request.args.get("status", "").strip()
    q = RepairRecord.query
    if status:
        q = q.filter(RepairRecord.status == status)
    items = q.order_by(RepairRecord.id.desc()).all()
    return jsonify({"code": 0, "data": [r.to_dict() for r in items]})


@bp.post("")
@login_required
def report_fault():
    """故障上报：教师与管理员均可上报"""
    data = request.get_json(force=True, silent=True) or {}
    ins = db.session.get(Instrument, int(data.get("instrument_id") or 0))
    if not ins:
        return jsonify({"code": 404, "msg": "仪器不存在"}), 404
    if not data.get("fault_desc"):
        return jsonify({"code": 400, "msg": "请填写故障描述"}), 400
    r = RepairRecord(instrument_id=ins.id, fault_desc=data["fault_desc"],
                     reporter_id=g.current_user.id)
    ins.status = "维修中"
    db.session.add(r)
    db.session.commit()
    log_action("上报仪器故障", f"{ins.code} {ins.name}")
    return jsonify({"code": 0, "msg": "故障已上报", "data": r.to_dict()})


@bp.put("/<int:rid>")
@role_required("admin", "sysadmin")
def update_repair(rid):
    """维修登记/状态更新"""
    r = db.session.get(RepairRecord, rid)
    if not r:
        return jsonify({"code": 404, "msg": "维修记录不存在"}), 404
    data = request.get_json(force=True, silent=True) or {}
    status = data.get("status")
    if status and status not in STATUS:
        return jsonify({"code": 400, "msg": "无效的维修状态"}), 400
    if "repair_result" in data:
        r.repair_result = data["repair_result"]
    if "cost" in data:
        r.cost = float(data["cost"] or 0)
    if status:
        r.status = status
        if status in ("维修中", "已完成"):
            r.repair_time = datetime.now()
        ins = db.session.get(Instrument, r.instrument_id)
        if status == "已完成":
            ins.status = "正常"
        elif status == "报废":
            ins.status = "报废"
    db.session.commit()
    log_action("更新维修记录", f"#{r.id} -> {r.status}")
    return jsonify({"code": 0, "msg": "保存成功", "data": r.to_dict()})
