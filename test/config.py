# -*- coding: utf-8 -*-
"""系统配置：默认使用 SQLite（开箱即用），部署时通过环境变量 DATABASE_URL 切换到 MySQL。

MySQL 示例：
    set DATABASE_URL=mysql+pymysql://root:password@localhost:3306/bio_lab?charset=utf8mb4
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "bio-lab-secret-key-please-change")
    # JWT 配置
    JWT_SECRET = os.environ.get("JWT_SECRET", SECRET_KEY)
    JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "12"))
    # 数据库：默认 SQLite，局域网部署时可切换 MySQL 5.7+
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "bio_lab.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 开发期模板自动重载（修改 HTML 后无需重启服务）
    TEMPLATES_AUTO_RELOAD = True
    # 上传目录（实验报告附件等）
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
