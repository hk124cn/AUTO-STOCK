# 04 — 信号系统审查（v1/v2 切换 + 卖信号集成）原始笔记

> 审查日期 2026-06-16
> 范围：脚本 calc_signals.py / sim_trader.py + 后端 src/backtest/signal_engine.py、strategies.py + API api/main.py + 前端 Signals.vue / Strategies.vue / Portfolio.vue / Stats.vue / loader.js + 数据 result/signals/{v1,v2}/ + 流水线 evening_pipeline.sh

---

## A. 关键文件位置与角色

| 文件 | 行数 | 角色 | git 状态 |
|---|---|---|---|
| `scripts/calc_signals.py` | 463 | 信号主计算（BUY + SELL） | **untracked**（从未 commit） |
| `scripts/sim_trader.py` | 343 | 模拟仓自动交易（盘后触达） | **untracked** |
| `src/backtest/signal_engine.py` | 399 | v2 回测引擎 | **untracked** |
| `src/backtest/strategies.py` | 102 | v1/v2 注册表 | 已 commit（之前 1 版本） |
| `src/portfolio/database.py` | 500+ | SQLite 持仓库 | 已 commit |
| `api/main.py` | 1216+ | FastAPI | uncommitted（修改） |
| `web/stock-system/src/views/Signals.vue` | 592 | 信号监控 UI | uncommitted（修改） |
| `web/stock-system/src/views/Strategies.vue` | 729 | 策略管理 + 版本切换 | uncommitted（修改） |
| `web/stock-system/src/data/loader.js` | 312 | 数据加载 | uncommitted（修改） |
| `result/signals/v1/signals_latest.csv` | - | v1 最新信号 | 文件有 |
| `result/signals/v2/signals_latest.csv` | - | v2 最新信号 | 文件有 |
| `scripts/evening_pipeline.sh` | 39 | 流水线 | 已 commit |

## B. 信号主流程链路

### B.1 信号计算（每日 19:30）
```
cron 19:30 → python scripts/calc_signals.py  →  result/signals/{v1,v2}/signals_YYYYMMDD.csv
                       ↑
                       接受 --strategy-version {v1,v2}，默认 v1
```

calc_signals.py 主要函数：
1. `load_score_history()` 读取 `result/score_price_history.csv`
2. `calc_moving_avg()` 计算前 N 日均分，触发 BUY 信号
3. `apply_cooldown()` 同股冷却期过滤
4. `generate_sell_signals()` 检查持仓触达止盈/止损，写入 SELL 信号
5. `save_signals()` 写 `signals_{date}.csv` + `signals_latest.csv`（原子 rename）

### B.2 信号消费（每日 19:30 之后）
```
sim_trader.py 应该被 cron/流水线调用 → 读 signals_latest.csv → 模拟仓下单/平仓
```

**但 evening_pipeline.sh 当前 4 步里没有 sim_trader**！文件 line 1-39 只跑：
1. 批量评分
2. kline_analyzer
3. daily_report

sim_trader 完全不在流水线里。MAINTENANCE.md 第 117 行说"19:30 信号计算 → calc_signals.py（v1+v2）"，但根本没说谁去消费信号执行下单。

CLAUDE.md "每日晚间流水线" 章节说"串联执行：批量评分 → kline_analyzer → 每日报告"，也未提 sim_trader。

### B.3 信号展示（前端）
```
Signals.vue → loadSignals(version=localStorage) → GET /api/v1/signals/latest?version=vX
                                              → 读 signals_latest.csv + 装饰 BUY/SELL 徽章
```

### B.4 卖信号执行路径（理论上）
```
calc_signals.py:generate_sell_signals() → 读 portfolio.db SIM 持仓 → 
  对比 score_price_history close_price → 触发止盈/止损 → 写 SELL 行到 signals_{date}.csv
```

问题：SELL 信号写到 CSV 文件里，但 sim_trader.py 实际不看 SELL 列（line 244：`buy_signals = signals[signals['signal'] == 'BUY']`）。**sim_trader 用自己独立的盘后扫描 K 线检查止盈/止损**（`check_take_profit_stop_loss()`），不从 signals_latest.csv 读 SELL 列。

## C. 信号版本切换（v1/v2）

### C.1 前端切换路径
- Strategies.vue 显示两个 version-card
- 用户点"切换到 v2" → `setStrategyVersion('v2')` 写入 localStorage
- 下次访问 Signals.vue → `getStrategyVersion()` 读 localStorage → 调用 `/api/v1/signals/latest?version=v2`
- Signals.vue:178 `sortField` 根据版本切换排序字段（v2 按 finance_score，v1 按 avg7_score）

### C.2 后端验证
- api/main.py:1101 `get_latest_signals(version: str = "v1")` 接受 query param
- 通过 `get_strategy(version)` 查注册表 → 未知名抛 ValueError → 返回 400
- 实际读 `result/signals/{output_subdir}/signals_latest.csv`
- 注册表内 v1 → output_subdir='v1'，v2 → output_subdir='v2'

### C.3 cron 选择
**calc_signals.py 默认只跑 v1**（line 372 `default=DEFAULT_STRATEGY_VERSION`）。要跑 v2 必须显式 `--strategy-version v2`。
**evening_pipeline.sh 既不调 calc_signals.py 也不调 sim_trader.py**——也就是说**v1/v2 信号根本没在流水线上自动产生**！

MAINTENANCE.md 第 117 行说"19:30 信号计算 calc_signals.py（v1+v2）"，但 evening_pipeline.sh 里没有这一步；需要靠系统 cron（不在 git 里）调。要核实服务器上是否有 cron 实际触发。

