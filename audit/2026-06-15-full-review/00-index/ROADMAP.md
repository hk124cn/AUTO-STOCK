# 改进路线图 — AUTO-STOCK 2026-06-16 复查

> 与 `00-index/REPORT.md` 配套。审查实际日期 2026-06-16，目录名沿用 06-15 作内部标识。

---

## 🔴 立即（24h 内）— 5 项

### 1. 删 `.git.backup-before-filter-repo/` 暗礁 ⏱ 5min
- S2 修复留下的 2MB 完整 git 仓库在 working tree
- 含未抹除旧 token，任何 tar / docker COPY / r2_backup 都会重新泄漏
- **建议**：确认 S2 完整后，git rm -rf

### 2. 修 accounts.strategy_id 漂移 ⏱ 30min
- `data/portfolio.db` accounts 表实际只有 7 列，缺 `strategy_id`
- `api/main.py:1027-1034 set_account_strategy` 上线即 SQL 错误
- `sim_trader.py:176 get_strategy` 静默 fallback default
- **建议**：`_init_db` 末尾加兼容性 ALTER（用 try/except sqlite3.OperationalError）

### 3. 修 main.py s_score 死计算 + 路径不一致 ⏱ 30min
- `main.py:48 s_score` 累加 9 因子 `sum_score`（=100）但下游拿不到满分
- main.py 用 `./result/daily_score/`，其他脚本用绝对路径

### 4. 修前导零 4→7 处（已恶化）⏱ 1h
- 上次 4 处遗留未修，本次增至 7 处
- 涉及 api/main.py + main.py 多处裸 `pd.read_csv` 不指定 dtype

### 5. 修 setStrategyVersion 调 clearAllCache 过重 ⏱ 1h
- `web/stock-system/src/loader.js:92-96` 切版本清全部缓存
- 放大成 2 次后端请求 + 跨页缓存丢失
- **建议**：只清 signals + scores 缓存键

---

## 🟠 1 周内（5d）— 回测可信度 + 信号 + 数据

### 回测 P0（用户最关心）
6. **A1 — scored 模式 T 日数据截断** ⏱ 1d
   - 当前用当天 19:00 batch_result 决策当天开盘前
   - 改：scored 模式强制 T-1 batch_result

7. **A4 — 调仓价改 T+1 开盘 + 滑点** ⏱ 2d
   - get_next_trade_day 已实现但无人调用
   - 改：所有 backtest engine execute_price 改 T+1 open + 0.1% 滑点

8. **重做回测** ⏱ 1d
   - 修 A1+A4 后重跑 2022-2026 全部数字
   - 输出"前视偏差修正版"

### 信号 + 策略双源
9. **sim_trader 消费 SELL 信号** ⏱ 2d
   - 当前 sim_trader 不读 SELL 列，独立用 K 线扫描
   - 改：sim_trader 改读 calc_signals 输出的 SELL，移除独立 K 线扫描逻辑

10. **策略双源联通** ⏱ 2d
    - DB strategies 表加 first_break_only / max_pos_pct_basis / build_days 字段
    - sim_trader 改读注册表（不是 DB）
    - 改完后端冒烟测试：前端切 V2 → sim_trader 用 V2 参数

11. **实盘账户接入止盈止损** ⏱ 1d
    - calc_signals:291 硬编码 SIM 改为支持 REAL
    - sim_trader:318 拒绝 REAL 改为接受

### 数据流水线
12. **F4 尾巴** ⏱ 10min
    - 删 src/backtester.py 和 src/tracker.py（F4 删 data_fetcher 没修他们的 import）
13. **F5 行业 mapping 重建** ⏱ 30min
    - mapping 34 天没动
    - 跑 build_industry_data（**只步骤 1 --industry**，不要全量）
14. **F6 get_market_change 异常处理** ⏱ 10min
15. **F7 get_fund_flow_5day 删一个** ⏱ 10min
16. **801010 农林牧渔 CSV 缺失** ⏱ 5min
17. **trade_days.csv 续期到 2028** ⏱ 5min

### 报告
18. **daily_report.py 去掉全量 JSON 序列化** ⏱ 2h
    - 仍 418KB，全量注入是反模式
