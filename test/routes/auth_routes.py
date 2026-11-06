# -*- coding: utf-8 -*-
"""用户管理模块：登录、个人信息、密码、账号管理（3.1）"""
import re
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g

from models import db, User, SchoolClass
from auth import (hash_password, check_password, generate_token,
                  login_required, role_required, log_action)

bp = Blueprint("auth", __name__, url_prefix="/api")

# 内置账号：不允许删除，避免系统失去管理员
PROTECTED_USERNAMES = {"admin"}

# 最后活跃时间在此范围内的账号视为在线（前端每分钟心跳）
ONLINE_WINDOW = timedelta(minutes=3)

# 任教班级分隔符：兼容历史数据的逗号、顿号与中文逗号
CLASS_SEPARATORS = re.compile(r"[,，、]")


def _split_classes(raw):
    """把逗号/顿号分隔的班级字符串拆成去重列表"""
    names = []
    for item in CLASS_SEPARATORS.split(raw or ""):
        item = item.strip()
        if item and item not in names:
            names.append(item)
    return names


def _normalize_classes(raw):
    """把请求中的班级数组规范化为去重列表；格式非法时返回 None"""
    if raw is None:
        return []
    if isinstance(raw, str):
        return _split_classes(raw)
    if not isinstance(raw, list):
        return None
    names = []
    for item in raw:
        name = str(item).strip()
        if not name or name in names:
            continue
        if len(name) > 20 or CLASS_SEPARATORS.search(name) or "\n" in name:
            return None
        names.append(name)
    return names


def _class_pool_names():
    return [c.name for c in SchoolClass.query.order_by(SchoolClass.sort_order, SchoolClass.id).all()]


