# -*- coding: utf-8 -*-
"""用户管理模块：登录、个人信息、密码、账号管理（3.1）"""
from flask import Blueprint, request, jsonify, g

from models import db, User
from auth import (hash_password, check_password, generate_token,
                  login_required, role_required, log_action)

bp = Blueprint("auth", __name__, url_prefix="/api")


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


@bp.put("/profile")
@login_required
def update_profile():
    data = request.get_json(force=True, silent=True) or {}
    u = g.current_user
    u.name = data.get("name", u.name) or u.name
    u.phone = data.get("phone", u.phone)
    if u.role == "teacher":
        u.classes = data.get("classes", u.classes)
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
    return jsonify({"code": 0, "data": [u.to_dict() for u in users]})


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
             phone=data.get("phone", ""), classes=data.get("classes", ""))
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
    u.classes = data.get("classes", u.classes)
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
    db.session.delete(u)
    db.session.commit()
    log_action("删除用户", f"账号:{u.username}")
    return jsonify({"code": 0, "msg": "删除成功"})
