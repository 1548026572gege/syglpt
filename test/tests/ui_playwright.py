# -*- coding: utf-8 -*-
"""浏览器端 UI 回归（P3）：Playwright + 本地临时实例，覆盖登录、导航、页面渲染与导出。

前置：
    pip install playwright
    python -m playwright install chromium
运行：
    python test/tests/ui_playwright.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = tempfile.mkdtemp(prefix="bio_ui_")
PORT = 8011
BASE = f"http://127.0.0.1:{PORT}"

ENV = dict(os.environ)
ENV.update({
    "DATABASE_URL": "sqlite:///" + os.path.join(TMP_DIR, "ui.db"),
    "SECRET_KEY": "ui-secret-key-0123456789abcdefghi",
    "JWT_SECRET": "ui-jwt-key-0123456789abcdefghijkl",
    "ADMIN_INIT_PASSWORD": "Admin123456",
    "TEACHER_INIT_PASSWORD": "Teach123456",
})

PASSED = 0
FAILED = []


def check(name, cond, detail=""):
    global PASSED
    if cond:
        PASSED += 1
        print(f"  [PASS] {name}")
    else:
        FAILED.append(name + (f"（{detail}）" if detail else ""))
        print(f"  [FAIL] {name} {detail}")


def wait_server(timeout=30):
    """等待本地实例可访问"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def run(page, download_expected=False):
    """执行 UI 用例"""
    # 1. 登录页
    page.goto(BASE + "/")
    check("登录页标题正确", "登录" in page.title())
    check("登录表单可见", page.locator("#login-username").is_visible() and
          page.locator("#login-password").is_visible())

    # 2. 错误密码提示
    page.fill("#login-username", "admin")
    page.fill("#login-password", "wrong-password")
    page.click("#login-btn")
    page.wait_for_selector(".toast.error", timeout=5000)
    check("错误密码弹出错误提示", page.locator(".toast.error").first.inner_text() != "")
    check("错误密码不跳转", page.url.rstrip("/") == BASE)

    # 3. 正确登录进入工作台
    page.fill("#login-username", "admin")
    page.fill("#login-password", "Admin123456")
    page.click("#login-btn")
    page.wait_for_url("**/page/dashboard", timeout=10000)
    page.wait_for_selector("#stat-grid .stat-card", timeout=10000)
    check("登录后进入工作台", "/page/dashboard" in page.url)
    check("工作台统计卡片 8 个", page.locator("#stat-grid .stat-card").count() == 8)
    check("顶部显示当前用户", page.locator("#top-user-name").inner_text().strip() == "系统管理员")
    check("侧边栏导航渲染", page.locator("#nav .nav-item").count() >= 10)

    # 4. 导航到仪器台账并加载数据
    page.click("#nav .nav-item[href='/page/instruments']")
    page.wait_for_url("**/page/instruments", timeout=10000)
    page.wait_for_selector(".data-table tbody tr", timeout=10000)
    check("仪器台账页面有数据行", page.locator(".data-table tbody tr").count() >= 5)

    # 5. 统计报表页：筛选栏与图表
    page.click("#nav .nav-item[href='/page/stats']")
    page.wait_for_url("**/page/stats", timeout=10000)
    page.wait_for_selector("#c-ins-status .bar-row", timeout=10000)
    check("统计页渲染图表", page.locator("#c-ins-status .bar-row").count() > 0)
    check("导出筛选栏可见", page.locator("#exp-start").is_visible() and
          page.locator("#exp-subject").is_visible())

    # 6. 导出下载（分类导出 + 日期筛选）
    page.fill("#exp-start", "2000-01-01")
    page.fill("#exp-end", "2099-12-31")
    with page.expect_download(timeout=15000) as dl:
        page.locator(".chart-box", has_text="仪器状态分布").locator("button").click()
    download = dl.value
    check("分类导出触发下载", download.suggested_filename.endswith(".xlsx"),
          download.suggested_filename)

    # 7. 退出登录回到登录页
    page.click("button:has-text('退出')")
    page.wait_for_url(BASE + "/", timeout=10000)
    check("退出后返回登录页", page.url.rstrip("/") == BASE)
    check("退出后 Token 已清除", page.evaluate("localStorage.getItem('bio_lab_token')") is None)


def main():
    proc = subprocess.Popen(
        [sys.executable, "-c", "from app import app; app.run(host='127.0.0.1', port=%d)" % PORT],
        cwd=TEST_DIR, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_server():
            print("本地实例启动失败")
            return 1
        print(f"本地实例已启动：{BASE}")
        from playwright.sync_api import sync_playwright

        console_errors = []
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.on("pageerror", lambda e: console_errors.append(str(e)))
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            try:
                run(page)
            finally:
                browser.close()

        # 忽略 favicon 资源噪音与「错误密码登录」用例产生的预期 400
        ignored = ("favicon", "400 (bad request)")
        real_errors = [e for e in console_errors if not any(k in e.lower() for k in ignored)]
        check("页面无 JavaScript 错误", not real_errors, "；".join(real_errors[:3]))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    print("=" * 60)
    print(f"通过 {PASSED} 项，失败 {len(FAILED)} 项")
    for item in FAILED:
        print("  [FAIL] " + item)
    print("=" * 60)
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
