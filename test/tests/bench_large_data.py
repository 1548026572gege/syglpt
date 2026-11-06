# -*- coding: utf-8 -*-
"""大数据量性能测试（P3）：1 万条仪器 + 1 万条预约下的列表、导出、统计耗时。

运行：
    python test/tests/bench_large_data.py
默认使用临时 SQLite，不影响已有数据；任一指标超过阈值时退出码为 1。
"""
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta

TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = tempfile.mkdtemp(prefix="bio_bench_")

os.environ.update({
    "DATABASE_URL": "sqlite:///" + os.path.join(TMP_DIR, "bench.db"),
    "SECRET_KEY": "bench-secret-key-0123456789abcdefg",
    "JWT_SECRET": "bench-jwt-key-0123456789abcdefghij",
    "ADMIN_INIT_PASSWORD": "Admin123456",
    "TEACHER_INIT_PASSWORD": "Teach123456",
})
sys.path.insert(0, TEST_DIR)

from app import app  # noqa: E402
from models import db, Instrument, Reservation, User  # noqa: E402

INSTRUMENT_COUNT = 10000
RESERVATION_COUNT = 10000
CHUNK = 1000

# 指标名称 -> 允许的最大耗时（秒）
THRESHOLDS = {
    "仪器列表（全量）": 6.0,
    "仪器列表（关键字）": 6.0,
    "仪器台账导出": 25.0,
    "预约列表（全量）": 6.0,
    "统计报表汇总": 6.0,
    "统计分类导出": 15.0,
}

client = app.test_client()
TOKEN = None


def headers():
    return {"Authorization": "Bearer " + TOKEN}


def timed(label, fn):
    start = time.perf_counter()
    resp = fn()
    cost = time.perf_counter() - start
    ok = resp.status_code == 200
    print(f"  {label:<22} {cost:6.3f}s   HTTP {resp.status_code}")
    return label, cost, ok


def seed():
    """批量写入 1 万条仪器与 1 万条预约"""
    with app.app_context():
        teacher = User.query.filter_by(username="teacher").first()
        for base in range(0, INSTRUMENT_COUNT, CHUNK):
            batch = [Instrument(
                state_code=f"GZ{base + i:08d}", subject="生物" if i % 2 == 0 else "化学",
                code=f"BENCH-{base + i:05d}", category_code=f"C{(base + i) % 100:03d}",
                name=f"性能测试仪器{base + i}", spec="标准", unit="台",
                category="光学仪器" if i % 3 == 0 else "培养设备",
                quantity=(base + i) % 30 + 1, price=100 + i % 50,
                location="性能测试库位", status="正常")
                for i in range(min(CHUNK, INSTRUMENT_COUNT - base))]
            db.session.bulk_save_objects(batch)
            db.session.commit()
        start = datetime.now() + timedelta(days=1)
        for base in range(0, RESERVATION_COUNT, CHUNK):
            batch = [Reservation(
                teacher_id=teacher.id, lab_name=f"实验室{base % 5}",
                experiment_name=f"性能测试预约{base + i}", class_name="高一(1)班",
                student_count=40, group_count=10,
                start_time=start + timedelta(hours=(base + i) % 24),
                end_time=start + timedelta(hours=(base + i) % 24 + 2),
                status="已通过")
                for i in range(min(CHUNK, RESERVATION_COUNT - base))]
            db.session.bulk_save_objects(batch)
            db.session.commit()


def main():
    global TOKEN
    print(f"写入测试数据：仪器 {INSTRUMENT_COUNT} 条、预约 {RESERVATION_COUNT} 条 …")
    seed_time_start = time.perf_counter()
    seed()
    seed_cost = time.perf_counter() - seed_time_start
    print(f"  数据准备耗时 {seed_cost:.2f}s\n")

    TOKEN = client.post("/api/login", json={"username": "admin", "password": "Admin123456"}) \
        .get_json()["data"]["token"]

    rows = [
        timed("仪器列表（全量）", lambda: client.get("/api/instruments", headers=headers())),
        timed("仪器列表（关键字）", lambda: client.get("/api/instruments?kw=性能测试仪器999", headers=headers())),
        timed("仪器台账导出", lambda: client.get("/api/instruments/export", headers=headers())),
        timed("预约列表（全量）", lambda: client.get("/api/reservations", headers=headers())),
        timed("统计报表汇总", lambda: client.get("/api/stats/report", headers=headers())),
        timed("统计分类导出", lambda: client.get("/api/stats/export?type=instrument_category",
                                                  headers=headers())),
    ]

    print("\n阈值检查：")
    failed = []
    for label, cost, ok in rows:
        limit = THRESHOLDS[label]
        if not ok:
            failed.append(f"{label}：接口返回非 200")
        elif cost > limit:
            failed.append(f"{label}：{cost:.2f}s 超过阈值 {limit:.1f}s")
    if failed:
        for item in failed:
            print("  [FAIL] " + item)
    else:
        print("  全部指标在阈值内")

    with app.app_context():
        db.session.execute(db.text("PRAGMA wal_checkpoint(TRUNCATE)"))
        db.session.commit()
        size_mb = os.path.getsize(os.path.join(TMP_DIR, "bench.db")) / 1024 / 1024
    print(f"\n数据库大小（checkpoint 后）：{size_mb:.1f} MB")
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
