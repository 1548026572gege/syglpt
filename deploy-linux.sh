#!/usr/bin/env bash
# 生物实验室管理平台 - CentOS / Alibaba Cloud Linux 部署脚本
# 用法：bash deploy-linux.sh
set -euo pipefail

APP_DIR=/opt/bio-lab
REPO=https://gitee.com/ylnong_0/glcs.git
PORT=8000

# 优先使用 Miniconda 自带的 Python（CentOS 7 系统 Python 缺少 ssl 模块）
if [ -x /opt/miniconda3/bin/python ]; then
  PY=/opt/miniconda3/bin/python
else
  PY=/usr/bin/python3.10
fi

echo "==> [1/7] Python 版本"
$PY --version

echo "==> [2/7] 获取代码"
if [ -d "$APP_DIR/.git" ]; then
  cd "$APP_DIR"
  git fetch origin main
  git reset --hard origin/main
else
  if [ -e "$APP_DIR" ]; then
    echo "错误：$APP_DIR 已存在但不是 Git 仓库，请先备份/移走后重试。" >&2
    exit 1
  fi
  git clone "$REPO" "$APP_DIR"
fi

echo "==> [3/7] 虚拟环境与依赖"
cd "$APP_DIR/test"
if [ ! -x venv/bin/python ] || ! venv/bin/python -c "import ssl" >/dev/null 2>&1; then
  echo "创建（或重建）虚拟环境..."
  rm -rf venv
  $PY -m venv venv
fi
venv/bin/pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ --quiet
venv/bin/pip install -r requirements.txt gunicorn -i https://mirrors.aliyun.com/pypi/simple/ --quiet
echo "依赖安装完成：$(venv/bin/python --version)"

echo "==> [4/7] 环境变量"
if [ ! -f "$APP_DIR/.env" ]; then
  ADMIN_PWD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-12)
  TEACHER_PWD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-12)
  SECRET=$(openssl rand -hex 32)
  cat > "$APP_DIR/.env" <<EOF
SECRET_KEY=$SECRET
ADMIN_INIT_PASSWORD=$ADMIN_PWD
TEACHER_INIT_PASSWORD=$TEACHER_PWD
EOF
  chmod 600 "$APP_DIR/.env"
  echo "=============================================="
  echo " 初始管理员密码：$ADMIN_PWD"
  echo " 初始教师密码：  $TEACHER_PWD"
  echo " （仅首次部署生成，请立即记录）"
  echo "=============================================="
else
  echo ".env 已存在，保留原密码配置"
fi

echo "==> [5/7] systemd 服务"
cat > /etc/systemd/system/biolab.service <<EOF
[Unit]
Description=BioLab Web Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR/test
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/test/venv/bin/gunicorn -w 3 -b 0.0.0.0:$PORT app:app --access-logfile $APP_DIR/access.log --error-logfile $APP_DIR/error.log
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable biolab >/dev/null 2>&1
systemctl restart biolab

echo "==> [6/7] 防火墙放行 $PORT"
if systemctl is-active firewalld >/dev/null 2>&1; then
  firewall-cmd --permanent --add-port=$PORT/tcp >/dev/null 2>&1 || true
  firewall-cmd --reload >/dev/null 2>&1 || true
  echo "firewalld 已放行 $PORT/tcp"
else
  echo "firewalld 未运行，跳过"
fi

echo "==> [7/7] 验证"
sleep 4
systemctl --no-pager status biolab | head -10 || true
echo "本机 HTTP 检测：$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/ || echo 失败)"

IP=$(hostname -I | awk '{print $1}')
echo ""
echo "部署完成。"
echo "  访问地址：http://$IP:$PORT/"
echo "  管理命令：systemctl {status|restart|stop} biolab"
echo "  日志文件：$APP_DIR/error.log、$APP_DIR/access.log"