## D. 卖信号定义（重点）

calc_signals.py:277-364 `generate_sell_signals()`：
1. 读 `portfolio.db` SIM 账户
2. 取账户绑定的策略（take_profit=0.20 / stop_loss=0.08 默认）
3. 遍历持仓
4. 用 `score_price_history.csv` 当天 `close_price` 比对持仓 `avg_cost`
5. 收益率 ≥ +20% → SELL "止盈"；≤ -8% → SELL "止损"
6. 写入 SELL 行到 signals DataFrame

注意：
- 用的是 score_price_history 的 close_price，与 sim_trader 用的 data/price/{code}.csv K 线**不同数据源**
- 同一个持仓可能在 calc_signals 和 sim_trader 各自触发一次 SELL（双重平仓风险）
- 收益率是相对 avg_cost（可能是多次加仓加权价），而不是 first buy_price
- 假设 score_price_history 当天有 close_price，否则静默跳过（line 323 `if code_data.empty: continue`）

## E. sim_trader 卖信号消化

sim_trader.py:188-231 `check_take_profit_stop_loss()`：
1. 加载 `data/price/{code}.csv` K 线
2. 循环 `[buy_date, end_date]` 每天 K 线
3. high ≥ cost*(1+tp) → 止盈触发；low ≤ cost*(1-sl) → 止损触发
4. 同时触发 → "保守 = 止损优先"
5. 返回触发日 + 目标价（不是 high/low）
6. 通过 `tm.sell(code, sell_price, shares, reason)` 执行

sim_trader.py 不消费 signals_latest.csv 里的 SELL 信号列。它**自己独立**做止盈/止损扫描。

## F. 端点鉴权状态

| 端点 | 鉴权 |
|---|---|
| `GET /api/v1/signals/latest` | 无 verify_token（公开） |
| `GET /api/v1/strategies/versions` | 无（公开） |
| `GET /api/v1/strategies` | 无（公开读） |
| `POST /api/v1/strategies` | verify_token ✓ |
| `PUT /api/v1/strategies/{id}` | verify_token ✓ |
| `DELETE /api/v1/strategies/{id}` | verify_token ✓ |
| `POST /api/v1/portfolio/buy` | verify_token ✓ |
| `POST /api/v1/portfolio/sell` | verify_token ✓ |

signal 信号全是只读 API，没鉴权合理；但**sim_trader 没有任何调用 sell API 的代码路径**——它直接走 `TradingManager.sell()` → DB 写入，跳过 API 层。

## G. 字段一致性

calc_signals.py 写入 signals CSV 字段：
```
date, code, name, close_price, current_score, avg7_score, prev_avg7_score, finance_score, signal
```
SELL 行另带 `sell_reason`（api 不输出，仅 CSV 内部）。

api/main.py:1142-1152 返回字段：
```
date, code, name, close_price, current_score, avg7_score, prev_avg7_score, finance_score, signal
```
✅ 字段对齐。SELL 行的 `current_score/avg7_score/finance_score` 都是空字符串（API 返 None），前端显示 `-`。

Signals.vue 表格列：代码、名称、当前评分、7日均分、财报、收盘价、信号 —— 完全对齐。

## H. 数据文件检查

实际 `result/signals/v1/signals_latest.csv`（30 行采样）：
- 全部为 BUY，无 SELL（持仓模拟仓可能为 0）
- `prev_avg7_score` 列在 v1 全空（v1 不算前 7 日均分对比）
- 包含 `*ST声迅/华幸` —— 风险股也进了 BUY 池，没有 ST 过滤

`result/signals/v2/signals_latest.csv`：
- BUY 列空（按 v2 规则"前 7 日均分首次跨阈值"），都是观望
- prev_avg7_score 列有数据
- ✅ 与 v2 策略逻辑一致（首次突破 = 难得触发）

## I. 与 cron 集成（关键风险）

`scripts/evening_pipeline.sh` line 1-39：**完全不调用 calc_signals.py / sim_trader.py**。
MAINTENANCE.md 第 117 行描述的"19:30 信号计算"是文档承诺，但 git 里没有实现。
实际触发信号靠系统 crontab（README 在 git 外），**用户/审计无法仅通过看 git 仓库判断是否真的跑**。

如果服务器 crontab 里**没有** calc_signals 和 sim_trader 的 cron 项：
- result/signals/v1/signals_latest.csv 是手动生成的
- 模拟仓永远不自动交易
- "实盘策略决策"中的策略决策落不到实操

这是审查阶段需要用户/运维确认的最关键不确定项。

## J. 待办：细节问题

1. sim_trader.py:236 `position_value` 用 `current_price or cost_price` —— 但 DB 里 `current_price` 可能是 None 时会回退 cost_price，造成估值偏离
2. calc_signals.py:436 sell_signals 计数再过滤一次（line 436 `sell_signals = signals_df[signals_df['signal'] == 'SELL']`）—— 没问题
3. calc_signals.py:432-433 `drop_duplicates(subset=['code'], keep='last')` —— 如果一个 code 同时有 BUY 和 SELL，会留下 SELL（last）—— ✅ 合理
4. sim_trader.py:226 cooldown 在 sell 后设置，但 sim_trader 里没用 cooldown 字段（只是 buy_signals 排序时跳过已持仓）—— OK
5. Stats.vue 不显示信号相关图表（仅收益曲线 + 交易统计）—— 设计选择，不是 bug
6. Signals.vue 不显示"前 7 天平均分"曲线（只有当前 avg7_score 数字）—— 用户问题里问到了，**确认：前端没做评分曲线图**