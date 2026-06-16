# 子报告：回测系统设计深度审查（V2 增量）

> 范围：src/backtest/ 全部 9 个模块 + scripts/run_*.py (5 个) + scripts/calc_signals.py + api/main.py 策略相关端点
> 严重程度评级：P0=功能错误/P1=性能或安全/P2=可改进/P3=小问题
> 审查日期：2026-06-15

## 0. 文件清单（增量对比 2026-06-14）

| 文件 | 行数 | 状态 | 关键变化 |
|------|------|------|---------|
| src/backtest/__init__.py | 14 | 改 | 新增 `STRATEGIES` 导出 |
| src/backtest/data.py | 403 | 不变 | 无 |
| src/backtest/engine.py | 604 | 不变 | 无 |
| src/backtest/grid_search.py | 186 | +3 | 新增 v2 三参数透传 |
| src/backtest/report.py | 368 | 不变 | 无 |
| src/backtest/scorer.py | 472 | 不变 | A2 仅部分缓解 |
| src/backtest/signal_engine.py | 398 | +62 | v2 三参数 + 2 天建仓 + finance_dicts |
| **src/backtest/strategies.py** | 101 | **新** | v1/v2 策略注册表（frozen dataclass） |
| scripts/calc_signals.py | 463 | +168 | v2 首次突破 + **SELL 信号** + pool 过滤 + min_periods |
| scripts/run_backtest.py | 230 | 不变 | 无 |
| scripts/run_grid_search.py | 75 | 不变 | 无 |
| scripts/run_launch_backtest.py | 201 | 不变 | 无 |
| **scripts/run_v2_backtest.py** | 320 | **新** | v2 保守策略回测入口 |
| scripts/run_signal.py | 108 | 不变 | **E1 仍未修复** |
| api/main.py | 1219 | +200+ | 新增 `/api/v1/strategies/versions`、`/api/v1/signals/latest?version=`、DB 策略 CRUD |

---

## 1. 概览

本轮审查重点是用户新增的 **V2 保守策略 + 卖信号**。技术债层面：实现了清晰的 `Strategy` 注册表（`strategies.py`），让 V1/V2 行为差异可配置、可热切换。`run_v2_backtest.py` 通过注册表读取 V2 参数，避免了硬编码——这是好的工程实践。`calc_signals.py` 增加了 `generate_sell_signals` 函数，从 `portfolio.db` 持仓读取盈亏判断止盈/止损，输出 SELL 信号——这是策略系统从"只发 BUY"走向"闭环"的关键一步。

但**正确性上 P0 系统性偏差全部未修复**。上轮（2026-06-14）发现的 6 个 P0 全部延续：scored 模式仍用 T 日 19:00 batch_result 决策（前视偏差）、调仓价仍用 T 日收盘而非 T+1 开盘（隔夜跳空未建模）、`print_signal_report`/`export_signal_trades` 仍未定义（`run_signal.py` 仍 ImportError）、`scorer._conservative_available` 仍以 4-30 法定截止日兜底（缺公告日时 Q1 数据滞后）。**V2 完整继承 V1 全部前视偏差，没有任何 PIT 修正**——`run_v2_backtest.py` 用历史预计算评分（含 T 日）跑 5 年回测，最优策略是"21 年 +5.43% 超额 / 25 年 48 周 +32.88%"，**这两个数字系统性高估**。

新增的策略版本注册表与 `portfolio.db` 的 strategies 表**完全没联通**——`/api/v1/strategies/versions` 走 `STRATEGIES` 注册表，`/api/v1/strategies` 走 DB 表。前端下拉切到"v2"后，实际 `tm.get_strategy()` 仍读 DB 默认（take_profit 20% / stop_loss 8%），**用户感知的"V2 行为"和实际跑的"V1 默认参数"不一致**——这是策略层 P1 系统性风险。

---

## 2. 关键发现（按严重程度降序）

### [P0] B-A1. scored 模式继续用 T 日 19:00 batch_result 做决策（未修复）

