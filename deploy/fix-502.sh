#!/usr/bin/env bash
# 修复 502：权限 + 确认 Python3.11 venv + 重启 API
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/agentflow}"
cd "$APP_ROOT"

echo "==> 检查 Python 3.11 venv"
if [[ ! -x .venv/bin/python ]]; then
  echo "未找到 .venv，正在创建…"
  python3.11 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -U pip
  pip install -e "./backend[web]"
else
  PY_VER="$(.venv/bin/python -V 2>&1 || true)"
  echo "$PY_VER"
  if ! .venv/bin/python -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null; then
    echo "venv 不是 3.11，重建…"
    rm -rf .venv
    python3.11 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install -U pip
    pip install -e "./backend[web]"
  fi
fi

# FastAPI 表单/上传依赖（缺了会 502）
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q 'python-multipart>=0.0.9'
pip install -q -e "./backend[web]"

echo "==> 修复目录权限"
mkdir -p backend/data backend/.mawp
chown -R www-data:www-data backend/data backend/.mawp 2>/dev/null || true
chmod -R u+rwX,g+rwX backend/data backend/.mawp 2>/dev/null || true
chown -R root:www-data "$APP_ROOT"
chmod -R g+rX "$APP_ROOT"
chmod -R g+w backend/data backend/.mawp 2>/dev/null || true
chmod 640 backend/.env 2>/dev/null || true
chmod 750 .venv/bin 2>/dev/null || true
find .venv/bin -type f -exec chmod 750 {} \; 2>/dev/null || true

echo "==> 测试 www-data 能否启动模块"
if ! sudo -u www-data env PYTHONPATH="$APP_ROOT/backend/src" \
  "$APP_ROOT/.venv/bin/python" -c "from mawp.api.platform import create_app; create_app()" 2>/tmp/agentflow-import.err; then
  echo "导入失败，错误如下："
  cat /tmp/agentflow-import.err
  exit 1
fi
echo "模块导入 OK"

echo "==> 重启 agentflow-api"
systemctl daemon-reload
systemctl restart agentflow-api
sleep 2
systemctl status agentflow-api --no-pager || true

echo "==> 健康检查"
if curl -sf http://127.0.0.1:8787/api/health; then
  echo ""
  echo "API 正常。请刷新浏览器：http://$(curl -s ifconfig.me 2>/dev/null || echo '<公网IP>'):8888/"
else
  echo "仍无法访问 8787，最近日志："
  journalctl -u agentflow-api -n 40 --no-pager
  exit 1
fi
