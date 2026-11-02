# -*- coding: utf-8 -*-
"""实验通知单模块（3.9）：管理员编辑发送、教师接收查看，支持导出与打印数据"""
import io
import re

from flask import Blueprint, request, jsonify, g, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.worksheet.pagebreak import Break

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


# ---------------- 导出（按《实验通知单》模板排版：一张 A4 上下两联） ----------------

FONT_NAME = "宋体"
THIN = Side(style="thin", color="000000")
CELL_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CELL_FONT = Font(name=FONT_NAME, size=11, bold=True)
TITLE_FONT = Font(name=FONT_NAME, size=18, bold=True)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

# 模板列宽 A-G，单位：字符
COL_WIDTHS = {"A": 11, "B": 12.5, "C": 20.4, "D": 9, "E": 11, "F": 5.2, "G": 23.2}


def grade_of(classes):
    """从班级串中提取年级，如「初一(1)班、初一(2)班」→「初一」"""
    m = re.search(r"(高[一二三](?:年级)?|初[一二三](?:年级)?|[七八九]年级)", classes or "")
    return m.group(1) if m else ""


def date_text(value):
    """「2026-11-02 14:30」→「2026 年 11 月 2 日 14:30」"""
    v = (value or "").strip().replace("T", " ")
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ ]+(\d{1,2}:\d{2}))?", v)
    if not m:
        return v
    y, mo, d, hm = m.groups()
    s = f"{y} 年 {int(mo)} 月 {int(d)} 日"
    return f"{s} {hm}" if hm else s


def _fill_form(ws, row, n, last_height):
    """按模板写一联：标题 / 学科·年级·班级 / 实验时间·任课教师 / 实验名称 / 实验仪器、用品"""
    for offset, height in ((0, 48.8), (1, 45), (2, 45), (3, 45), (4, last_height)):
        ws.row_dimensions[row + offset].height = height

    ws.cell(row, 1, "实   验   通   知   单").font = TITLE_FONT
    ws.cell(row, 1).alignment = CENTER
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)

    values = {
        (1, 1): "学科", (1, 2): n.subject or "", (1, 3): "演示",
        (1, 4): "实验年级", (1, 5): grade_of(n.classes),
        (1, 6): "班级", (1, 7): n.classes or "",
        (2, 1): "实验时间", (2, 2): date_text(n.experiment_time),
        (2, 4): "任课教师", (2, 5): n.teacher_name or "",
        (3, 1): "实验名称", (3, 2): n.title or "",
        (4, 1): "实验仪器、用品", (4, 2): n.instruments or "",
    }
    for dr in range(1, 5):
        for col in range(1, 8):
            c = ws.cell(row + dr, col)
            c.font = CELL_FONT
            c.alignment = CENTER
            c.border = CELL_BORDER
    for (dr, col), v in values.items():
        ws.cell(row + dr, col, v)

    ws.merge_cells(start_row=row + 2, start_column=2, end_row=row + 2, end_column=3)
    ws.merge_cells(start_row=row + 2, start_column=5, end_row=row + 2, end_column=7)
    ws.merge_cells(start_row=row + 3, start_column=2, end_row=row + 3, end_column=7)
    ws.merge_cells(start_row=row + 4, start_column=2, end_row=row + 4, end_column=7)


@bp.get("/export")
@login_required
def export_notices():
    items = Notice.query.order_by(Notice.id.desc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "实验通知单"
    for col, width in COL_WIDTHS.items():
        ws.column_dimensions[col].width = width
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = 9  # A4
    ws.page_margins.left, ws.page_margins.right = 0.71, 0.41
    ws.page_margins.top, ws.page_margins.bottom = 0.75, 0.75

    row = 1
    for n in items:
        _fill_form(ws, row, n, 113.2)          # 第一联
        ws.row_dimensions[row + 10].height = 21.8
        _fill_form(ws, row + 11, n, 121.5)     # 第二联（存根/通知）
        ws.row_breaks.append(Break(id=row + 16))
        row += 17

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    log_action("导出实验通知单", f"共{len(items)}条")
    return send_file(buf, as_attachment=True, download_name="实验通知单.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
