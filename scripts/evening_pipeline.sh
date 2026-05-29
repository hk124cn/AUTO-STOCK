#!/bin/bash
# ====================================================
# 每日晚间流水线
# cron: 0 19 * * 1-5 bash /home/admin/AUTO-STOCK/scripts/evening_pipeline.sh
# ====================================================

set -euo pipefail
cd /home/admin/AUTO-STOCK

TARGET_DATE="${1:-$(date +%Y%m%d)}"
LOG="logs/evening_pipeline_${TARGET_DATE}.log"
exec > >(tee -a "$LOG") 2>&1

start_time=$(date +%s)

step() {
    echo ""
    echo "=========================================="
    echo "  步骤 $1: $2"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
}

fail() {
    echo "❌  步骤失败: $1"
    echo "日志: $LOG"
    exit 1
}

# 步骤1: 批量多因子评分
step 1 "批量多因子评分"
printf "2\nstock_pool.csv\n\n" | python3 main.py || fail "批量评分"
echo "✅  批量评分完成"

# 步骤2: 评分-价格历史表
step 2 "生成评分-价格历史表"
python3 src/analyzer/kline_analyzer.py --date "$TARGET_DATE" || fail "kline_analyzer"
echo "✅  评分-价格历史表完成"

# 步骤3: 每日报告
step 3 "生成每日报告"
python3 scripts/daily_report.py "$TARGET_DATE" || fail "daily_report"
if [ -f "reports/daily_report_${TARGET_DATE}.html" ]; then
    cp "reports/daily_report_${TARGET_DATE}.html" reports/index.html
    echo "✅  已更新 reports/index.html"
fi
echo "✅  每日报告完成"

end_time=$(date +%s)
elapsed=$(( end_time - start_time ))
echo ""
echo "=========================================="
echo "  全部完成 ✅"
echo "  耗时: ${elapsed}秒"
echo "  日期: $TARGET_DATE"
echo "=========================================="