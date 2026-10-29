# -*- coding: utf-8 -*-
"""生物实验室管理平台 - Flask 应用入口。

启动：python app.py   （默认监听 0.0.0.0:8000，局域网内可通过 http://服务器IP:8000 访问）
"""
import os
from datetime import datetime

from flask import Flask, render_template, send_from_directory

from config import Config
from models import db, User
from auth import hash_password


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    # 注册 API 蓝图
    from routes.auth_routes import bp as auth_bp
    from routes.instruments import bp as instruments_bp
    from routes.reservations import bp as reservations_bp
    from routes.borrows import bp as borrows_bp
    from routes.repairs import bp as repairs_bp
    from routes.losses import bp as losses_bp
    from routes.purchases import bp as purchases_bp
    from routes.reports import bp as reports_bp
    from routes.notices import bp as notices_bp
    from routes.catalog import bp as catalog_bp
    from routes.stats import bp as stats_bp

    for bp in (auth_bp, instruments_bp, reservations_bp, borrows_bp, repairs_bp,
               losses_bp, purchases_bp, reports_bp, notices_bp, catalog_bp, stats_bp):
        app.register_blueprint(bp)

    # ---------------- 页面路由（HTML 管理后台） ----------------
    @app.route("/")
    def index():
        return render_template("login.html")

    @app.route("/page/<name>")
    def page(name):
        allowed = {"dashboard", "instruments", "reservations", "borrows", "repairs",
                   "losses", "purchases", "reports", "notices", "catalog", "users", "stats", "logs"}
        if name in allowed:
            return render_template(f"{name}.html")
        return "页面不存在", 404

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    # 初始化数据库与种子数据
    with app.app_context():
        db.create_all()
        seed_data()

    return app


def seed_data():
    """首次启动创建初始账号与示例数据"""
    if User.query.count() > 0:
        return
    admin = User(username="admin", password_hash=hash_password("admin123"),
                 role="admin", name="系统管理员", phone="13800000001")
    teacher = User(username="teacher", password_hash=hash_password("teacher123"),
                   role="teacher", name="张老师", phone="13800000002", classes="高一(1)班,高一(2)班")
    db.session.add_all([admin, teacher])
    db.session.commit()

    from models import Instrument, Notice
    samples = [
        Instrument(state_code="GZ20230001", code="SW-XSJ-001", name="生物显微镜", model="XSP-02",
                   category="光学仪器", quantity=20, price=1500, location="生物实验室A-101柜",
                   status="正常", purchase_date="2023-03-15", remark=""),
        Instrument(state_code="GZ20230002", code="SW-PYQ-001", name="恒温培养箱", model="DHP-9052",
                   category="培养设备", quantity=2, price=3800, location="生物实验室B-202",
                   status="正常", purchase_date="2023-05-20", remark=""),
        Instrument(state_code="GZ20230003", code="SW-LXJ-001", name="低速离心机", model="TD4",
                   category="分离设备", quantity=1, price=2600, location="生物实验室B-203",
                   status="维修中", purchase_date="2022-09-01", remark="转子待更换"),
        Instrument(state_code="GZ20230004", code="SW-MJ-001", name="高压灭菌锅", model="YXQ-LS-50",
                   category="灭菌设备", quantity=1, price=5600, location="准备室C-01",
                   status="正常", purchase_date="2022-11-11", remark="每年需年检"),
        Instrument(state_code="GZ20230005", code="SW-TP-001", name="电子天平", model="JA2003",
                   category="称量仪器", quantity=5, price=980, location="生物实验室A-102柜",
                   status="正常", purchase_date="2024-02-28", remark=""),
    ]
    db.session.add_all(samples)
    db.session.add(Notice(title="观察植物细胞有丝分裂实验", subject="生物学",
                          classes="高一(1)班、高一(2)班", teacher_name="张老师",
                          lab_name="生物实验室A", experiment_time="2026-10-26 10:00",
                          instruments="生物显微镜、载玻片、盖玻片、龙胆紫染液",
                          content="请各班实验小组组长提前10分钟到实验室领取实验材料，注意规范使用显微镜。",
                          sender_id=admin.id))
    db.session.commit()
    #print("[初始化] 已创建初始账号 admin/admin123、teacher/teacher123 及示例仪器数据")


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