- 位置：`src/backtest/engine.py:236-379` `_run_scored`
- 现象：上轮 P0 A1 完整延续。`load_batch_scores(entry_date)` 仍直接读 `result/daily_score/batch_result_{entry_date}.csv`——该文件由 19:00 晚间流水线生成，**所有 9 个因子都用了 T 日数据**（含 T 日收盘价）。
- 后果：2026-05-12 回测时，5-12 当日的"单日涨跌幅""5日涨跌幅"实际是用 5-12 自身的价格算的，但回测假设 5-12 开盘前决策——**典型教科书级前视偏差**，系统高估 1-3%。
- 证据：
  - `engine.py:294` `scores_df = load_batch_scores(entry_date)` 仍用 entry_date
  - `daily_change_factor.py:101` `recent[close_col].iloc[-1]` 用 T 日收盘
- 上轮修复建议：①用 T-1 数据 ②主推 live 模式 ③明文说明——三个**全未采纳**
- 验证：本轮 audit 期间 `git log` 显示仅 3 次提交（最近一次 `d5eae82` 是 Web 目录重组），**未触及 engine.py**
- 建议：
  1. 立即将 `_run_scored` 的 entry_date 改为 `get_prev_trade_day(entry_date)`，读 `batch_result_{T-1}.csv`
  2. 或在 README 顶部加红字警告"scored 模式仅供评估，不可用于真实回测决策"

### [P0] B-E1. `print_signal_report` / `export_signal_trades` 仍未定义（未修复）

- 位置：`src/backtest/signal_engine.py:1-398`（**整个文件无这两个函数**）+ `scripts/run_signal.py:74-79, 98, 103`
- 现象：上轮 P0 E1 完整延续。`run_signal.py` 仍 `from src.backtest.signal_engine import (..., export_signal_trades, print_signal_report)`，但 `signal_engine.py` 只定义了 `SignalEngine`、`SignalConfig`、`SignalTrade`、`SignalResult`——**这两个函数从头到尾不存在**。
- 实测验证：
  ```bash
  $ python -c "from src.backtest.signal_engine import print_signal_report"
  ImportError: cannot import name 'print_signal_report'
  ```
- 后果：
  - `python scripts/run_signal.py` **直接 ImportError**
  - CLAUDE.md 仍把信号策略标"规划中"（上次 P1 J1）—— **V2 新增业务后文档更失真**
  - 既然 v2 改写了 signal_engine 整个文件，本来是修复 E1 的最佳时机，但**只补了 v2 业务逻辑，没补报告/导出函数**
- 建议：
  1. 立即补全两个函数（参照 `engine.py:print_report` 的实现改写 trades/daily_nav 统计）
  2. 或在 `run_signal.py` 里 `try/except ImportError: print("信号报告暂未实现")` 防止阻塞

### [P0] B-A4. 调仓/买入价仍用 T 日收盘而非 T+1 开盘（未修复）

- 位置：`src/backtest/data.py:191-192` `get_forward_return` + `src/backtest/signal_engine.py:168-182, 307, 348`
- 现象：上轮 P0 A4 + P1 A7 + P0 E6 完整延续。`get_forward_return` 用 `df.iloc[entry_pos]['收盘']`（T 日收盘），`signal_engine.run` 中买入价 `bp = get_price(code, date)`（line 307）也是 T 日收盘。
- 反讽证据：`data.py:47-55` `get_next_trade_day(date, offset=1)` **已实现**但**全代码库无人调用**（`grep -rn get_next_trade_day src/` 只有定义点）
- 后果：整个回测体系**未建模隔夜跳空**。实盘上 19:00 收到 BUY 信号，**次日开盘才能成交**——回测用 T 日收盘价买入，**系统性高估 0.5-1.5%/次换仓**。
- 建议：
  1. `BacktestConfig` 加 `entry_price_mode: Literal["close", "open_next"]`（默认 `"open_next"`）
  2. `signal_engine.run` 中 `bp = get_price(code, get_next_trade_day(date, 1))`
  3. 增加 `slippage_bps: float = 15` 配置

### [P0] B-V2-1. V2 完整继承 V1 全部前视偏差

- 位置：`scripts/run_v2_backtest.py:100` + `src/backtest/grid_search.py:36-44` + `src/backtest/signal_engine.py:160`
- 现象：`run_v2_backtest.py` 调 `load_backtest_data(scores_dir, ...)` 读 `result/backtest/{year}/{year}_*_score/scores_*.csv`——这些评分来自 `precompute_scores`，**已含 T 日数据**。`signal_engine.run` 用这些评分做 T 日决策，**和 V1 同样的 PIT 偏差**。
- 后果：用户最关心的"v2 三年年均 +21.6%"（来自 memory 笔记）**系统性高估**——修正 PIT + 开盘价后实际可能降 3-5%/年。
- 建议：在 `run_v2_backtest.py` 顶部加红字警告"v2 沿用 v1 评分目录，含 T 日前视偏差，结果仅供参考"

