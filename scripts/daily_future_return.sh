#!/bin/bash
# 未来收益标签生成器
# 每日 18:00 运行（在数据下载完成后）
# 依赖于 data/price 目录有最新价格数据

cd /home/admin/AUTO-STOCK

python3 src/analyzer/future_return_generator.py

echo "$(date '+%Y-%m-%d %H:%M:%S') - future_return_generator.py 执行完成" >> logs/cron.log