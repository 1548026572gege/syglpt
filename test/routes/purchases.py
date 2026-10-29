# -*- coding: utf-8 -*-
"""采购申报管理模块（3.8）：采购申请、状态跟踪、记录查询"""
from flask import Blueprint, request, jsonify, g

from models import db, PurchaseRequest
from auth import login_required, role_required, log_action

bp = Blueprint("purchases", __name__, url_prefix="/api/purchases")

FLOW = {"草稿": ["已提交"], "已提交": ["已审批", "已驳回"], "已审批": ["已采购"]}


@bp.get("")
@login_required
def list_purchases():
    status = request.args.get("status", "").strip()
    q = PurchaseRequest.query
    if g.current_user.role == "teacher":
        q = q.filter(PurchaseRequest.applicant_id == g.current_user.id)
    if status:
        q = q.filter(PurchaseRequest.status == status)
    items = q.order_by(PurchaseRequest.id.desc()).all()
    return jsonify({"code": 0, "data": [p.to_dict() for p in items]})


@bp.post("")
@role_required("teacher", "admin", "sysadmin")
def create_purchase():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("instrument_name"):
        return jsonify({"code": 400, "msg": "仪器名称不能为空"}), 400
    p = PurchaseRequest(instrument_name=data["instrument_name"], model=data.get("model", ""),
                        quantity=int(data.get("quantity") or 1), budget=float(data.get("budget") or 0),
                        reason=data.get("reason", ""), applicant_id=g.current_user.id,
                        status="已提交" if data.get("submit") else "草稿")
    db.session.add(p)
    db.session.commit()
    log_action("提交采购申报" if p.status == "已提交" else "保存采购草稿",
               f"{p.instrument_name} x{p.quantity}")
    return jsonify({"code": 0, "msg": "保存成功", "data": p.to_dict()})


@bp.put("/<int:pid>")
@login_required
def update_purchase(pid):
    p = db.session.get(PurchaseRequest, pid)
    if not p:
        return jsonify({"code": 404, "msg": "采购申请不存在"}), 404
    data = request.get_json(force=True, silent=True) or {}

    # 状态流转（管理员审批/标记采购）
    new_status = data.get("status")
    if new_status:
        if g.current_user.role not in ("admin", "sysadmin") and new_status != "已提交":
            return jsonify({"code": 403, "msg": "无权限变更该状态"}), 403
        allowed = FLOW.get(p.status, [])
        # 草稿可直接提交
        if p.status == "草稿" and new_status == "已提交":
            allowed = ["已提交"]
        if new_status not in allowed:
            return jsonify({"code": 400, "msg": f"当前状态「{p.status}」不能变更为「{new_status}」"}), 400
        p.status = new_status
        p.review_comment = data.get("review_comment", p.review_comment)
        log_action("采购状态变更", f"#{p.id} {p.instrument_name} -> {new_status}")
        db.session.commit()
        return jsonify({"code": 0, "msg": "状态已更新", "data": p.to_dict()})

    # 内容编辑：仅申请人本人、且为草稿状态
    if p.applicant_id != g.current_user.id and g.current_user.role not in ("admin", "sysadmin"):
        return jsonify({"code": 403, "msg": "只能编辑自己的申请"}), 403
    if p.status != "草稿":
        return jsonify({"code": 400, "msg": "仅草稿状态可编辑内容"}), 400
    for f in ("instrument_name", "model", "reason"):
        if f in data:
            setattr(p, f, data[f])
    if "quantity" in data:
        p.quantity = int(data["quantity"] or 1)
    if "budget" in data:
        p.budget = float(data["budget"] or 0)
    db.session.commit()
    return jsonify({"code": 0, "msg": "保存成功", "data": p.to_dict()})


@bp.delete("/<int:pid>")
@login_required
def delete_purchase(pid):
    p = db.session.get(PurchaseRequest, pid)
    if not p:
        return jsonify({"code": 404, "msg": "采购申请不存在"}), 404
    if p.applicant_id != g.current_user.id and g.current_user.role not in ("admin", "sysadmin"):
        return jsonify({"code": 403, "msg": "只能删除自己的申请"}), 403
    if p.status not in ("草稿", "已驳回"):
        return jsonify({"code": 400, "msg": "仅草稿或已驳回的申请可删除"}), 400
    db.session.delete(p)
    db.session.commit()
    log_action("删除采购申请", f"#{pid} {p.instrument_name}")
    return jsonify({"code": 0, "msg": "删除成功"})