@bp.post("/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = User.query.filter_by(username=username).first()
    if not user or not check_password(password, user.password_hash):
        return jsonify({"code": 400, "msg": "用户名或密码错误"}), 400
    return jsonify({"code": 0, "msg": "登录成功",
                    "data": {"token": generate_token(user), "user": user.to_dict()}})


@bp.get("/profile")
@login_required
def profile():
    return jsonify({"code": 0, "data": g.current_user.to_dict()})


@bp.post("/heartbeat")
@login_required
def heartbeat():
    """前端定时心跳；login_required 已刷新最后活跃时间"""
    return jsonify({"code": 0})


@bp.put("/profile")
@login_required
def update_profile():
    data = request.get_json(force=True, silent=True) or {}
    u = g.current_user
    u.name = data.get("name", u.name) or u.name
    u.phone = data.get("phone", u.phone)
    db.session.commit()
    return jsonify({"code": 0, "msg": "保存成功", "data": u.to_dict()})


@bp.put("/password")
@login_required
def change_password():
    data = request.get_json(force=True, silent=True) or {}
    old, new = data.get("old_password", ""), data.get("new_password", "")
    if len(new) < 6:
        return jsonify({"code": 400, "msg": "新密码长度至少6位"}), 400
    if not check_password(old, g.current_user.password_hash):
        return jsonify({"code": 400, "msg": "原密码错误"}), 400
    g.current_user.password_hash = hash_password(new)
    db.session.commit()
    return jsonify({"code": 0, "msg": "密码修改成功"})


# ---------------- 账号管理（管理员） ----------------

@bp.get("/users")
@role_required("admin", "sysadmin")
def list_users():
    kw = request.args.get("kw", "").strip()
    q = User.query
    if kw:
        q = q.filter(db.or_(User.username.contains(kw), User.name.contains(kw)))
    users = q.order_by(User.id).all()
    now = datetime.now()
    data = []
    for u in users:
        item = u.to_dict()
        item["online"] = bool(u.last_active_at and (now - u.last_active_at) <= ONLINE_WINDOW)
        data.append(item)
    return jsonify({"code": 0, "data": data})


@bp.post("/users")
@role_required("admin", "sysadmin")
def create_user():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username or not data.get("name") or not data.get("password"):
        return jsonify({"code": 400, "msg": "用户名、姓名、密码不能为空"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"code": 400, "msg": "用户名已存在"}), 400
    u = User(username=username, name=data["name"],
             password_hash=hash_password(data["password"]),
             role=data.get("role", "teacher"),
             phone=data.get("phone", ""))
    db.session.add(u)
    db.session.commit()
    log_action("新增用户", f"账号:{username} 角色:{u.role}")
    return jsonify({"code": 0, "msg": "创建成功", "data": u.to_dict()})


@bp.put("/users/<int:uid>")
@role_required("admin", "sysadmin")
def update_user(uid):
    u = db.session.get(User, uid)
    if not u:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404
    data = request.get_json(force=True, silent=True) or {}
    u.name = data.get("name", u.name)
    u.role = data.get("role", u.role)
    u.phone = data.get("phone", u.phone)
    if u.role != "teacher":
        u.classes = ""
    if data.get("password"):
        u.password_hash = hash_password(data["password"])
    db.session.commit()
    log_action("修改用户", f"账号:{u.username}")
    return jsonify({"code": 0, "msg": "保存成功", "data": u.to_dict()})


@bp.delete("/users/<int:uid>")
@role_required("admin", "sysadmin")
def delete_user(uid):
    if uid == g.current_user.id:
        return jsonify({"code": 400, "msg": "不能删除当前登录账号"}), 400
    u = db.session.get(User, uid)
    if not u:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404
    if u.username in PROTECTED_USERNAMES:
        return jsonify({"code": 400, "msg": "内置管理员账号 admin 不能删除"}), 400
    db.session.delete(u)
    db.session.commit()
    log_action("删除用户", f"账号:{u.username}")
    return jsonify({"code": 0, "msg": "删除成功"})


# ---------------- 班级库与教师绑定（管理员） ----------------

@bp.get("/classes")
@login_required
def list_classes():
    return jsonify({"code": 0, "data": _class_pool_names()})


@bp.put("/classes")
@role_required("admin", "sysadmin")
def update_classes():
    """整体更新班级库（建议每两年手动维护一次）；已移除的班级会同步从教师解绑"""
    data = request.get_json(force=True, silent=True) or {}
    names = _normalize_classes(data.get("classes"))
    if not names:
        return jsonify({"code": 400, "msg": "班级库不能为空"}), 400

    old_names = set(_class_pool_names())
    removed = old_names - set(names)
    unbound = 0
    if removed:
        for u in User.query.filter(User.classes.isnot(None)).all():
            kept = [c for c in _split_classes(u.classes) if c not in removed]
            if kept != _split_classes(u.classes):
                u.classes = ",".join(kept)
                unbound += 1

    SchoolClass.query.delete()
    for i, name in enumerate(names):
        db.session.add(SchoolClass(name=name, sort_order=i))
    db.session.commit()
    log_action("更新班级库", f"共 {len(names)} 个班级，自动解绑 {unbound} 位教师")
    return jsonify({"code": 0, "msg": "班级库已更新",
                    "data": {"count": len(names), "unbound": unbound}})


@bp.put("/users/<int:uid>/classes")
@role_required("admin", "sysadmin")
def set_user_classes(uid):
    """绑定/解绑教师任教班级（传入完整班级列表）"""
    u = db.session.get(User, uid)
    if not u:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404
    if u.role != "teacher":
        return jsonify({"code": 400, "msg": "只能为生物教师绑定班级"}), 400

    data = request.get_json(force=True, silent=True) or {}
    names = _normalize_classes(data.get("classes"))
    if names is None:
        return jsonify({"code": 400, "msg": "班级格式不正确"}), 400
    pool = set(_class_pool_names())
    invalid = [n for n in names if n not in pool]
    if invalid:
        return jsonify({"code": 400, "msg": "班级不在班级库中：" + "、".join(invalid)}), 400

    old_names = _split_classes(u.classes)
    u.classes = ",".join(names)
    db.session.commit()

    added = [n for n in names if n not in old_names]
    removed = [n for n in old_names if n not in names]
    detail = f"教师:{u.name}"
    if added:
        detail += " 绑定:" + "、".join(added)
    if removed:
        detail += " 解绑:" + "、".join(removed)
    log_action("调整任教班级", detail)
    return jsonify({"code": 0, "msg": "保存成功", "data": u.to_dict()})
