#!/usr/bin/env bash
# nip.io 免费 HTTPS（不买域名）
# 用法：sudo bash deploy/setup-nipio-https.sh
# 可选：NIP_HOST=47-94-238-221.nip.io AGENTFLOW_PORT=8888 sudo bash deploy/setup-nipio-https.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 root：sudo bash deploy/setup-nipio-https.sh"
  exit 1
fi

APP_ROOT="${APP_ROOT:-/opt/agentflow}"
NIP_HOST="${NIP_HOST:-47-94-238-221.nip.io}"
AGENTFLOW_PORT="${AGENTFLOW_PORT:-8888}"

cd "$APP_ROOT"

echo "==> 域名：${NIP_HOST}  →  AgentFlow :${AGENTFLOW_PORT}"

apt-get update -y
apt-get install -y certbot python3-certbot-nginx

mkdir -p /var/www/certbot

# 先生成仅 HTTP 的站点（供 certbot 申请证书）
cat >/etc/nginx/sites-available/agentflow-nipio <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${NIP_HOST};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://127.0.0.1:${AGENTFLOW_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
        proxy_buffering off;
    }
}
EOF

ln -sfn /etc/nginx/sites-available/agentflow-nipio /etc/nginx/sites-enabled/agentflow-nipio
nginx -t
systemctl reload nginx

echo "==> 申请 Let's Encrypt 证书（按提示输入邮箱，同意条款）"
certbot --nginx -d "${NIP_HOST}" --non-interactive --agree-tos --register-unsafely-without-email \
  || certbot --nginx -d "${NIP_HOST}"

# 写入完整 HTTPS 配置（certbot 通常已改好；再覆盖一份带反代参数的）
sed "s/47-94-238-221.nip.io/${NIP_HOST}/g; s/127.0.0.1:8888/127.0.0.1:${AGENTFLOW_PORT}/g" \
  deploy/nginx-nipio-https.conf >/etc/nginx/sites-available/agentflow-nipio

nginx -t
systemctl reload nginx

ufw allow 443/tcp || true

echo ""
echo "============================================"
echo " HTTPS 已配置"
echo " 访问：https://${NIP_HOST}/"
echo " 若证书申请失败，检查："
echo "  1) 安全组已放行 80、443"
echo "  2) 浏览器能打开 http://${NIP_HOST}/"
echo "  3) 再执行：certbot --nginx -d ${NIP_HOST}"
echo "============================================"
