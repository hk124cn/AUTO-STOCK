# 草稿笔记 — 报告与流水线 (#6)

## 阅读清单
- /home/admin/AUTO-STOCK/scripts/daily_report.py (1068 行)
- /home/admin/AUTO-STOCK/scripts/evening_pipeline.sh (55 行)
- /home/admin/AUTO-STOCK/scripts/daily_data_fetch.py (111 行)
- /home/admin/AUTO-STOCK/scripts/calc_signals.py (463 行)
- /home/admin/AUTO-STOCK/scripts/precompute_scores.py (64 行)
- /home/admin/AUTO-STOCK/scripts/launch_analysis.py (443 行)
- /home/admin/AUTO-STOCK/scripts/stock_analysis.py (602 行) [modified: line 17 RESULT_DIR 路径变更]
- /home/admin/AUTO-STOCK/scripts/run_v2_backtest.py (320 行) [新]
- /home/admin/AUTO-STOCK/scripts/daily_future_return.sh (10 行) [新]
- /home/admin/AUTO-STOCK/scripts/sim_trader.py (12.9KB, 已存在)
- /home/admin/AUTO-STOCK/scripts/daily_report_cron.sh (18 行, 已存在但被 evening_pipeline 取代)
- /home/admin/AUTO-STOCK/reports/daily_report_*.{html,md} (58 个日期)
- /home/admin/AUTO-STOCK/reports/index.html (覆盖式, 418KB)
- /home/admin/AUTO-STOCK/reports/daily_report_latest.md (stale 2026-05-15, 19KB)

## git 状态
- d5eae82 (2026-06-12) feat: Web目录重组、个股预警修复、每日流水线整合
- evening_pipeline.sh 上次修改 2026-06-15 09:35 (本次工作树无变更, 但 git 显示与 HEAD 一致)
- daily_report.py 上次修改 2026-05-29 10:16
- stock_analysis.py modified: line 17 `RESULT_DIR = ".../src/result"` → `".../result/daily_score"` (路径迁移)
- daily_future_return.sh new (May 24)
- run_v2_backtest.py new (Jun 15)

## 上次审查 3 个 P0 的修复状态

### P0-1 节假日跳过逻辑
- 结论：**未修复，且消失**
- 现状：evening_pipeline.sh 没有交易日历检查，整段 grep + DATE_HUMAN 转换逻辑都被删了
- 现状脚本只 3 步 (score → kline_analyzer → daily_report)
- cron `0 19 * * 1-5` 仍然周一-周五跑，周末会因 data/daily_market/...csv 缺失失败
- 上次 P1 的 sim_trader 失败吞错：脚本不再调 sim_trader，问题"消失"但 sim_trader 现在完全没有被流水线调

### P0-2 行业分析板块
- 结论：**未修复**
- 现状：daily_report.py 只有 8 个板块，仍然没有"行业分析"或"行业聚合"板块
- grep "industry\|行业分析\|industry_aggreg" 在 daily_report.py 0 命中
- 行业仅作为单因子 `行业相对强弱` 显示
- CLAUDE.md line 113 仍然声称 "特别关注股票高亮、收盘价+涨跌幅显示、行业分析"

### P0-3 sim_trader 失败被静默吞
- 结论：**未修复但不再相关**
- evening_pipeline.sh 不再调 sim_trader.py
- 但 sim_trader.py 是真实存在的 (12.9KB, Jun 15 还在更新)，仅靠 cron 0 19 跑 evening_pipeline 不会触发它
- v2 SELL 信号逻辑已搬到 calc_signals.py (lines 277-364)
- 因此 sim_trader 现在处于"功能存在但无调用方"的状态

### P0-4 calc_signals 只产 BUY 信号 (上次 P0)
- 结论：**已修复**
- calc_signals.py:277-364 新增 `generate_sell_signals()` 函数
- 读取 portfolio.db 的 SIM 账户持仓，结合 take_profit/stop_loss 参数生成 SELL 信号
- line 428-433 在 main() 中合并 BUY/SELL
- 输出 'SELL' 信号并带 sell_reason 字段

### P0-5 daily_report.py 内嵌 JSON 400KB (上次 P0)
- 结论：**未修复**
- daily_report.py:956 仍然 `stock_data_js = str(today_data).replace(...)`
- `reports/daily_report_20260615.html` 418022 字节 (上次 420539)，基本没改善
- 替换 'score' → 'total_score' 仍然是 dead code (batch_result 中没 'score' 字段)

## 新发现

### 流水线严重缩水 (新 P0)
- evening_pipeline.sh 现在只有 3 步：`批量评分 → kline_analyzer → daily_report`
- **完全没有** calc_signals、sim_trader 步骤
- CLAUDE.md line 120 说 "串联执行：批量评分 → kline_analyzer → 每日报告，任一步失败会停在该步"
  - 字面上 3 步是对的，但实际丢掉了 calc_signals 这一步（CLAUDE.md "数据存储" 段提到 result/signals/v1/, v2/）
- 这意味着 cron 跑完后 result/signals/ 不会更新，stock.auto-claw.top/signals 页面看到的是陈旧信号

