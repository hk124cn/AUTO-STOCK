#!/bin/bash
cd /home/admin/AUTO-STOCK

# 获取日期：默认今天，可传入参数覆盖
if [ -n "$1" ]; then
    TARGET_DATE=$1
else
    TARGET_DATE=$(date +%Y%m%d)
fi

# 运行报告生成
python3 scripts/daily_report.py $TARGET_DATE

# 复制最新报告为 index.html
if [ -f reports/daily_report_${TARGET_DATE}.html ]; then
    cp reports/daily_report_${TARGET_DATE}.html reports/index.html
    echo "✅ 已更新 index.html"
fi
