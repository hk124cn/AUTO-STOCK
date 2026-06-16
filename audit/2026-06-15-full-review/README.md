# AUTO-STOCK 复查 — 2026-06-15

> 与上次审查（`audit/2026-06-14-full-review/`，约 24h 前）对比  
> 重点关注：**stock-system 的信号版本切换 + 卖信号集成**  
> 距离上次审查期间已做：S1 API 鉴权、S2 TUSHARE 轮换、S6/F4 死文件清理

## 复用上次骨架
`_shared/CONVENTIONS.md` 和 `CHECKLIST.md` 直接继承上次，不重写。每个子报告输出到 `raw-notes/notes.md` + `final/SUBREPORT-*.md`。

## 本轮特别检查项

### A. 上次审查的 P0 修复状态（关键对照表）
上次 06-14 审查发现 **P0 ×23+ P1×46+ P2×55+**，本轮重点追踪：

| # | 上次 P0 | 状态 | 证据 |
|---|---------|------|------|
| F1 | daily_change 列名 bug | ⏳ 待查 | src/factors/daily_change_factor.py |
| F2 | scoring_engine 死代码 | ⏳ 待查 | main.py 是否走 factor_manager |
| F3 | dp_diff_factor 命名误导 | ⏳ 待查 | 文件是否改名 |
| F4 | data_fetcher 0 字节 + sel.py 死 import | ✅ 应已修 | git status 显示 D（删除） |
| F5 | 行业映射 33 天未更新 | ✅ 应已修 | 16:00 data_fetcher 恢复 + cron 17:00 自动跑 |
| F6 | get_market_change 异常返 0.0 | ⏳ 待查 | src/utils.py |
| F7 | get_fund_flow_5day 双定义 | ⏳ 待查 | data_manager.py |
| F8 | trade_days.csv 硬编码 | ⏳ 待查 | data/calendar/ |
| F9 | 财务因子 final 截断边界 | ⏳ 待查 | financial_factor.py |
| F10 | 前导零 4 处遗留 | ⏳ 待查 | api/main.py + main.py |
| S1 | API 无认证 | ✅ 应已修 | api/security.py + 11 个 Depends |
| S2 | TUSHARE_TOKEN 泄漏 | ✅ 应已修 | 已轮换 + filter-repo |
| S3 | feedbacks.json IP 隐私 | ⏳ 待查 | 是否改 SQLite |
| S4 | 双服务端口冲突 | ⏳ 待查 | systemd vs gunicorn |
| S5 | CLI path traversal | ⏳ 待查 | main.py run_batch |
| S6 | 死文件 bak/fix | ✅ 应已修 | 已建 .trash/ |
| 回测 A1-A4 | 前视偏差 4 项 | ⏳ 待查 | src/backtest/ |
| 回测 E1 | run_signal.py ImportError | ⏳ 待查 | 是否补实现或删除 |

### B. 本轮新增审查重点（用户特别要求）

1. **stock-system 信号版本切换**
   - `scripts/calc_signals.py`（463 行，比上次 295 行 +168 行）
   - V1 vs V2 策略如何切换？参数？UI 入口？
   - 是否在 web/stock-system/src/views/Signals.vue 体现？

2. **卖信号集成**
   - 信号策略原本只有"买入"信号（CLAUDE.md 写"前 7 天平均分≥30分买入"）
   - 新增"卖信号"的定义？阈值？触发？
   - sim_trader.py 是否消费卖信号自动平仓？

3. **新文件清单**（本次新出现）
   - `scripts/run_v2_backtest.py`（320 行）—— V2 回测入口
   - `src/analyzer/future_return_generator.py` —— 未来收益
   - `src/analyzer/ANALYZER_PLAN.md` —— 计划文档
   - `docs/stock-system/`、`docs/README.md` —— 文档站？
   - `deploy/stock-system.conf`、`deploy/deploy_stock_system.sh` —— 部署
   - `meta/` —— 用途不明
   - `miniprogram/` 已有 + `miniprogram/CLAUDE.md` —— 微信小程序？

4. **HANDOVER.md（352 行新建）/ MAINTENANCE.md / CLAUDE.md（已改）**
   - 写的是什么？是否过期？
   - 重点：HANDOVER.md 的最新状态

5. **回测结果**
   - 是否新增了 V2 的回测数据？（`result/backtest/` 新文件夹？）
   - V1 vs V2 对比？

## 子任务清单

| # | 子任务 | 重点 |
|---|--------|------|
| 1 | 因子系统 | 06-14 P0 修复状态 |
| 2 | 数据流水线 | future_return_generator + 行业 cron |
| 3 | 回测系统 + V2 | run_v2_backtest.py / signal_engine.py |
| 4 | **stock-system 信号** | **【本轮重点】版本切换 + 卖信号** |
| 5 | Web 前端 | 3 个项目 |
| 6 | 报告+流水线 | stock_analysis.py / launch_analysis.py |
| 7 | 持仓+信号 | schema + 卖信号消费 |
| 8 | Cron+部署 | deploy_stock_system.sh / stock-system.conf |
| 9 | 横向 | HANDOVER/MAINTENANCE/CLI |

## 输出汇总

汇总到 `00-index/REPORT.md`：
- 06-14 P0 修复状态表（修了/未修/新增）
- 本轮新增 P0 列表
- 重点关注：stock-system 信号逻辑的合理性
