# 草稿笔记 — 报告与流水线 (#5)

## 阅读清单
- /home/admin/AUTO-STOCK/scripts/daily_report.py (1069 行, 当前活跃版本)
- /home/admin/AUTO-STOCK/scripts/daily_report.py.bak (45367 字节, 旧版)
- /home/admin/AUTO-STOCK/scripts/daily_report.py.fix (45367 字节, 几乎等同 .bak)
- /home/admin/AUTO-STOCK/scripts/daily_report_cron.sh (旧版, 不在用)
- /home/admin/AUTO-STOCK/scripts/evening_pipeline.sh (晚间流水线)
- /home/admin/AUTO-STOCK/scripts/daily_data_fetch.py (每日数据拉取入口)
- /home/admin/AUTO-STOCK/scripts/daily_download.py
- /home/admin/AUTO-STOCK/scripts/daily_fund_flow.py
- /home/admin/AUTO-STOCK/scripts/daily_industry_change.py
- /home/admin/AUTO-STOCK/scripts/calc_signals.py
- /home/admin/AUTO-STOCK/scripts/precompute_scores.py
- /home/admin/AUTO-STOCK/scripts/launch_analysis.py
- /home/admin/AUTO-STOCK/reports/ (产物)

## 已查的事实

### evening_pipeline.sh
- set -euo pipefail 在第 7 行
- 调用 main.py 通过 printf "2\nstock_pool.csv\n\n" 注入 (line 57)
- main.py read input 第二个空行作为 in_fname → 触发默认 filename 走 today 日期 (line 87-90 of main.py)
- 4 步:
  - step 1: 批量评分 → fail 终止
  - step 2: kline_analyzer → fail 终止
  - step 3: calc_signals → fail 终止
  - step 3.5: sim_trader → 失败仅 echo warn 不终止 (line 77)
  - step 4: daily_report → 失败时回滚 reports/index.html (line 90-97)
- 交易日历 grep 检查 line 37: `grep -q "^${TARGET_DATE}"` — 这是匹配 `20260512` 在 `2026-05-12` 之前的内容？ 注意 trade_days.csv 是 `2026-05-12` 格式。grep "^20260512" 不会匹配 "2026-05-12"。
  → 这是 P1 bug：节假日跳过逻辑实际上不会触发。

### daily_report.py
- 行 11-12: import requests, re — 都未使用 (0 处使用)
- 行 31-38: RESULT_DIR/SELF_STOCK_FILE/FOCUS_STOCK_FILE 定义**两次** (重复块)
- 行 32/37: 结果目录指向 /home/admin/AUTO-STOCK/result/daily_score
- 行 333: 生成时间用 datetime.now() 不带时区
- 行 41: PRICE_DIR = "/home/admin/AUTO-STOCK/data/price" — 硬编码绝对路径
- 行 578-642: HTML 报告里又**重新定义**了 factor_names 列表（与全局 FACTOR_LIST 一致），且重复代码块（与 generate_report 函数几乎复制粘贴）
- 9 因子列表 (line 137): 包含 "今年相对大盘强弱" 和 "行业相对强弱" 两个不同因子。
- src/factors/dp_diff_factor.py 存在但**未在 FACTOR_LIST**里
- src/factors/financial_factor.py 用的是 "财报" 因子
- HTML 内嵌 JS: stock_data_js = str(today_data).replace("'score'", "'total_score'") — 但 batch_result 里就没有 'score' 字段，replace 无效（无害）
- HTML 行 957: stockData 把整张 today_data JSON 嵌入页面 — 上千只股票直接序列化到 HTML，单文件 400+KB (从 stat 验证: 420539 字节)
- 行 31/36: RESULT_DIR 重复定义两次 — 重复但不影响功能
- 生成报告不向 reports/daily_report_latest.html 输出，仅写 daily_report_${date}.html
- 行 1058-1067: 同时写 .md 和 .html，覆盖式 (同一日期第二次跑会覆盖)

