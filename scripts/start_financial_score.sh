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
cd /home/admin/AUTO-STOCK/web/financial-report
pkill -f "node.*vite.*port 3000" 2>/dev/null
sleep 1
nohup node node_modules/.bin/vite --host 0.0.0.0 --port 3000 > /tmp/vite.log 2>&1 &

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
ps aux | grep -E "gunicorn.*api.main|vite.*port 3000" | grep -v grep | awk '{print "   ", $2, $11, $12, $13}'