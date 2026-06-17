#!/bin/bash
# 停止财报评分系统，进入维护模式

echo "🛑 停止财报评分系统..."

API_SERVICE="${API_SERVICE:-stock-api}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# 1. 停止后端 API（systemd service；需与 start_financial_score.sh 的 API_SERVICE 保持一致）
echo "📡 停止后端 API (${API_SERVICE})..."
sudo systemctl stop "${API_SERVICE}"

# 2. 停止前端 (只停指定端口的 vite)
echo "🌐 停止前端..."
pkill -f "node.*vite.*port ${FRONTEND_PORT}" 2>/dev/null

# 3. 修改 Nginx 配置直接返回维护页面
echo "⚙️  切换到维护页面..."

# 写入维护模式配置
sudo tee /etc/nginx/conf.d/auto-claw.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name auto-claw.top www.auto-claw.top;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name auto-claw.top www.auto-claw.top;

    ssl_certificate /ssl/cert.pem;
    ssl_certificate_key /ssl/cert.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    root /home/admin/AUTO-STOCK/web;
    index maintenance.html;

    location / {
        try_files /maintenance.html =404;
    }

    location /api/ {
        return 503;
    }
}
EOF

sudo nginx -t && sudo nginx -s reload

sleep 1

echo ""
echo "✅ 已进入维护模式，访问 https://auto-claw.top 将显示维护页面"
echo "   释放内存: ${API_SERVICE} + vite ≈ 300-500MB"
echo ""
echo "恢复服务命令: bash /home/admin/AUTO-STOCK/scripts/start_financial_score.sh"