### calc_signals.py
- 行 29-30: BUY_THRESHOLD=30, LOOKBACK_DAYS=7
- 行 215-220: 使用 os.replace 原子更新 signals_latest.csv（无软链接）
- 行 175-178: 排除 signals_latest 和临时文件 — 但 signals_latest.csv 现在是普通文件，会被 glob 'signals_*.csv' 匹配，但 stem 是 'signals_latest' → 被手动排除
- 行 152: signal 字段只标 'BUY' 或 ''（空字符串） — 没有 SELL
- 行 162-204: apply_cooldown 函数 — 仅用 BUY 信号历史过滤
- 行 207-222: save_signals — 保存到 signals_${date}.csv + signals_latest.csv
- 行 169: cutoff = target_dt - 2 * cooldown_days — 命名奇怪：变量名 cutoff 实际是过滤范围起点（更早的信号会被丢弃）
- 行 41-44: load_pool_codes — 用 zfill(6) 补齐 6 位
- 行 50-65: normalize_date_value — 强健（处理 .0、ISO、横线）
- 行 73-84: load_score_history — 去重 + 数值化，coerce 错误
- 行 264-273: 输出 buy_signals 空时仅 print "没有找到"，无日志
- 行 286: 没把 buy 信号写入单独文件，仅一起写入 signals_${date}.csv（前端需过滤 signal=='BUY'）

### daily_data_fetch.py / daily_download.py / daily_fund_flow.py / daily_industry_change.py
- daily_data_fetch.py 包装 3 个子脚本 (line 89/95/101)
- daily_download.py: 调 download_market + build_price，仅 is_trade_day 判断（依赖 src/datafactory/trade_calendar.is_trade_day）
- daily_fund_flow.py: MAX_RETRIES=3, 文件已存在则跳过 (line 60-62)
- daily_industry_change.py: 131 个行业 × 2 秒延时 = 至少 4 分钟（262 秒）。当日文件已存在则跳过 (line 100-103)
- 失败时 daily_data_fetch 不中断后续步骤 — 但子脚本失败已被打印

### precompute_scores.py
- 薄包装：调 src.backtest.scorer.precompute_scores
- 与 evening_pipeline.sh 无集成

### launch_analysis.py
- 与流水线无集成
- 是研究/回测工具（找启动点）

### 日志
- logs/ 目录各脚本独立写日志
- evening_pipeline.sh 写 logs/evening_pipeline_${date}_${HHMMSS}.log
- daily_download.py 写 logs/daily_download_${date}.log
- daily_data_fetch.py 写 logs/daily_fetch_${date}.log
- 注意：daily_data_fetch 是 16:00 跑，evening_pipeline 是 19:00 跑 — 不在同一步骤。
- CLAUDE.md 说"日志路径 logs/" 模糊；实际是按脚本和日期分散
- calc_signals.py 不写日志文件，只 print 到 stdout（晚上重定向到 evening_pipeline.log）

### 软链接 vs 普通文件
- CLAUDE.md 写"signals_latest.csv 是软链接"
- 实际: 用 os.replace 写入，是普通文件覆盖式 (不是 symlink)
- 验证: file 命令显示 UTF-8 Unicode (with BOM) text, 不是 symbolic link

### 行业分析
- daily_report.py 内**没有**"行业分析"板块 (CLAUDE.md 提到了，实际不存在)
- 实际只有 8 个板块: 大盘概览 / TOP榜单 / 自选股 / 特别关注 / 今日vs昨日 / 5日走势 / 风险 / 投资建议

## 主要问题
1. P0: 节假日跳过 grep 模式不匹配
2. P0: 没有 SELL 信号定义（CLAUDE.md 也只说买入）
3. P0: 报告缺少"行业分析"板块
4. P1: daily_report.py 大量重复代码块（FACTOR_LIST 写两次）
5. P1: main.py 通过 stdin 注入易碎（其它调用方式都需要 in_fname 是日期）
6. P1: 硬编码绝对路径 /home/admin/AUTO-STOCK/...
7. P1: signals_latest.csv 是普通文件覆盖（不是 symlink），与 CLAUDE.md 文档不一致
8. P2: 未使用 imports (requests, re, timedelta)
9. P2: 重复 CONFIG 块
10. P2: 日志路径分散