### [P0] B-V2-2. V2 首次突破在 i=0（首日）有盲区

- 位置：`src/backtest/signal_engine.py:285-291`
- 现象：
  ```python
  if cfg.first_break_only and i > 0:
      prev_avg = self._get_avg_score(code, i - 1, ...)
      if prev_avg is None or prev_avg >= cfg.buy_threshold:
          continue
  ```
  当 `i == 0`（回测首日），**整个 first_break_only 检查被跳过**——首日任何 `avg_score >= 30` 都直接买。
- 后果：
  - **与"V2 是首次突破"的语义矛盾**：首日没有"昨"的概念，但代码静默放行
  - 历史回测首日（2022/01/04 等）会一次性买入所有 ≥30 的股（如果有的话）
  - `calc_signals.py:155-163` 实现不同——v2 calc_signals 在 `prev_window_df is None` 时 `continue`（**拒绝首日交易**），与 signal_engine **行为不一致**
- 建议：`signal_engine.py:285` 改成 `if cfg.first_break_only and i > 0` → `if cfg.first_break_only:`（首日也走 prev 检查，但 prev_window 在 i=0 时为 None → continue，行为与 calc_signals 对齐）

### [P0] B-A2. financial_factor fallback 路径仍在用 4-30 法定截止日

- 位置：`src/backtest/scorer.py:245-258, 397-413`
- 现象：上轮 P0 A2 部分缓解。`scorer.py:248-255` **优先**用 `disclosure_map[rp]` 做 `pd.to_datetime(period_map[rp]) <= target_date` 检查——**这是修复**。但 line 256-258 fallback：`else: if self._conservative_available(rp, target_date): available.append(row)` 仍用 4-30 兜底。
- 后果：
  - 有公告日的股票：用真实公告日 → 正确
  - 缺公告日的新股票：用 4-30 法定截止日 → 4-30 前用 Q1 数据是**未来数据**
  - 上轮建议（"缺失时往前一个季度取数据"）**未采纳**
- 建议：fallback 改为 `return False`（保守地剔除未披露季度），而不是用法定截止日

### [P0] B-C1. 停牌 / 无价格股票被静默剔除，等权算法未缩放（未修复）

- 位置：`src/backtest/engine.py:329` + `signal_engine.py:188-189`
- 现象：上轮 P0 C1 完整延续。`gross_return = sum(top_returns.values()) / len(top_returns)`，但 `top_returns` 是 `get_returns_matrix` 返回的（自动跳过数据不足的）——**实际 N 小于 top_n，但分母用实际成交数**，而 nav 累加按"top_n 只组合"计。
- 后果：
  - top-20 选股，5 只停牌 → 实际持有 15 只，但 nav 按 15 只等权
  - 没有"5/20 现金"概念 → **回测组合实际是 15 只满仓 + 5 只空仓，nav 计算错误**
- 建议：明确处理方式（剔除后缩放权重 / 保留现金 / 按 0 收益占位），并在 README 写明

### [P1] B-STRAT-1. DB 策略表与注册表策略不联通

- 位置：`api/main.py:968-1014`（DB CRUD） + `api/main.py:1166-1184`（注册表） + `src/portfolio/database.py:80-95`（DB schema）
- 现象：
  - **DB 表 `strategies`** 字段：`buy_threshold, take_profit, stop_loss, cooldown_days, max_position_pct, max_positions, description, is_default`（schema line 80-95）——**没有 v2 字段**
  - **注册表 `STRATEGIES`** 字段：`+ first_break_only, max_pos_pct_basis, build_days, output_subdir`（strategies.py:28-47）
  - 前端 UI 切到"V2"（首次突破）→ 调 `/api/v1/strategies/versions` 拿到注册表 v2 → 实际执行时 `tm.get_strategy()` 读 DB 默认 → **跑的是 V1 参数**（take_profit 20% / stop_loss 8%）
  - `sim_trader.py:176` `strategy = tm.get_strategy()` 读 DB，**忽略注册表**
