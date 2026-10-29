# -*- coding: utf-8 -*-
"""JWT 认证与 RBAC 权限控制（设计文档第 7 章）。"""
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
import jwt
from flask import request, jsonify, current_app, g

from models import db, User, OperationLog


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def generate_token(user: User) -> str:
    payload = {
        "uid": user.id,
        "role": user.role,
        "name": user.name,
        "exp": datetime.utcnow() + timedelta(hours=current_app.config["JWT_EXPIRE_HOURS"]),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def _parse_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        payload = _parse_token()
        if not payload:
            return jsonify({"code": 401, "msg": "未登录或登录已过期"}), 401
        user = db.session.get(User, payload["uid"])
        if not user:
            return jsonify({"code": 401, "msg": "用户不存在"}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """基于角色的访问控制：限制接口仅指定角色可用"""
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if g.current_user.role not in roles:
                return jsonify({"code": 403, "msg": "无权限执行该操作"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def log_action(action: str, detail: str = ""):
    """敏感操作日志"""
    try:
        user_id = g.current_user.id if hasattr(g, "current_user") else None
        db.session.add(OperationLog(user_id=user_id, action=action, detail=detail))
        db.session.commit()
    except Exception:
        db.session.rollback()
