# -*- coding: utf-8 -*-
"""实验计划模块：按《实验计划书》模板维护年级、实验名称、类别、地点、计划时间"""
import io

from flask import Blueprint, request, jsonify, g, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side

from models import db, ExperimentPlan
from auth import login_required, role_required, log_action

bp = Blueprint("plans", __name__, url_prefix="/api/plans")

CATEGORIES = ("演示", "分组")
LOCATIONS = ("生物实验室1", "生物实验室2", "教室")
FIELDS = ("grade", "experiment_name", "category", "location", "planned_time")
HEADERS = ["年级", "实验名称", "类别", "实验地点", "计划时间"]


def _validate(data, partial=False):
    """校验类别与地点枚举；返回错误信息或 None"""
    if "category" in data or not partial:
        if data.get("category") not in CATEGORIES:
            return "类别只能选择「演示」或「分组」"
    if "location" in data or not partial:
        if data.get("location") not in LOCATIONS:
            return "实验地点只能选择「生物实验室1」「生物实验室2」或「教室」"
    return None


@bp.get("")
@login_required
def list_plans():
    items = ExperimentPlan.query.order_by(
        db.func.coalesce(ExperimentPlan.planned_time, "9999-12-31").asc(),
        ExperimentPlan.id.desc()).all()
    return jsonify({"code": 0, "data": [p.to_dict() for p in items]})


@bp.post("")
@role_required("teacher", "admin", "sysadmin")
def create_plan():
    data = request.get_json(force=True, silent=True) or {}
    if not (data.get("grade") or "").strip() or not (data.get("experiment_name") or "").strip():
        return jsonify({"code": 400, "msg": "年级和实验名称不能为空"}), 400
    err = _validate(data)
    if err:
        return jsonify({"code": 400, "msg": err}), 400
    p = ExperimentPlan(
        grade=data["grade"].strip(),
        experiment_name=data["experiment_name"].strip(),
        category=data["category"],
        location=data["location"],
        planned_time=(data.get("planned_time") or "").strip(),
        creator_id=g.current_user.id,
    )
    db.session.add(p)
    db.session.commit()
    log_action("新增实验计划", f"{p.grade} {p.experiment_name} {p.planned_time}")
    return jsonify({"code": 0, "msg": "新增成功", "data": p.to_dict()})


def _may_modify(p):
    """管理员可维护任意计划，教师只能维护自己创建的"""
    return (g.current_user.role in ("admin", "sysadmin")
            or p.creator_id == g.current_user.id)


@bp.put("/<int:pid>")
@login_required
def update_plan(pid):
    p = db.session.get(ExperimentPlan, pid)
    if not p:
        return jsonify({"code": 404, "msg": "实验计划不存在"}), 404
    if not _may_modify(p):
        return jsonify({"code": 403, "msg": "只能编辑自己创建的实验计划"}), 403
    data = request.get_json(force=True, silent=True) or {}
    err = _validate(data, partial=True)
    if err:
        return jsonify({"code": 400, "msg": err}), 400
    for f in FIELDS:
        if f in data:
            setattr(p, f, data[f])
    if not (p.grade or "").strip() or not (p.experiment_name or "").strip():
        return jsonify({"code": 400, "msg": "年级和实验名称不能为空"}), 400
    db.session.commit()
    log_action("编辑实验计划", f"#{pid} {p.experiment_name}")
    return jsonify({"code": 0, "msg": "保存成功", "data": p.to_dict()})


@bp.delete("/<int:pid>")
@login_required
def delete_plan(pid):
    p = db.session.get(ExperimentPlan, pid)
    if not p:
        return jsonify({"code": 404, "msg": "实验计划不存在"}), 404
    if not _may_modify(p):
        return jsonify({"code": 403, "msg": "只能删除自己创建的实验计划"}), 403
    db.session.delete(p)
    db.session.commit()
    log_action("删除实验计划", f"#{pid} {p.experiment_name}")
    return jsonify({"code": 0, "msg": "删除成功"})


@bp.get("/export")
@login_required
def export_plans():
    items = ExperimentPlan.query.order_by(
        db.func.coalesce(ExperimentPlan.planned_time, "9999-12-31").asc(),
        ExperimentPlan.id.desc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "实验计划"
    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_font = Font(name="宋体", size=11, bold=True)
    center = Alignment(horizontal="center", vertical="center")
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = header_font
        cell.alignment = center
        cell.border = border
    for p in items:
        ws.append([p.grade, p.experiment_name, p.category, p.location, p.planned_time])
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = center
            cell.border = border
    for col, width in zip("ABCDE", (12, 30, 10, 16, 16)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    log_action("导出实验计划", f"共{len(items)}条")
    return send_file(buf, as_attachment=True, download_name="实验计划.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