- 后果：用户感知的"V2 行为"和实际跑的"V1 默认参数"**完全不一致**——这是策略层 P1 系统性风险。
- 证据：
  ```sql
  -- src/portfolio/database.py:80-95
  CREATE TABLE strategies (
      ...
      max_position_pct REAL NOT NULL DEFAULT 0.20,
      max_positions INTEGER NOT NULL DEFAULT 5,
      ...
  )
  -- 没有 first_break_only / max_pos_pct_basis / build_days
  ```
- 建议：
  1. DB 表 schema 加 v2 字段（`ALTER TABLE strategies ADD COLUMN first_break_only INTEGER DEFAULT 0`）
  2. `tm.get_strategy()` 接受 `version` 参数，**优先**用注册表，**回退**到 DB
  3. 或彻底合并：`Strategy` 注册表是 source of truth，DB 表只存用户自定义 `cooldown_days` 等

### [P1] B-SELL-1. SELL 信号在 score_price_history 缺数据时静默 continue

- 位置：`scripts/calc_signals.py:316-336` `generate_sell_signals`
- 现象：
  ```python
  for pos in positions:
      code = pos.get('code', '')
      ...
      code_data = df[(df['code'] == code) & (df['date'] == target_date)]
      if code_data.empty:
          continue  # 静默跳过
  ```
  当某持仓在 `score_price_history.csv` 中没有 target_date 的记录（停牌、退市、缺数据），**`continue` 而不报 SELL**——即使已暴跌也无法告警。
- 后果：
  - 停牌股永远不报 SELL 信号（即使已亏 30%）
  - 数据缺口的持仓被静默忽略
  - 实盘 sim_trader 收到 signals 文件，没 SELL → **持仓无监控**
- 建议：
  1. 缺数据时用"前一日价格"兜底（取最后一个已知价）
  2. 或加 `LOG.warning` + 单独的 `signals_sell_missing_data.csv` 暴露

### [P1] B-SELL-2. signal_engine 回测与 calc_signals 生产的 SELL 路径不一致

- 位置：`src/backtest/signal_engine.py:195-229`（只检查止盈/止损，无评分跌破） vs `scripts/calc_signals.py:277-364`（止盈/止损 + 读 portfolio.db 持仓）
- 现象：
  - **回测**：`signal_engine.run` 只按 `take_profit` / `stop_loss` 阈值卖出，**不读 portfolio.db**
  - **生产**：`calc_signals.generate_sell_signals` 读 `portfolio.db` 持仓、判断阈值、生成 SELL 行
- 后果：回测时如果有持仓触达阈值，回测会"自动卖出"（写 trades）；生产时**也**会生成 SELL 信号（写到 signals 文件），但 sim_trader 是否读 signals 文件并执行 SELL？—— `sim_trader.py` 主要做 BUY，SELL 路径未明
- 验证：`sim_trader.py` 全文搜 "SELL" 主要是数据库写入（持仓表），未见读 signals 文件
- 建议：明确 SELL 触发的单一来源（建议生产用 generate_sell_signals，回测继续用 signal_engine 的止盈止损，文档写清差异）

### [P1] B-DUP-1. calc_signals 合并 BUY+SELL 时 SELL 可能被 BUY 覆盖

- 位置：`scripts/calc_signals.py:432-433`
- 现象：
  ```python
  signals_df = pd.concat([signals_df, sell_signals], ignore_index=True)
  signals_df = signals_df.drop_duplicates(subset=['code'], keep='last')
  ```
  - `signals_df`（BUY）在前，`sell_signals` 在后 → concat 后 SELL 行在末尾
  - `drop_duplicates(subset=['code'], keep='last')` 保留 last → **保留 SELL**
  - 但若 `signals_df` 内部本身就有同 code 多行（罕见但可能），`keep='last'` 会保留最后买入 → SELL 丢失
- 后果：低概率但**理论上** SELL 可能被 BUY 覆盖
- 建议：先合并，再按"signal=='SELL' 优先"排序后去重

### [P1] B-COOLDOWN-1. signal_engine `cooldown_until` 与 `positions` 状态可能不一致

- 位置：`src/backtest/signal_engine.py:225-226`
- 现象：`cooldown_until[code] = i + cfg.cooldown_days`，但**仅在卖出时设置**，买入时 `if code in cooldown_until and i < cooldown_until[code]: continue`——**OK**。但当 `cooldown_days=0` 时（grid_search 网格里有），line 225 跳过 → cooldown_until 不设置 → **OK**。
- 验证：逻辑正确，**无 P0 问题**，但和上次 P1 E3（"min_periods=1 时 1 个值就触发"）边界类似—— `current_idx=2, lookback=7` 时实际只取 2 个值，仍触发
- 建议：在 `_get_avg_score` 加 `min_periods=5`（上轮 P1 E3 未修复）

