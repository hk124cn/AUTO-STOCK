#!/bin/bash
# 启动财报评分系统所有服务

echo "🚀 启动财报评分系统..."

# 切换到项目目录
cd /home/admin/AUTO-STOCK

# 1. 启动后端 API (gunicorn)
echo "📡 启动后端 API..."
# 先等待旧进程完全退出
for i in {1..5}; do
    pkill -f "gunicorn.*api.main:app" 2>/dev/null
    sleep 1
    if ! pgrep -f "gunicorn.*api.main:app" > /dev/null 2>&1; then
        echo "  ✓ 旧进程已退出"
        break
    fi
    echo "  等待旧进程退出... ($i/5)"
done
sleep 1
nohup python3 -m gunicorn -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 api.main:app > /tmp/gunicorn.log 2>&1 &

# 2. 启动前端 Vite
echo "🌐 启动前端..."
cd /home/admin/AUTO-STOCK/web
pkill -f "node.*vite.*port 3000" 2>/dev/null
sleep 1
nohup node node_modules/.bin/vite --host 0.0.0.0 --port 3000 > /tmp/vite.log 2>&1 &

# 3. 恢复 Nginx 配置
echo "⚙️  恢复 Nginx 配置..."
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

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

sudo nginx -t && sudo nginx -s reload

sleep 2

# 检查状态
echo ""
echo "✅ 启动完成！"
echo "   前端: https://auto-claw.top"
echo "   后端: http://localhost:8000"

# 查看进程
echo ""
echo "📊 进程状态:"
ps aux | grep -E "gunicorn.*api.main|vite.*port 3000" | grep -v grep | awk '{print "   ", $2, $11, $12, $13}'