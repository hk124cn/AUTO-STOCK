#!/bin/bash
# ============================================================
# 股票操作系统部署脚本
# 用法：sudo bash deploy/deploy_stock_system.sh
# ============================================================
set -euo pipefail

AUTO_STOCK="/home/admin/AUTO-STOCK"
NGINX_CONF_SRC="$AUTO_STOCK/deploy/stock-system.conf"
NGINX_CONF_DST="/etc/nginx/conf.d/stock-system.conf"
SYSTEMD_SRC="$AUTO_STOCK/deploy/stock-api.service"
SYSTEMD_DST="/etc/systemd/system/stock-api.service"

echo "================================================"
echo "  股票操作系统部署"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================"

# 检查权限
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请用 root 权限运行: sudo bash $0"
    exit 1
fi

# 检查现有服务（不修改）
echo ""
echo "=== 0. 备份现有配置 ==="
if [ -f /etc/nginx/conf.d/auto-claw.top.conf ]; then
    cp /etc/nginx/conf.d/auto-claw.top.conf /etc/nginx/conf.d/auto-claw.top.conf.bak.$(date +%Y%m%d)
    echo "✅ 已备份: auto-claw.top.conf"
fi
echo ""

# 1. 部署 nginx 配置
echo "=== 1. 部署 Nginx 配置 ==="
if [ -f "$NGINX_CONF_DST" ]; then
    echo "⚠️  配置文件已存在: $NGINX_CONF_DST"
    echo "    先备份为 stock-system.conf.bak.$(date +%Y%m%d)"
    cp "$NGINX_CONF_DST" "${NGINX_CONF_DST}.bak.$(date +%Y%m%d)"
fi
cp "$NGINX_CONF_SRC" "$NGINX_CONF_DST"
echo "✅ 复制: $NGINX_CONF_SRC → $NGINX_CONF_DST"

# 测试配置
echo ""
echo "=== 2. 测试 Nginx 配置 ==="
nginx -t
echo ""

# 2. 部署 API 服务
echo "=== 3. 部署 API 服务 ==="
mkdir -p "$AUTO_STOCK/logs"
cp "$SYSTEMD_SRC" "$SYSTEMD_DST"
echo "✅ 复制: $SYSTEMD_SRC → $SYSTEMD_DST"

# 3. 启动服务
echo ""
echo "=== 4. 启动 API 服务 ==="
systemctl daemon-reload
systemctl enable stock-api.service
systemctl restart stock-api.service
sleep 2

if systemctl is-active --quiet stock-api.service; then
    echo "✅ stock-api.service 运行中"
else
    echo "❌ stock-api.service 启动失败，查看日志:"
    journalctl -u stock-api.service -n 30 --no-pager
    exit 1
fi

# 4. 重载 nginx
echo ""
echo "=== 5. 重载 Nginx ==="
systemctl reload nginx
echo "✅ Nginx 已重载"

# 5. 健康检查
echo ""
echo "=== 6. 健康检查 ==="
sleep 2

# 检查 API
if curl -s -f -o /dev/null --max-time 5 http://127.0.0.1:8000/api/v1/portfolio/account; then
    echo "✅ API 端点正常: http://127.0.0.1:8000/api/v1/portfolio/account"
else
    echo "⚠️  API 端点无响应（数据库可能未初始化，使用时会自动创建）"
fi

# 检查域名
echo ""
echo "=== 7. 验证外部访问 ==="
DOMAIN_CHECK=$(python3 -c "import socket; print(socket.gethostbyname('stock.auto-claw.top'))" 2>/dev/null || echo "DNS_ERROR")
echo "DNS 解析: stock.auto-claw.top → $DOMAIN_CHECK"

if [ "$DOMAIN_CHECK" != "DNS_ERROR" ]; then
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -k https://stock.auto-claw.top/ 2>/dev/null || echo "000")
    echo "HTTPS 响应: $RESPONSE"
fi

echo ""
echo "================================================"
echo "  部署完成 ✅"
echo "================================================"
echo ""
echo "访问地址: https://stock.auto-claw.top/"
echo ""
echo "现有服务状态（应未受影响）:"
echo "  - auto-claw.top (80/443): $(systemctl is-active nginx)"
echo "  - stock-api (8000): $(systemctl is-active stock-api.service)"
echo ""
echo "常用命令:"
echo "  - 查看 API 日志: tail -f /home/admin/AUTO-STOCK/logs/api-stdout.log"
echo "  - 重启 API: sudo systemctl restart stock-api.service"
echo "  - 重载 Nginx: sudo systemctl reload nginx"
echo "  - 查看状态: sudo systemctl status stock-api.service"