### run_v2_backtest.py (新文件)
- Jun 15 创建，与 run_launch_backtest.py 完全平行
- 固定 v2 参数 (first_break_only=True, max_pos_pct_basis='capital', build_days=2)
- 参数网格：止盈 {5,10,15,20,30} × 止损 {3,5,8,10} × 冷却期 {0,1,3} = 60 种
- 跑两轮：按总评分排序 + 按财报评分排序
- 输出到 result/backtest/v2_首次突破_资金固定_2天建仓/{year}/
- 问题：参数网格太密 (60 × 2 排序)，耗时长；而且 sort_by_finance=True 时仍固定 buy_threshold=30
- 与 CLAUDE.md (2026-06-15 实盘策略决策) 一致：10万本金，v1+总评分，止盈20%/止损8%/冷却3天 ✓

### daily_future_return.sh (新文件)
- Jun 24 创建，cron `0 18 * * 1-5` 跑
- 调 src/analyzer/future_return_generator.py
- 不属于 evening_pipeline 流水线的一部分，但写入 logs/cron.log
- 目的：计算未来 5d/10d/20d 收益率作为模型训练标签

### daily_data_fetch.py cron 时间变更
- 上次审查 cron `0 16 * * 1-5`
- 当前 cron `0 17 * * 1-5` (晚 1 小时)
- 16:00 跑可能 akshare 数据还没出来，17:00 更安全 — 这是一个改善

### CLAUDE.md / API 路径迁移
- src/result/ → result/daily_score/ 已在 api/main.py 全面完成
- stock_analysis.py:17 也跟着改了
- 但 daily_report.py 仍硬编码 `RESULT_DIR = "/home/admin/AUTO-STOCK/result/daily_score"`（绝对路径），没改用 __file__ 计算
- 上次 P1 硬编码绝对路径问题未改善

### daily_report.py best/worst 空检查 (P2)
- HTML 报告 line 856 `if focus_avg_scores:` 已保护 best/worst (line 857/858)
- 但 Markdown 报告 line 417 `if focus_avg:` 后面 line 430/431 仍然 `max(focus_today.items())` 无保护
- 差异：`focus_avg` 是从 `focus_today` 派生但只 append 当 `today_row` 非空，所以理论上 `focus_avg` 非空时 `focus_today` 也非空 — 但两者不是同一变量，逻辑间接

### REPORT_DIR、generated_at.json
- /home/admin/AUTO-STOCK/reports/individual/generated_at.json 有 60+ 只股票的 "今天已生成报告" 缓存
- 这是 stock_analysis.py 用 daily cache，但 cache 是按 "YYYY-MM-DD" 写入
- 如果用户周六搜股生成报告，cache['code'] = 周六日期；周日再搜 → cache['code'] != 今天 → 重新生成
- 即：cache 不能区分"今天是否交易日"，导致非交易日会重生成报告
- P3

### daily_report.py 仍然 8 板块，没扩成 9 板块
- README_每日评分网页系统.md 说 "8 个板块"
- CLAUDE.md 说 "8 个板块 + 行业分析"
- 实际 8 板块

## 主要问题
1. **P0**: 流水线丢失 calc_signals + sim_trader 步骤 (result/signals/ 不再被 cron 更新)
2. **P0**: 流水线丢失交易日历检查 (周末 cron 会跑然后失败)
3. **P0**: 行业分析板块缺失 (CLAUDE.md 文档承诺但未实现)
4. **P0**: daily_report.py 内嵌 1300+ 只股票 JSON 到 HTML (400KB+)
5. **P1**: daily_report.py Markdown 报告 best/worst 无空保护 (line 430)
6. **P1**: daily_report.py 硬编码绝对路径 `/home/admin/AUTO-STOCK/...` (line 31-41, 586, 599)
7. **P1**: daily_report.py 重复定义 CONFIG 块 (line 31-33 vs 35-38)
8. **P1**: daily_report.py 重复定义 factor_names (line 137 vs 578)
9. **P1**: daily_report.py 未使用 import: `requests`, `re`, `timedelta`
10. **P1**: signals_latest.csv 是普通文件覆盖式 (与 CLAUDE.md 软链接文档矛盾)
11. **P2**: daily_report.py datetime.now() 无时区
12. **P2**: main.py 通过 stdin 注入 (printf "2\nstock_pool.csv\n\n") 仍脆弱
13. **P2**: daily_report.py `str(today_data)` 内嵌 JS，搜索功能 unicode/空格不严谨
14. **P2**: dp_diff_factor 未纳入 FACTOR_LIST (CLAUDE.md 说 9 因子)
15. **P3**: daily_report_cron.sh 是旧版 wrapper，未删除 (P3)
16. **P3**: individual/generated_at.json 用日期判断，无交易日过滤 (P3)

## 与上次审查对比
- 修复：P0-4 calc_signals SELL 信号已实现
- 修复：daily_report.py.bak/.fix 已清理
- 修复：daily_report.py HTML 端 best/worst 空保护
- 修复：sim_trader P1 失败吞错 → 通过删除调用解决（不彻底）
- 未修复：P0-1 节假日跳过逻辑（且恶化：grep 整段被删）
- 未修复：P0-2 行业分析板块
- 未修复：P0-5 daily_report.py 400KB JSON
- 未修复：P1 硬编码路径
- 未修复：P1 重复代码块（CONFIG、factor_names）
- 未修复：P1 未使用 import
- 未修复：P1 signals_latest 软链接 vs 普通文件
- 未修复：P2 dp_diff_factor 纳入