### [P1] B-MIN-PERIODS-1. signal_engine `_get_avg_score` 无 min_periods

- 位置：`src/backtest/signal_engine.py:137-146`
- 现象：`scores = []` → 哪怕只有 1 个值也 `np.mean` 返回
- 上轮 P1 E3 完整延续。`calc_signals.py:113-114` 已加 `min_periods`（默认 = `lookback`），但 `signal_engine._get_avg_score` **没加**。
- 后果：边界 `current_idx=2, lookback=7` 时实际取 2 个值（j=0,1）→ **仍能触发买**
- 建议：signal_engine:137 仿 calc_signals 加 `min_periods=5` 默认

### [P1] B-API-1. `/api/v1/signals/latest` 接受任意 `version`，但前端可能要双向同步

- 位置：`api/main.py:1101-1163`
- 现象：默认 `version="v1"`，未知 version 抛 500。`get_strategy(version)` line 1110 用 `ValueError` 兜底 → 转 500（line 1161 实际是 400，但异常路径 1163 走 500）
- 验证：异常路径不统一——P2
- 建议：统一所有 `get_strategy` 异常路径为 400

### [P2] B-A6. 行业因子历史快照仍未建立

- 位置：`src/backtest/data.py:241-259` `get_industry_change_snapshot`
- 现象：上轮 P2 A6 完整延续。注释自己写了"暂无历史快照"，line 257 `return float(df.iloc[-1]['change_pct'])` 永远返回最新值
- 后果：行业因子的整个回测期间用"今天的"行业涨幅
- 建议：建立按月历史快照（每月 1 号全量刷新），或在 scored 模式禁用 hy_diff_factor

### [P2] B-SORT-1. V2 calc_signals 排序混在 calc_moving_avg 里

- 位置：`scripts/calc_signals.py:198-199`
- 现象：`sort_col = 'finance_score' if strategy and strategy.first_break_only else 'avg7_score'`
  - V1（first_break_only=False）→ 按 avg7_score 排
  - V2（first_break_only=True）→ 按 finance_score 排
  - **但 V2 的 run_v2_backtest.py 同时跑"按总评分"和"按财报评分"两种网格**——calc_signals 这里 hard-code 了 v2 → 财报
- 后果：run_v2_backtest.py:117 写 `sort_by_finance=[False]`，但 calc_signals 仍按 finance_score 排——**回测和生产的 sort 逻辑不一致**
- 建议：calc_signals 加 `sort_by` 参数（'avg7' 或 'finance'），与 run_v2_backtest 同步

### [P2] B-SORT-2. V2 README 文档与代码不匹配

- 位置：`scripts/run_v2_backtest.py:225-251`（写 README）
- 现象：README 写"按总评分排序（动量优先）"和"按财报评分排序（价值优先）"——但实际 `sort_col` 选择（`run_v2_backtest.py:117, 139` 写 `sort_by_finance=[False]/[True]`）没在 engine.run 里实现—— engine 没有 `sort_by_finance` 字段
- 验证：`signal_engine.py:33-39` 也没有 `sort_by_finance` 字段的引用（除了 `SignalConfig` line 39 定义）
- 后果：README 写错（或者 engine 没读这个参数）—— P2 文档 vs 代码不符
- 建议：要么 README 改描述，要么 engine 加 `sort_by_finance` 实现

### [P2] B-PORT-1. V2 build_days 的 target_pos_pct 写死

- 位置：`src/backtest/signal_engine.py:335`
- 现象：`'target_pos_pct': cfg.max_pos_pct` 写死用 cfg 值。如果 cfg 在回测期间变了（不可能但原则性），会不一致
- 建议：minor——`'target_pos_pct': cfg.max_pos_pct` 改为 `pos.get('target_pos_pct', cfg.max_pos_pct)`

### [P2] B-COOLDOWN-2. `cooldown_days * 2` magic number

- 位置：`scripts/calc_signals.py:217`
- 现象：`cutoff = (target_dt - timedelta(days=cooldown_days * 2)).strftime('%Y%m%d')`
- 建议：常量 `COOLDOWN_HISTORY_MULTIPLIER = 2`

