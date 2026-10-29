# -*- coding: utf-8 -*-
"""统计报表模块（3.10）：仪器使用率、预约频次、维修/损耗统计、采购汇总；操作日志"""
from flask import Blueprint, jsonify, g

from models import (db, Instrument, Reservation, BorrowRecord, RepairRecord,
                    LossRecord, PurchaseRequest, OperationLog, User, ExperimentReport)
from auth import login_required, role_required

bp = Blueprint("stats", __name__, url_prefix="/api")


@bp.get("/stats/overview")
@login_required
def overview():
    """仪表盘概览数据"""
    data = {
        "instrument_total": Instrument.query.count(),
        "instrument_qty": db.session.query(db.func.coalesce(db.func.sum(Instrument.quantity), 0)).scalar(),
        "reservation_pending": Reservation.query.filter_by(status="待审核").count(),
        "reservation_total": Reservation.query.count(),
        "borrow_active": BorrowRecord.query.filter_by(status="已借出").count(),
        "repair_active": RepairRecord.query.filter(RepairRecord.status.in_(["报修中", "维修中"])).count(),
        "purchase_pending": PurchaseRequest.query.filter_by(status="已提交").count(),
        "loss_total": db.session.query(db.func.coalesce(db.func.sum(LossRecord.quantity), 0)).scalar(),
        "report_total": ExperimentReport.query.count(),
        "user_total": User.query.count(),
    }
    return jsonify({"code": 0, "data": data})


@bp.get("/stats/report")
@role_required("admin", "sysadmin")
def report():
    """统计报表"""
    # 仪器状态分布
    status_rows = db.session.query(Instrument.status, db.func.count(Instrument.id)) \
        .group_by(Instrument.status).all()
    # 仪器分类分布
    cat_rows = db.session.query(Instrument.category, db.func.count(Instrument.id)) \
        .group_by(Instrument.category).all()
    # 借用次数最多的仪器（使用率参考）
    borrow_rows = db.session.query(Instrument.name, db.func.count(BorrowRecord.id)) \
        .join(BorrowRecord, BorrowRecord.instrument_id == Instrument.id) \
        .group_by(Instrument.id).order_by(db.func.count(BorrowRecord.id).desc()).limit(10).all()
    # 预约频次（按实验室）
    lab_rows = db.session.query(Reservation.lab_name, db.func.count(Reservation.id)) \
        .group_by(Reservation.lab_name).all()
    # 预约状态分布
    rv_rows = db.session.query(Reservation.status, db.func.count(Reservation.id)) \
        .group_by(Reservation.status).all()
    # 维修统计
    repair_rows = db.session.query(RepairRecord.status, db.func.count(RepairRecord.id)) \
        .group_by(RepairRecord.status).all()
    repair_cost = db.session.query(db.func.coalesce(db.func.sum(RepairRecord.cost), 0)).scalar()
    # 损耗统计（按仪器）
    loss_rows = db.session.query(Instrument.name, db.func.sum(LossRecord.quantity)) \
        .join(LossRecord, LossRecord.instrument_id == Instrument.id) \
        .group_by(Instrument.id).all()
    # 采购汇总
    purchase_rows = db.session.query(PurchaseRequest.status, db.func.count(PurchaseRequest.id),
                                     db.func.coalesce(db.func.sum(PurchaseRequest.budget), 0)) \
        .group_by(PurchaseRequest.status).all()
    return jsonify({"code": 0, "data": {
        "instrument_status": [{"name": s or "未知", "value": c} for s, c in status_rows],
        "instrument_category": [{"name": c0 or "未分类", "value": c1} for c0, c1 in cat_rows],
        "top_borrowed": [{"name": n, "value": c} for n, c in borrow_rows],
        "reservation_by_lab": [{"name": l, "value": c} for l, c in lab_rows],
        "reservation_status": [{"name": s, "value": c} for s, c in rv_rows],
        "repair_status": [{"name": s, "value": c} for s, c in repair_rows],
        "repair_cost_total": repair_cost,
        "loss_by_instrument": [{"name": n, "value": int(q or 0)} for n, q in loss_rows],
        "purchase_summary": [{"status": s, "count": c, "budget": b} for s, c, b in purchase_rows],
    }})


@bp.get("/logs")
@role_required("admin", "sysadmin")
def logs():
    items = OperationLog.query.order_by(OperationLog.id.desc()).limit(200).all()
    return jsonify({"code": 0, "data": [l.to_dict() for l in items]})