19. **evening_pipeline.sh 恢复 4 步** ⏱ 30min
    - 加回 calc_signals 和 sim_trader 调用
    - 失败硬退出（不能 `|| echo`）
20. **节假日跳过逻辑恢复** ⏱ 10min
    - 整段被删，需用 human 时间格式匹配

---

## 🟡 1 月内 — 业务联调 + 文档 + 安全

### 业务联调
21. **Calc_signals 接入 cron** ⏱ 30min
    - 当前 3 脚本 untracked，cron 调度外部
    - 改：commit + 加进 evening_pipeline 步骤 4
22. **sim_trader CLI 加 --strategy-version** ⏱ 2h
    - 当前 v2 无法通过 CLI 跑
23. **Portfolio.vue 加 TP/SL 列 + 策略版本列** ⏱ 4h
24. **删除 Strategies.vue 硬编码回测数字** ⏱ 1h
    - 改从 /api/v1/backtest/top 拉
25. **CORS 收紧** ⏱ 1h
    - `allow_origins=["*"]` → 白名单 auto-claw.top
    - 同步改 nginx.conf

### 文档去重
26. **三份文档去重** ⏱ 4h
    - HANDOVER (352) / MAINTENANCE (168) / CLAUDE.md 80% 重复
    - 留 CLAUDE.md 为唯一权威，其他归档到 docs/
27. **HANDOVER.md 重写** ⏱ 2h
    - 提及 v2、sim_trader、卖信号、stock-system 部署
28. **CRON.md 修死脚本** ⏱ 30min
    - 删 `daily_download.sh`（不存在）→ `daily_data_fetch.py`
    - 修正 daily_data_fetch docstring 写"0 16"实际"0 17"
29. **meta/ 决定保留/删除** ⏱ 1h
    - 3 文件 0 代码引用，snapshot_manifest 停更 26 天

### Web 工程质量
30. **vite minify: false → 'esbuild'** ⏱ 30min
    - 3 项目都改，可降 60% 体积
31. **echarts 按需引入** ⏱ 2h
    - 当前 Stats.js 2.5MB
32. **stock-alert dist 393MB 切 nginx alias** ⏱ 4h
33. **Home.vue 14 处 console.log** ⏱ 30min
34. **Dashboard clearAllCache** ⏱ 1h
35. **StockKline 死代码** ✅ 已修

### 安全
36. **CORS** (见 #25)
37. **portfolio.db 权限 644 → 600** ⏱ 5min
38. **api str(e) 12 处脱敏** ⏱ 2h
39. **feedbacks.json 改 SQLite + .gitignore** ⏱ 2h

### 横向
40. **requirements.txt 补齐** ⏱ 10min
41. **CLI EOFError 4 处加 try** ⏱ 30min
42. **miniprogram pages/webview 删死代码** ⏱ 30min
43. **miniprogram/node_modules 363MB .gitignore** ⏱ 5min

---

## 🟢 长期

44. **回测 v2 拆分**：数据层/因子层/组合层/报告层分离 ⏱ 1w
45. **回测 v2 单元测试** ⏱ 3d
46. **Web 三件套统一 loader** ⏱ 3d
47. **跨机 sync 策略**（本地笔记本+云服务器） ⏱ 2d
48. **API 版本化**（/api/v1/ → /api/v2/） ⏱ 1w
49. **miniprogram 实际跑起来** ⏱ 3d
50. **将 calc_signals.py / sim_trader.py / signal_engine.py commit** ⏱ 5min（最优先）

---

## 工作量统计

- 🔴 立即：~3h
- 🟠 1 周：~12d
- 🟡 1 月：~25d
- 🟢 长期：~5w

---

## 审查质量声明

- 9 个子 agent 全部完成，**无 429 限流**
- P0 安全类已可信，**功能类建议最小复现脚本二次确认**
- **本轮最重要的发现**：
  1. **策略双源不联通**——用户感知的 V2 ≠ 实际跑的策略
  2. **卖信号集成是半成品**——SELL 算了但没人消费
  3. **三个核心脚本 untracked**——仓库内不可复现
  4. **S2 暗礁 .git.backup-before-filter-repo**——可能重新泄漏
  5. **evening_pipeline.sh 缩水**——业务核心流水线不再完整