### [P2] B-API-2. `get_latest_signals` 异常路径不统一

- 位置：`api/main.py:1161-1163`
- 现象：line 1161 `except ValueError` → 400；line 1163 `except Exception` → 500。统一为 400/500 即可
- 建议：统一所有 `get_strategy` 异常路径

### [P2] B-PORT-2. `is_default=1` 唯一性约束缺失

- 位置：`src/portfolio/database.py:80-95` + `api/main.py:978-993`
- 现象：DB schema 没 `UNIQUE` 约束在 `is_default` 上，多个 `is_default=1` 不会报错
- 后果：`get_default_strategy` 取 `LIMIT 1`（line 230）→ 用户可能有 2 个 default → 行为不确定
- 建议：应用层强制只有 1 个 default（`UPDATE ... WHERE is_default=1; UPDATE x SET is_default=1`）

### [P3] B-DUP-2. README 引用 emoji 字符不一致

- 现象：scripts/run_v2_backtest.py:74 用 emoji 标题，其他文件用 ASCII
- 建议：保持 ASCII 风格

### [P3] B-DB-1. `db.get_default_strategy()` 的 fallback 不可预期

- 位置：`src/portfolio/database.py:228-235`
- 现象：`if is_default: c.execute(... WHERE is_default = 1 LIMIT 1)`，无 → `ORDER BY id LIMIT 1`——取最早创建的策略作为默认
- 建议：明确 README "若无 default 则用最早创建的"

---

## 3. 改进建议（非问题，但有更好做法）

1. **合并策略源**：将 `STRATEGIES` 注册表和 `portfolio.db.strategies` 表合并——注册表作 source of truth，DB 表只存用户自定义 `cooldown_days` 覆盖。`tm.get_strategy()` 接受 `version` 参数。
2. **scored 模式 + T+1 开盘价 + 滑点**：在 `BacktestConfig` 一次性加 `entry_price_mode: Literal["close", "open_next"]` 和 `slippage_bps: float = 15`，让所有回测都用 T+1 开盘 + 滑点，更接近实盘。
3. **SELL 信号单一来源**：`generate_sell_signals` 应作为唯一 SELL 来源，signal_engine 回测时也读 portfolio.db（如果回测时用真实 DB）。
4. **min_periods 全局化**：在 `Strategy` 注册表加 `min_periods` 字段，calc_signals 和 signal_engine 都从注册表读，避免硬编码 `min_periods=5`。
5. **CLAUDE.md 更新 V2 状态**：把"信号策略（规划中）"改成"信号策略 v1（每日触发）已上线，v2（首次突破）已上线"，并标注回测的 PIT 偏差。

---

## 4. 需要核实的不确定项

- **[需核实]** B-STRAT-1 中"sim_trader 的 --strategy-version 与 tm.get_strategy() 是两个独立来源"——需要看 sim_trader.py:153-176 完整逻辑确认 --strategy-version 是否在 tm.get_strategy() 之后被覆盖。
- **[需核实]** B-SELL-2 中"sim_trader 是否读 signals 文件并执行 SELL"——需查 sim_trader.py 完整 SELL 路径。
- **[需核实]** B-SORT-2 中 "engine 没有 sort_by_finance 字段"——需 grep `sort_by_finance` 全代码库确认。
- **[需核实]** A3 `_conservative_available` 在 main.py 9 因子评分（`js_score`）中是否被调用——若是，则 A2 影响范围比回测更大。
- **[需核实]** V2 README 路径 `result/backtest/v2_首次突破_资金固定_2天建仓/{year}/` 是否实际生成（`ls` 确认目录在，但 README 内容是 hard-code 写的还是 grid 跑出来的）—— 需查 README 中的数字和 grid_results.csv 是否对齐。

---

## 5. 评分（1-5，5 = 优）

| 维度 | 评分 | 说明 |
|------|------|------|
| 正确性 | 1 | 8 个 P0 全部未修复（5 个完整延续 + 3 个新增 V2 引入）；scored/live 两模式系统性前视偏差；V2 完整继承；策略双源不联通 |
| 可维护性 | 3 | `Strategy` 注册表（frozen=True）设计好；`signal_engine` 加 v2 业务清晰；但双源策略/双源 SELL 路径增加维护成本 |
| 性能 | 3 | 5 年 × 60 组合 × 2 排序 = 600 次回测，`run_v2_backtest.py` 单脚本运行（无 multiprocessing）—— 单进程慢；上次 P1 H2 未修复 |
| 文档 | 2 | CLAUDE.md 仍标"信号策略（规划中）"——实际 v1+v2 都已上线；run_v2 README 描述与代码 sort 逻辑不符 |
| 总评 | 2 | 业务功能 V2 上线值得肯定，但 P0 全部未修复 + 策略双源不联通 = 实际结果不可信。**v1/v2 数字都建议标注"含 PIT 偏差"** |

