#!/usr/bin/env bash
# 智流 AgentFlow — Ubuntu 22.04 / 24.04 一键安装（阿里云 2C8G）
# 用法（在服务器上）：
#   sudo bash deploy/setup-ubuntu.sh
# 或先把代码放到 /opt/agentflow 再执行。
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/agentflow}"
REPO_URL="${REPO_URL:-}"
NODE_MAJOR="${NODE_MAJOR:-20}"
# 默认 8080：同机若下午已有项目占了 80，互不抢占。独占整机时可 HTTP_PORT=80
HTTP_PORT="${HTTP_PORT:-8080}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 root 执行：sudo bash deploy/setup-ubuntu.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl git nginx build-essential ca-certificates gnupg ufw \
  software-properties-common

# 项目要求 Python >=3.11（Ubuntu 22.04 默认 3.10，需单独装）
if ! command -v python3.11 >/dev/null 2>&1; then
  add-apt-repository -y ppa:deadsnakes/ppa || true
  apt-get update -y
  apt-get install -y python3.11 python3.11-venv python3.11-dev
fi
apt-get install -y python3-pip

# Node 20
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | sed 's/v//' | cut -d. -f1)" -lt "$NODE_MAJOR" ]]; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y nodejs
fi

mkdir -p "$APP_ROOT"
if [[ -n "$REPO_URL" && ! -d "$APP_ROOT/.git" ]]; then
  git clone "$REPO_URL" "$APP_ROOT"
fi

if [[ ! -f "$APP_ROOT/package.json" ]]; then
  echo "未找到 $APP_ROOT/package.json。请先把项目上传到 $APP_ROOT，或设置 REPO_URL=你的仓库地址"
  exit 1
fi

cd "$APP_ROOT"

# Python 3.11 venv + 后端
rm -rf .venv
python3.11 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -e "./backend[web]"

# 前端构建（密钥只用于构建期占位；真实代理密钥在 nginx snippet）
if [[ ! -f .env ]]; then
  echo "提示：根目录可放 .env（DEEPSEEK_API_KEY 等），构建时 Vite 会读取；生产代理密钥以 backend/.env 为准"
fi
npm install
npm run build

# backend/.env
if [[ ! -f backend/.env ]]; then
  if [[ -f backend/.env.example ]]; then
    cp backend/.env.example backend/.env
    echo "已生成 backend/.env，请编辑填入密钥后重新执行或手动 systemctl restart agentflow-api"
  else
    touch backend/.env
  fi
fi

# 从 backend/.env 安全提取密钥（避免 source 特殊字符炸掉）
extract_env() {
  local key="$1"
  local file="$APP_ROOT/backend/.env"
  [[ -f "$file" ]] || return 0
  local line
  line="$(grep -E "^${key}=" "$file" | tail -n1 | sed 's/\r$//' || true)"
  [[ -n "$line" ]] || return 0
  printf '%s' "${line#*=}" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

mkdir -p /etc/nginx/snippets
DS_KEY="$(extract_env DEEPSEEK_API_KEY || true)"
BOCHA_KEY="$(extract_env BOCHA_API_KEY || true)"
POL_KEY="$(extract_env POLLINATIONS_API_KEY || true)"
[[ -z "$POL_KEY" ]] && POL_KEY="$(extract_env VITE_POLLINATIONS_KEY || true)"

if [[ -n "$DS_KEY" ]]; then
  printf 'proxy_set_header Authorization "Bearer %s";\n' "$DS_KEY" \
    >/etc/nginx/snippets/agentflow-secrets-deepseek.conf
else
  echo '# no DEEPSEEK_API_KEY' >/etc/nginx/snippets/agentflow-secrets-deepseek.conf
fi

if [[ -n "$BOCHA_KEY" ]]; then
  printf 'proxy_set_header Authorization "Bearer %s";\n' "$BOCHA_KEY" \
    >/etc/nginx/snippets/agentflow-secrets-bocha.conf
else
  echo '# no BOCHA_API_KEY' >/etc/nginx/snippets/agentflow-secrets-bocha.conf
fi

if [[ -n "$POL_KEY" ]]; then
  printf 'proxy_set_header Authorization "Bearer %s";\n' "$POL_KEY" \
    >/etc/nginx/snippets/agentflow-secrets-pollinations.conf
else
  echo '# no POLLINATIONS_API_KEY' >/etc/nginx/snippets/agentflow-secrets-pollinations.conf
fi
chmod 640 /etc/nginx/snippets/agentflow-secrets-*.conf
chown root:www-data /etc/nginx/snippets/agentflow-secrets-*.conf

# 确保生产监听本机（nginx 反代）
grep -q '^MAWP_HOST=' backend/.env 2>/dev/null || echo 'MAWP_HOST=127.0.0.1' >> backend/.env
grep -q '^MAWP_PORT=' backend/.env 2>/dev/null || echo 'MAWP_PORT=8787' >> backend/.env
grep -q '^AUTH_DEV_MODE=' backend/.env && sed -i 's/^AUTH_DEV_MODE=.*/AUTH_DEV_MODE=0/' backend/.env \
  || echo 'AUTH_DEV_MODE=0' >> backend/.env

# 权限：www-data 跑 API，需读 .venv、写 backend/data、读 backend/.env
mkdir -p backend/data backend/.mawp
chown -R www-data:www-data backend/data backend/.mawp 2>/dev/null || true
chmod -R u+rwX,g+rwX backend/data backend/.mawp 2>/dev/null || true
# .venv 与源码：组内可读可执行（勿 chown -R root 覆盖整个目录）
chown -R root:www-data "$APP_ROOT"
chmod -R g+rX "$APP_ROOT"
chmod -R g+w backend/data backend/.mawp 2>/dev/null || true
chmod 640 backend/.env 2>/dev/null || true
chmod 750 "$APP_ROOT/.venv/bin" 2>/dev/null || true
find "$APP_ROOT/.venv/bin" -type f -exec chmod 750 {} \; 2>/dev/null || true

# systemd
cp deploy/agentflow-api.service /etc/systemd/system/agentflow-api.service
systemctl daemon-reload
systemctl enable --now agentflow-api

# nginx（改监听端口；不删已有 default/其它站点，避免挤掉下午那个项目）
sed "s/listen 8080;/listen ${HTTP_PORT};/g; s/listen \\[::\\]:8080;/listen [::]:${HTTP_PORT};/g" \
  deploy/nginx.conf >/etc/nginx/sites-available/agentflow
ln -sfn /etc/nginx/sites-available/agentflow /etc/nginx/sites-enabled/agentflow
nginx -t
systemctl enable --now nginx
systemctl reload nginx

# 防火墙（阿里云安全组也要放行 HTTP_PORT）
ufw allow OpenSSH || true
ufw allow "${HTTP_PORT}/tcp" || true
ufw allow 443/tcp || true
ufw --force enable || true

PUB_IP="$(curl -s ifconfig.me 2>/dev/null || echo '<公网IP>')"
echo ""
echo "============================================"
echo " 安装完成（HTTP 端口 ${HTTP_PORT}）"
echo " 访问：http://${PUB_IP}:${HTTP_PORT}/"
echo " 检查：systemctl status agentflow-api nginx"
echo " 日志：journalctl -u agentflow-api -f"
echo " 安全组请放行：${HTTP_PORT}"
echo " 请确认 backend/.env 已填 DEEPSEEK_API_KEY / SMTP_* 等"
echo "============================================"
