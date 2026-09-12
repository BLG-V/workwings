#!/usr/bin/env bash
# 更新代码后：重建前端、刷新密钥片段、重启服务
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/agentflow}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 root 执行：sudo bash deploy/update.sh"
  exit 1
fi

cd "$APP_ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -e "./backend[web]"
npm install
npm run build

# 刷新 nginx 密钥片段
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

HTTP_PORT="${HTTP_PORT:-8080}"
# 若已安装过，尽量从现有站点读出 listen 端口
if [[ -f /etc/nginx/sites-available/agentflow ]]; then
  DETECTED="$(grep -oE 'listen [[:digit:]]+;' /etc/nginx/sites-available/agentflow | head -1 | grep -oE '[[:digit:]]+' || true)"
  [[ -n "$DETECTED" ]] && HTTP_PORT="$DETECTED"
fi
sed "s/listen 8080;/listen ${HTTP_PORT};/g; s/listen \\[::\\]:8080;/listen [::]:${HTTP_PORT};/g" \
  deploy/nginx.conf >/etc/nginx/sites-available/agentflow
nginx -t
systemctl reload nginx
systemctl restart agentflow-api

echo "更新完成：http://$(curl -s ifconfig.me 2>/dev/null || echo '<公网IP>'):${HTTP_PORT}/"