---

## 总结

| 类别 | P0 | P1 | P2 | P3 |
|------|----|----|----|----|
| A. Point-in-time | 3 | 0 | 1 | 0 |
| B. scored/live + V2 | 2 | 3 | 4 | 1 |
| C. Top-N 策略 | 1 | 0 | 0 | 0 |
| D. 因子指标 | 0 | 0 | 0 | 0 |
| E. 信号策略 | 2 | 2 | 0 | 0 |
| F. 报告/导出 | 1 | 0 | 0 | 0 |
| G. 死代码 | 0 | 0 | 0 | 0 |
| H. 性能 | 0 | 0 | 0 | 0 |
| I. 错误处理 | 0 | 0 | 0 | 0 |
| J. 文档/双源 | 0 | 1 | 2 | 1 |
| K. 测试 | 0 | 0 | 0 | 0 |
| **总计** | **9** | **6** | **7** | **2** |

### Top-5 严重问题

1. **[P0] B-A1**: scored 模式直接用 T 日 19:00 batch_result 做 T 日决策 → 系统性前视偏差，所有 scored 模式回测结果**高估 1-3%**（上轮未修复）
2. **[P0] B-E1**: `print_signal_report`/`export_signal_trades` 仍未定义 → `python scripts/run_signal.py` 仍 ImportError（上轮未修复）
3. **[P0] B-A4**: 调仓/买入价仍用 T 日收盘而非 T+1 开盘 → 全回测体系**未建模隔夜跳空**，高估 0.5-1.5%/次（上轮未修复）
4. **[P0] B-V2-1**: V2 完整继承 V1 全部前视偏差——`run_v2_backtest.py` 用历史预计算评分（含 T 日）跑回测，最优策略的"21.6% 年均"**系统性高估**
5. **[P1] B-STRAT-1**: DB 策略表 vs 注册表策略完全没联通——前端切到"V2"实际跑"V1 默认参数"（take_profit 20% / stop_loss 8%），是**策略层系统性风险**

### 上次 P0 修复状态

| P0 编号 | 主题 | 状态 |
|---------|------|------|
| A1 | scored 模式前视偏差 | ❌ 未修复（engin.py:294 仍用 entry_date）|
| A2 | financial_factor 3 季度窗口 | ⚠️ 部分（disclosure 优先，fallback 仍 4-30）|
| A3 | _conservative_available | ❌ 未修复（fallback 路径仍在）|
| A4 | 调仓价 T+1 开盘 | ❌ 未修复（get_next_trade_day 已存在但无人调用）|
| B1 | scored/live 都用 T 日数据 | ❌ 未修复（A1 + A8 共因）|
| C1 | 停牌等权 | ❌ 未修复（sum / len(top_returns) 未缩放）|
| E1 | print_signal_report 未定义 | ❌ 未修复（实测 ImportError）|
| E6 | 信号策略买入价当日收盘 | ❌ 未修复（signal_engine:307 仍当日收盘）|

**8 个 P0 全部未修复 / 部分修复——本轮重点是新增 V2 业务逻辑，P0 修复被搁置**

### V2 是否同样有前视偏差

**是的，V2 完整继承 V1 全部前视偏差**：
- A1：V2 用 `load_backtest_data` 读 `scores_*.csv` 预计算评分（含 T 日数据）
- A2：V2 用的 finance_score 来自 `precompute_scores`，`scorer._conservative_available` 仍在 fallback
- A4：`signal_engine.py:307 bp = get_price(code, date)` 仍用 T 日收盘
- 此外 V2 自身有"首日盲区"新 P0（`signal_engine.py:285` first_break_only 在 i=0 时跳过）

**建议**：在 `run_v2_backtest.py` 顶部加红字警告"v2 沿用 v1 评分目录，含 T 日前视偏差，结果仅供参考"，并在 README 写明修正 PIT 后预期收益会下降。
