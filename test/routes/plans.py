# -*- coding: utf-8 -*-
"""实验计划模块：按《实验计划书》模板维护年级、实验名称、类别、地点、计划时间"""
import io
from datetime import date, datetime

from flask import Blueprint, request, jsonify, g, send_file
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils.datetime import from_excel

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


def _norm_date(value):
    """将 Excel 日期、文本日期统一为 YYYY-MM-DD"""
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (int, float)):
        try:
            return from_excel(value).strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            return str(value)
    s = str(value).strip()
    for sep in ("/", "."):
        if sep in s:
            s = s.replace(sep, "-")
    return s


@bp.post("/import")
@role_required("teacher", "admin", "sysadmin")
def import_plans():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"code": 400, "msg": "请选择要导入的 Excel 文件"}), 400
    if not f.filename.lower().endswith((".xlsx", ".xlsm")):
        return jsonify({"code": 400, "msg": "仅支持 .xlsx 或 .xlsm 文件"}), 400
    try:
        wb = load_workbook(f.stream, data_only=True, read_only=True)
    except Exception:
        return jsonify({"code": 400, "msg": "Excel 文件无法解析，请使用模板格式"}), 400

    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = [str(c).strip() if c is not None else "" for c in next(rows, [])]
    idx = {h: i for i, h in enumerate(header) if h}
    missing = [h for h in HEADERS if h not in idx]
    if missing:
        wb.close()
        return jsonify({"code": 400, "msg": "表头缺少：" + "、".join(missing)}), 400

    imported, skipped, errors = 0, 0, []
    for rowno, row in enumerate(rows, start=2):
        vals = [row[idx[h]] if idx[h] < len(row) else None for h in HEADERS]
        if all(v is None or str(v).strip() == "" for v in vals):
            continue
        grade, name, category, location, planned_time = vals
        grade = str(grade or "").strip()
        name = str(name or "").strip()
        category = str(category or "").strip()
        location = str(location or "").strip()
        if not grade or not name:
            skipped += 1
            errors.append(f"第{rowno}行：年级和实验名称不能为空")
            continue
        if category not in CATEGORIES:
            skipped += 1
            errors.append(f"第{rowno}行：类别只能是演示或分组")
            continue
        if location not in LOCATIONS:
            skipped += 1
            errors.append(f"第{rowno}行：实验地点不在允许范围")
            continue
        db.session.add(ExperimentPlan(
            grade=grade, experiment_name=name, category=category,
            location=location, planned_time=_norm_date(planned_time),
            creator_id=g.current_user.id))
        imported += 1
    wb.close()
    db.session.commit()
    log_action("导入实验计划", f"成功{imported}条，跳过{skipped}条")
    return jsonify({"code": 0, "msg": f"导入完成：成功 {imported} 条，跳过 {skipped} 条",
                    "data": {"imported": imported, "skipped": skipped, "errors": errors}})


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
