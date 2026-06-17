#!/bin/bash
# 启动财报评分系统所有服务

echo "🚀 启动财报评分系统..."

API_SERVICE="${API_SERVICE:-stock-api}"
FRONTEND_DIR="${FRONTEND_DIR:-/home/admin/AUTO-STOCK/web/financial-report}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# 切换到项目目录
cd /home/admin/AUTO-STOCK

# 1. 启动后端 API（systemd 单 worker；不同功能可通过 API_SERVICE 指向各自 service）
echo "📡 启动后端 API (${API_SERVICE})..."
sudo systemctl restart "${API_SERVICE}"

# 2. 启动前端 Vite
echo "🌐 启动前端..."
cd "${FRONTEND_DIR}"
pkill -f "node.*vite.*port ${FRONTEND_PORT}" 2>/dev/null
sleep 1
nohup node node_modules/.bin/vite --host 0.0.0.0 --port "${FRONTEND_PORT}" > /tmp/vite.log 2>&1 &

# 3. 检查 Nginx 配置（不覆盖，使用 auto-claw.top.conf 的静态文件配置）
echo "⚙️  检查 Nginx 配置..."
# 删除可能残留的代理配置
sudo rm -f /etc/nginx/conf.d/auto-claw.conf
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
ps aux | grep -E "uvicorn api.main:app|vite.*port ${FRONTEND_PORT}" | grep -v grep | awk '{print "   ", $2, $11, $12, $13}'