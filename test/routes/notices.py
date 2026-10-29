# -*- coding: utf-8 -*-
"""实验通知单模块（3.9）：管理员编辑发送、教师接收查看，支持导出与打印数据"""
import io

from flask import Blueprint, request, jsonify, g, send_file
from openpyxl import Workbook

from models import db, Notice
from auth import login_required, role_required, log_action

bp = Blueprint("notices", __name__, url_prefix="/api/notices")

FIELDS = ("title", "subject", "classes", "teacher_name", "lab_name",
          "experiment_time", "instruments", "content")


@bp.get("")
@login_required
def list_notices():
    items = Notice.query.order_by(Notice.id.desc()).all()
    return jsonify({"code": 0, "data": [n.to_dict() for n in items]})


@bp.post("")
@role_required("admin", "sysadmin")
def create_notice():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("title"):
        return jsonify({"code": 400, "msg": "实验名称不能为空"}), 400
    n = Notice(**{f: data.get(f, "") for f in FIELDS}, sender_id=g.current_user.id)
    db.session.add(n)
    db.session.commit()
    log_action("发送实验通知单", n.title)
    return jsonify({"code": 0, "msg": "通知已发送", "data": n.to_dict()})


@bp.put("/<int:nid>")
@role_required("admin", "sysadmin")
def update_notice(nid):
    n = db.session.get(Notice, nid)
    if not n:
        return jsonify({"code": 404, "msg": "通知不存在"}), 404
    data = request.get_json(force=True, silent=True) or {}
    for f in FIELDS:
        if f in data:
            setattr(n, f, data[f])
    db.session.commit()
    return jsonify({"code": 0, "msg": "保存成功", "data": n.to_dict()})


@bp.delete("/<int:nid>")
@role_required("admin", "sysadmin")
def delete_notice(nid):
    n = db.session.get(Notice, nid)
    if not n:
        return jsonify({"code": 404, "msg": "通知不存在"}), 404
    db.session.delete(n)
    db.session.commit()
    log_action("删除实验通知单", f"#{nid} {n.title}")
    return jsonify({"code": 0, "msg": "删除成功"})


HEADERS = ["序号", "科目", "实验名称", "班级", "任教教师", "实验时间", "地点",
           "实验内容", "实验仪器、用品", "发布人", "发布时间"]


@bp.get("/export")
@login_required
def export_notices():
    wb = Workbook()
    ws = wb.active
    ws.title = "实验通知单"
    ws.append(HEADERS)
    for idx, n in enumerate(Notice.query.order_by(Notice.id.desc()).all(), start=1):
        ws.append([idx, n.subject, n.title, n.classes, n.teacher_name, n.experiment_time,
                   n.lab_name, n.content, n.instruments,
                   n.sender.name if n.sender else "",
                   n.created_at.strftime("%Y-%m-%d %H:%M") if n.created_at else ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    log_action("导出实验通知单", f"共{len(Notice.query.all())}条")
    return send_file(buf, as_attachment=True, download_name="实验通知单.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
