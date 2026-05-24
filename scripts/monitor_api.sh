#!/bin/bash
# API 监控脚本 - 挂了就拉起来

LOG_FILE="/home/admin/AUTO-STOCK/logs/api_monitor.log"
API_PORT=8000
API_URL="http://localhost:${API_PORT}/api/v1/financial/score/600519"

check_api() {
    curl -s --connect-timeout 3 --max-time 5 "$API_URL" > /dev/null 2>&1
    return $?
}

restart_api() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - API 挂了，重启中..." >> "$LOG_FILE"

    # 杀掉现有进程
    pkill -f "gunicorn.*api.main" 2>/dev/null || true
    sleep 1

    # 启动新进程
    cd /home/admin/AUTO-STOCK
    nohup python3 -m gunicorn -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${API_PORT} api.main:app > /tmp/api.log 2>&1 &

    sleep 3

    # 检查是否启动成功
    if check_api; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - API 重启成功" >> "$LOG_FILE"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - API 重启失败!" >> "$LOG_FILE"
    fi
}

if check_api; then
    # API 正常
    exit 0
else
    # API 异常，重启
    restart_api
    exit 0
fi