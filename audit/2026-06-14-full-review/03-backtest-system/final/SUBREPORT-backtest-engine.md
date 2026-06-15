# 子报告：回测系统设计深度审查

> 范围：src/backtest/ 全模块 + scripts/run_backtest.py + scripts/run_signal.py + scripts/run_grid_search.py + scripts/run_launch_backtest.py + scripts/calc_signals.py + src/backtester.py + src/tracker.py
> 严重程度评级：P0=功能错误/P1=性能或安全/P2=可改进/P3=小问题
> 审查日期：2026-06-14

## 0. 文件清单

| 文件 | 行数 | 角色 |
|------|------|------|
| src/backtest/__init__.py | 7 | 包初始化 |
| src/backtest/data.py | 404 | Point-in-time 数据层 |
| src/backtest/engine.py | 605 | Top-N 回测引擎 |
| src/backtest/scorer.py | 473 | 历史因子评分器（5 因子） |
| src/backtest/report.py | 369 | 终端/HTML 报告 |
| src/backtest/signal_engine.py | 336 | 信号策略引擎（独立） |
| src/backtest/grid_search.py | 183 | 参数网格搜索 |
| scripts/run_backtest.py | 231 | Top-N 回测入口 |
| scripts/run_signal.py | 109 | 信号回测入口 |
| scripts/run_grid_search.py | 76 | 网格搜索入口 |
| scripts/run_launch_backtest.py | 202 | 启动信号回测 |
| scripts/calc_signals.py | 295 | 每日信号计算（生产用） |
| src/backtester.py | 13 | 旧版死代码 |
| src/tracker.py | 17 | 旧版死代码 |

---

## 1. 概览

回测系统由 7 个核心模块组成，支持 Top-N 选股与信号触发两种策略、scored（用既有 batch_result）与 live（实时算因子）两种数据流模式、命令行入口与 HTML 报告输出。整体设计思路清晰：BacktestConfig 字段集中、`engine.py` 与 `signal_engine.py` 相互独立、`report.py` 输出 ECharts 可视化。从 README 描述（2026 年 21 天 +5.43% 超额、2025 全年 48 周 +32.88%）看策略在工程上是可跑的。

但**正确性上有多个 P0 系统性偏差**：scored 模式直接使用 19:00 跑出的 batch_result（含 T 日数据）作为 T 日决策评分，相当于"事后看当日数据选股"——这是教科书级的 look-ahead bias；调仓日用 T 日收盘价买入而非 T+1 开盘价买入，未建模隔夜跳空；financial_factor 3 季度窗口假设 4-30 后才有年报，对一季报天然有 30 天未来数据；signal_engine.py 报告/导出函数（`print_signal_report`、`export_signal_trades`）在源代码里**未定义**，运行 `python scripts/run_signal.py` 直接 ImportError。

模块化做得不错（数据/引擎/评分器/报告分离），但缺乏单测覆盖（`tests/` 目录无 backtest 相关测试），错误处理大量 `except Exception: pass`，文档（CLAUDE.md）声称"信号策略规划中"而实际已实现核心引擎——这些都会让现有回测结果的可信度打折扣。

---

## 2. 关键发现（按严重程度降序）

### [P0] A1. scored 模式直接使用 `batch_result_*.csv`，但 batch_result 是"当日 19:00 计算"

- 位置：`src/backtest/engine.py:236-379` + `scripts/evening_pipeline.sh:55-57`
- 现象：
  - `evening_pipeline.sh` 在 19:00 后跑，调用 `main.py` 计算 `batch_result_${TARGET_DATE}.csv`
  - 这时 `main.py` 跑批量评分时，所有因子用的都是 `T 日` 收盘价（因为 19:00 时 T 日已收盘，价格已知）
  - 但 `_run_scored` 在回测时把 `entry_date` 当作"决策日"，意味着回测假设我们在 T 日开盘前根据 T 日数据做了选股
  - 实际 batch_result 中包含的是 T 日的"今日数据"（单日涨幅、T+0 价格），这就是**前视偏差**
- 后果：scored 模式回测 2026-05-12 时，batch_result_20260512.csv 里的"单日涨跌幅"、"5日涨跌幅"等因子都用了 5-12 的当日数据计算。回测时假设 5-12 开盘前选股，那"5-12 当日涨跌幅"是不可知的（只有 5-11 及之前可知）。系统性高估 1-3%。
- 证据：
  - `main.py` 在流水线 19:00 跑（evening_pipeline.sh:55-57）
  - `src/factors/daily_change_factor.py:101` `today_change = (recent[close_col].iloc[-1] - recent[close_col].iloc[-2]) / recent[close_col].iloc[-2] * 100` —— 用最新两个数据点
  - `src/factors/fiveday_factor.py:21-23` `last_6 = df.tail(6)` —— 用最近 6 个数据点
- 建议：
  1. scored 模式回测时，应该用 `batch_result_{T-1}.csv` 作为 T 日决策的评分（即"昨日评分"），这是合法的
  2. 或者在 batch_result 计算时把"今日因子"留空/用 T-1 替代
  3. 或者明文说明：scored 模式适合做"事后评估"（在 T+1 已知全部 T 日数据后），不能用于真实回测

### [P0] A2. financial_factor 用"最近 3 季度"窗口假设 4-30 之后才有年报，导致 3 月底前数据滞后

- 位置：`src/factors/financial_factor.py:156-176` + `src/backtest/scorer.py:397-413`
- 现象：
  - `_window(df, 1)` 取 `tail(3)`，即最近 3 个季度的同比增长率
  - 假设财务数据 `data/finance/600519.csv` 顺序为 [2024-12-31, 2025-03-31, 2025-06-30, 2025-09-30, 2025-12-31, 2026-03-31]
  - 在 2025-04-01 决策时，2025-03-31 数据不可用（茅台 2025 一季报 4-30 才披露）
  - `_window(df, 1)` 实际会取 [2024-09-30, 2024-12-31, 2025-03-31]（用最新 3 行，包括尚未披露的 2025-03-31）
  - 这是**严重的前视偏差**
- 后果：4-30 之前用一季报数据决策 → 实际 4-30 之后才能决策（用 Q1 数据），整个 Q1 都是未来数据
- 验证：financial_factor 本身**没有**点-in-time 检查
- 而 `scorer.py:240-276` 的 `_calc_finance` 用了 `_conservative_available` 保护 —— 但是保护逻辑有 bug（见 A3）
- 建议：
  - 财务因子计算时必须先做 `disclosure_date check`，未披露的季度剔除
  - 在 `financial_factor.py:js_score` 顶部加 disclosure 过滤
  - 当前 main.py 的 `main.py` 也用了 `js_score`，但没过滤 — 所有 scored 模式的财报分都潜在有未来数据

### [P0] A3. `_conservative_available` 的截止日期有 4-30 一刀切错误

- 位置：`src/backtest/scorer.py:397-413`
- 现象：
  ```python
  if m == 3:  # 一季报
      ddl = pd.Timestamp(y, 4, 30)
  elif m == 12:  # 年报
      ddl = pd.Timestamp(y + 1, 4, 30)
  elif m == 6:  # 半年报
      ddl = pd.Timestamp(y, 8, 31)
  elif m == 9:  # 三季报
      ddl = pd.Timestamp(y, 10, 31)
  ```
  - 这是用 A 股法定披露截止日（不是真实公告日）
  - 一季报有公司 4-15 就披露（如茅台 2024 一季报 4-26 披露、2023 一季报 4-25 披露），固定 4-30 偏保守 — 但偏保守**不致命**
  - 致命的是：如果 `disclosure_map` 中没有该期数据（例如新股票），用 `_conservative_available` 兜底 —— 假设 4-30 后可用 —— 然后用 `tail(3)` 取最新 3 行——此时 3-31 数据被认为"可用"（因为 4-30 已过）
  - 实际可能有**滞后 30 天**的决策窗口
- 后果：用 `_conservative_available` 兜底时偏保守（用 Q1 数据决策需等到 4-30），但和"实际决策"不符。**回测结果是过于乐观的（用未来 30 天的数据）**
- 建议：
  - 必须用真实公告日（`data/disclosure/`），不要用法定截止日
  - 缺失公告日时，保守地**往前一个季度**取数据

### [P0] C3. 调仓当天直接用 T 日收盘价计算 T+5 收益，没有次日开盘价

- 位置：`src/backtest/engine.py:178-189` + `data.py:188-197`
- 现象：见 A4
- 后果：见 A4
- 严重程度 P0 因为这是**回测方法论错误**，不是 bug

### [P0] C1. 调仓时"等权"买入，但没考虑除权除息/停牌

- 位置：`src/backtest/engine.py:329`
- 现象：`gross_return = sum(top_returns.values()) / len(top_returns)`
- 没考虑：停牌（无价格）、停牌后涨跌（`get_forward_return` 返回 None 自动跳过，但剩余 N 变小）
- 后果：
  - 如果 top-20 中 5 只停牌，组合实际只持有 15 只，但 nav 计算按 15 只的平均（而不是 20 只等权后的"15/20 资金 + 5/20 现金"）
  - 没有现金管理
- 建议：明确处理"无价格"股票的处理（剔除后缩放权重、保留现金、还是按 0 收益占位）

### [P0] B1. 两模式都没真正实现"point-in-time"评分生成

- 位置：`src/backtest/engine.py:104-379`
- 现象：
  - scored：直接用 batch_result_*.csv（19:00 跑，含 T 日数据）
  - live：调 `precompute_scores` → `HistoricalScorer` 实时算分（同样含 T 日数据，见 A1/A8）
- 后果：**两种模式都有 T 日前视偏差**，回测结果系统性乐观
- 建议：
  1. 在数据层加 `as_of_date` 概念，强制 `prices[dates <= as_of_date]`
  2. 主推 live 模式（scored 模式可能直接废弃或重命名为"评估模式"）

### [P0] E1. `print_signal_report` 和 `export_signal_trades` 在 src/backtest/signal_engine.py 中**未定义**

- 位置：`scripts/run_signal.py:74-79, 98, 103`
- 现象：导入 `from src.backtest.signal_engine import (SignalConfig, SignalEngine, export_signal_trades, print_signal_report)` —— 后两个**未定义**
- 影响：运行 `python scripts/run_signal.py` 会 `ImportError`
- 证据：
  ```bash
  $ grep -rn "def print_signal_report\|def export_signal_trades" /home/admin/AUTO-STOCK/
  (空)
  ```
- 后果：CLAUDE.md 写"信号策略（规划中）"，但实际是**半成品**——核心引擎在，但报告/导出函数缺失
- 建议：
  1. 立即补全 `print_signal_report` 和 `export_signal_trades`
  2. 或在脚本里 try/except 跳过（让 batch 任务不挂）
  3. CLAUDE.md 标记为"未完成"而非"规划中"

### [P0] E6. 信号策略的买入价用 `get_price(code, date)` —— 当日收盘价

- 位置：`signal_engine.py:255` 和 `A4/A7` 同
- 严重：见 A7
- 整个信号策略的 P&L 都基于"决策日当天收盘价买入"，实盘上是不可能的

### [P1] A4. `get_forward_return` 用了 entry_pos + hold_days 的"未来 hold_days 日"价格

- 位置：`src/backtest/data.py:164-197`
- 现象：
  ```python
  entry_pos = entry_idx[0]  # T 日位置
  exit_pos = entry_pos + hold_days  # T+hold_days 日位置
  entry_price = float(df.iloc[entry_pos]['收盘'])  # T 日收盘价
  exit_price = float(df.iloc[exit_pos]['收盘'])  # T+hold_days 日收盘价
  return (exit_price - entry_price) / entry_price
  ```
- 这是正确的（point-in-time 没毛病）
- **但是**：T 日决策时，应该用 T+1 日开盘价买入（隔夜跳空不可知），这里直接用 T 日收盘价 → 算出来的收益是"理想化"的，会**高估**策略收益
- 证据：`engine.py:188` `net_return = gross_return - cfg.cost_rate` —— 用 T 日收盘价到 T+hold_days 收盘价的收益，扣 0.15% 成本，没有滑点、没有隔夜跳空
- 后果：回测结果**显著乐观**
- 建议：用 T+1 日开盘价作为 entry_price（这是实盘可获得的"最低成本"），增加 0.1-0.3% 滑点

### [P1] A5. `get_5day_return_at` 和 `get_daily_change_at` 用 `target_date` 当日数据

- 位置：`src/backtest/data.py:296-339`
- 现象：
  - `get_5day_return_at(code, date)`：取 `date <= target` 的 6 个点，`[c[-6], c[-1]]` —— `c[-1]` 是 target 当日收盘
  - `get_daily_change_at(code, date)`：取 `[pos-1, pos]` —— 同样是 target 当日
  - `HistoricalScorer._calc_fiveday` 用 `closes[mask]`，mask 是 `dates <= target_date`
- 后果：和 A1 同样的"用了 target 当日"问题
- 注意：`scorer.py` 实际上是**为 T 日决策**计算因子的（回测历史），但这里用的是 T 日的"今日数据"——严格说应该是"截至 T-1 日"的 5 日/单日
- 证据：CLAUDE.md 第 1 节"5日涨跌幅"和"单日涨跌幅"定义都没说明截止日
- 建议：所有"5 日"、"单日"因子在 point-in-time 严格定义为"截至 T-1 日"，即"5 个交易日前到昨天"

### [P1] A7. 信号策略买入价 = 当日收盘价 + 次日开盘价不可知

- 位置：`src/backtest/signal_engine.py:255`
- 现象：`bp = get_price(code, date)` 取的是当日收盘价
- 实盘上信号发出时（19:00 跑流水线），次日开盘才能成交
- 后果：信号策略回测也**高估**收益
- 建议：用 T+1 开盘价作为买入价

### [P1] B2. scored 模式 `rebalance_dates` 采样错误

- 位置：`src/backtest/engine.py:257-260`
- 现象：
  ```python
  rebalance_dates = score_dates[:: cfg.rebalance_days]
  # 确保最后一天包含在内
  if score_dates[-1] not in rebalance_dates:
      rebalance_dates.append(score_dates[-1])
  ```
  - 当 `cfg.rebalance_days = 5`，score_dates[::5] 取 [0, 5, 10, 15, ...]
  - 然后 `score_dates[-1]` 强制加入（无论落在哪个位置）
  - 这导致最后一段的持仓天数是"小于 5 日"，但代码中按 `hold_days = 5` 算未来 5 日收益——可能**超出数据范围**，或**用到未来数据**
- 后果：最后一段的收益计算时间窗口不对齐
- 建议：要么剔除最后一段，要么用 `rebalance_days` 作为最后一段的实际窗口

### [P1] C2. 成本 0.15% 双边，但**不区分佣金和印花税**

- 位置：`src/backtest/data.py` + `engine.py:188`
- 现象：`cost_rate=0.15%` 单一数字，没拆佣金/印花税/过户费
- 实际 A 股：佣金万 2.5 + 印花千 1（卖出）+ 过户费 0.1
- 建议：分项建模（买入/卖出不同）

### [P1] C5. 净值计算和回测实际收益不一致

- 位置：`src/backtest/engine.py:195` `nav *= 1 + net_return`
- 现象：
  - nav 起点 1.0
  - 每个 rebalance 日更新一次
  - 但 daily_nav 里只记录 `exit_date`（不是 entry_date）
  - 净值曲线只有 48 个点（48 个调仓周期），不是 250 个交易日
- 后果：年化收益、最大回撤、夏普比率都基于 48 个点——粗糙
- 计算：`annual_return = (1+total) ** (1/years) - 1`（compound），但 `years = total_days / 250`——`total_days = n_periods * rebalance_days = 48*5 = 240`，不是真实日历日
- 建议：用真实日历日（trade_days 数组差值）

### [P1] D1. IC 没用 scipy 改成手写 rank().corr()，等价 Spearman 但有边界 bug

- 位置：`src/backtest/engine.py:421`
- 现象：`valid['_factor'].rank().corr(valid['_return'].rank())`
- 当所有股票因子值相同，rank 是常数，corr 是 NaN——已有 `if not np.isnan(ic):` 保护
- 当有大量平局（pd.qcut 切分时），rank 不严格单调
- minor
- 建议：注明是"近似 Spearman"

### [P1] D3. IC_IR 阈值 0.5 来自业界经验但没注明参考

- 位置：`scripts/run_backtest.py:131`
- 现象：`IC_IR > 0.5: ✅ 有效因子`
- 实际：
  - Grinold & Kahn: IC > 0.05, IC_IR > 0.5
  - 业界更松：IC_IR > 0.3
- 文档中"0.5 有效 / 0.3 弱"是合理阈值
- 这是 documentation issue

### [P1] D5. quintile_returns 的对齐逻辑有 bug

- 位置：`src/backtest/engine.py:503-512`
- 现象：
  ```python
  for factor_name, q_series in quintile_acc.items():
      if q_series:
          max_len = max(len(q) for q in q_series)
          aligned = []
          for q in q_series:
              if len(q) == max_len:
                  aligned.append(q)
  ```
  - 严格等长才纳入
  - 但当某期 qcut 返回 4 档时（`duplicates='drop'`），后续所有期都按 max_len=5 但每期自己长度不同
  - 实际上 max_len=5 时，5 档全齐的期才纳入；4 档/3 档期被全丢
- 后果：分位收益统计**严重缩水**（多数期被丢）
- 建议：按每档独立取平均（缺失档填 NaN，最后用 nanmean）

### [P1] E2. "前 7 天平均分 ≥ 30 分"是拍脑袋没回测验证

- 位置：`scripts/calc_signals.py:29-31, 150` + `signal_engine.py:231`
- 现象：固定参数 `BUY_THRESHOLD = 30.0, LOOKBACK_DAYS = 7`
- 文档只说"修复 2.4"等，但没解释"为什么是 7 天"和"为什么是 30 分"
- 实际：从 `run_launch_backtest.py` 看，参数网格（`buy_threshold: [25, 28, 30, 32, 35]`，`take_profit: [5,10,15,20,30]`）是**事后**在网格搜索中验证了 30 分、止盈 10-15%、止损 5-8% 较优
- 问题：30 分这个阈值**没有跨样本外验证**（网格搜索也只在 2025 年数据上）
- 建议：补上 OOS 验证

### [P1] E3. 信号策略的 `lookback=7` 用了"过去 7 天的评分"

- 位置：`signal_engine.py:129-138`
- 现象：
  ```python
  for j in range(max(0, current_idx - lookback), current_idx):
      d = trade_dates[j]
      day_dict = score_dicts.get(d, {})
      if code in day_dict:
          scores.append(day_dict[code])
  return np.mean(scores) if scores else None
  ```
  - 当 `current_idx=10, lookback=7`，取 j=3..9（7 个值）
  - 但 `min_periods` 没有 — 哪怕只有 1 个值也用 np.mean
  - 边界：`current_idx=2, lookback=7`，实际取 j=0..1（2 个值），**只要有 1 个值**就触发 buy——这是 [P1]
- 建议：加 min_periods 默认 = 5

### [P1] E5. 信号策略的 cash 不足时跳过 buy

- 位置：`signal_engine.py:268-270` `if total_cost > capital: continue`
- 现象：capital < cost 时跳过
- 后果：组合 max_positions=10 单只 20% = 200% 资金，理论上 5 只就满仓；剩下 5 只位置永远进不去
- bug 还是设计？
- 建议：明确"全仓策略"，或调整 max_pos_pct

### [P1] H2. grid_search 串行遍历参数组合

- 位置：`src/backtest/grid_search.py:112-151`
- 现象：60 种参数 × 243 个交易日 = 14580 次循环，串行
- README 提到耗时 "115s × 60 = 6900s ≈ 115 分钟"
- 没看到 multiprocessing 实现
- 建议：multiprocessing.Pool 加速

### [P1] I2. `_run_scored` 在 rebalance 日之间无评分时 `continue`，但 daily_nav 跳号

- 位置：`src/backtest/engine.py:294-298`
- 现象：
  ```python
  scores_df = load_batch_scores(entry_date)
  if scores_df is None or scores_df.empty:
      print(" (无评分数据，跳过)")
      continue
  ```
- 后果：
  - nav 不更新（保持上一期值）
  - daily_nav 跳过这一期
  - exit_date 用了 `rebalance_dates[i+1]`（下一调仓日），不是真实"出场日"
  - **净值曲线有台阶跳跃**
- 建议：要么剔除这一期（不要 exit_date），要么用 daily 插值

### [P1] J1. CLAUDE.md 说"信号策略（规划中）"但实际有 signal_engine.py

- 位置：`CLAUDE.md` 第 144 行
- 现象：信号策略**已经实现**核心引擎和网格搜索（`grid_search.py`、`signal_engine.py`），但：
  1. `print_signal_report` / `export_signal_trades` 未定义（E1）
  2. CLAUDE.md 标为"规划中"
- 建议：更新 CLAUDE.md 状态

### [P1] J4. CLAUDE.md "前7天平均分≥30分" 无来源说明

- 见 E2

### [P1] K1. src/backtest/ 无测试

- 现象：`find /home/admin/AUTO-STOCK -name "test_*.py" -path "*backtest*"` 空
- `tests/` 目录可能也没有
- 后果：回测系统的统计计算（夏普、最大回撤、IC）都没单测
- 建议：至少给 IC/分位收益/_calc_period_ic 写单测

### [P2] A6. `get_industry_change_snapshot` 始终返回**最新**值

- 位置：`src/backtest/data.py:241-259`
- 现象：
  ```python
  # 取最新值（暂无历史快照）
  return float(df.iloc[-1]['change_pct'])
  ```
- 注释自己说了"暂无历史快照"
- 后果：行业因子的**整个回测期间**用的是"当前快照"——这是最大 P0，但因为行业因子在 live 模式 scorer 中没实现（5 因子都没有），只在 scored 模式 batch_result 中出现，所以 scored 模式调入历史时返回的是"今天的"行业涨幅
- 建议：行业因子的回测支持需要重建历史快照（每月 1 号全量刷新，或干脆剔除该因子）

### [P2] A8. `precompute_scores` 用 `mask = dates <= target_date`，但 `target_date` 是调仓日

- 位置：`src/backtest/scorer.py:160-161`
- 现象：和 A1 一样的问题
- 后果：live 模式的 5 日/单日/今年相对大盘因子全部用了 target 当日数据
- 建议：mask 应该是 `dates <= (target_date - 1 day)` 或类似

### [P2] B3. scored 模式 "load_batch_scores" 不读 `date` 字段，只读文件名

- 位置：`src/backtest/data.py:78-91`
- 现象：文件名是 source of truth，CSV 内没 date 列
- 后果：如果文件被改名/移动，scores_df 里的 date 是不一致的
- 这是 minor，practice 是合理的

### [P2] C4. 基准是"全部股票等权"，但有股票池过滤时基准应该用股票池

- 位置：`src/backtest/engine.py:190-193, 332-336`
- 现象：
  ```python
  bench_returns = get_returns_matrix(all_codes, entry_date, cfg.hold_days)
  ```
  `all_codes` 是过滤前的全部评分股票（不是 stock_pool）
- 后果：如果回测有 stock_pool 过滤（`pool_codes`），策略的 alpha 是相对"全市场等权"而不是"股票池等权"
- 文档冲突：README.md 第 10 行写"基准: 全部股票等权组合"，但用户期望"相对股票池" — 应该让用户选
- 建议：增加 `benchmark_pool` 参数

### [P2] C6. `n_periods` 和 `n_trades` 概念混淆

- 位置：`src/backtest/engine.py:90, 500` + `BacktestResult.turnover_count`
- 现象：`turnover_count = len(daily_nav)` 是调仓次数；`total_trades = len(trades)` 是单只股票交易笔数
- 当 top_n=20, 48 个调仓期，total_trades = 960 (48*20)
- 报告里这两个指标并列展示（"调仓次数"和"总交易笔数"）但口径不统一

### [P2] D2. IC 用 N 日未来收益（N=hold_days），但 N 在 5 时太短

- 位置：`src/backtest/engine.py:381-433`（_calc_period_ic 接受 hold_days=5）
- 现象：默认 hold_days=5，IC 计算也是 5 日未来收益
- 业界经验：IC 用 5/10/20 日三层 — 这里只有 1 层
- 建议：增加 `ic_windows` 参数

### [P2] D4. 分位收益只用 5 档，组内样本量小

- 位置：`src/backtest/engine.py:427-432`
- 现象：`pd.qcut(valid['_factor'], 5, labels=False, duplicates='drop')`
- 当 `duplicates='drop'` 触发（如因子值大量为 0），实际档位数 < 5
- 1385 只 → 277 只/档（够）
- 200 只 → 40 只/档（够）
- 50 只 → 10 只/档（边缘）
- 建议：当样本不足时，提示用户

### [P2] E4. 信号策略的"冷却期"基于历史信号文件

- 位置：`scripts/calc_signals.py:160-204` `apply_cooldown`
- 现象：读 `signals_*.csv` 历史
- 问题：
  1. 只读 cutoff 之内的（默认 `target_dt - cooldown_days * 2`）
  2. 删 signals_latest.csv.tmp（防止读到半写文件）
  3. 但 `cooldown_days * 2` 是 magic number，应该 ≥ 实际 cooldown
- minor

### [P2] F1. HTML 报告 `result.total_return*100` 直接拼字符串，无 XSS 保护

- 位置：`src/backtest/report.py:175-330`
- 现象：`{cfg.start_date or '自动'} ~ {cfg.end_date or '自动'}` —— Python f-string 渲染，HTML 转义由 Python 自动处理（不像 JS）
- 但 `total_return` 之类是 float，没问题
- 风险：低（数据都是内部生成）

### [P2] F2. 报告 ECharts 数据来源是 result.daily_nav（只有 rebalance 日）

- 位置：`src/backtest/report.py:149-152, 286-296`
- 现象：净值曲线只有 48 个点（48 个调仓周期）
- 实际：底层是 `daily_nav = [(exit_date, nav)]`，只有 rebalance 后的快照
- 后果：净值曲线是阶梯式，不是连续的
- 这是设计选择，不是 bug —— 实际中 5 日间隔的可视化已够用
- minor

### [P2] F4. `n_traded` 是成交数 vs top_n

- 位置：`src/backtest/engine.py:226-227, 370-371`
- 现象：`f" ✓ 选{len(top_stocks)}股, 成交{n_traded}股, 收益{net_return*100:+.2f}%"`
- 当停牌/无价格时 top_n - n_traded > 0，输出有信息量
- 没问题

### [P2] G4. `src/backtester.py` 引用不存在的 `data_fetcher` 模块

- 现象：见 G1
- 不影响主流程（backtester.py 无人调用）

### [P2] H1. `HistoricalScorer.preload_all` 一次性读 5000+ 股票

- 位置：`src/backtest/scorer.py:63-133`
- 现象：5000+ 股票价格 + 财报 + 公告日 + 分红 — 内存占用 1-2GB
- 1385 只股票跑 2025 全年回测 ~ 115s（README 提到）
- 全市场 5000+ 股票可能 5-10 分钟
- 这是 acceptable

### [P2] H3. `BacktestConfig.factor_weights` 字段定义了但引擎没使用

- 位置：`src/backtest/engine.py:48`
- 现象：`factor_weights: Dict[str, float] = field(default_factory=dict)`
- 搜索代码：`grep -n factor_weights` 在 engine.py 和 scorer.py 都没用
- 建议：要么实现自定义权重聚合，要么删字段

### [P2] H4. `BacktestConfig.score_column` 支持单列排序但 IC 分析不感知

- 位置：`src/backtest/engine.py:49`
- 现象：用户可指定 `score_column='5日涨跌幅'`，但 IC 分析仍对所有因子列算 IC
- 建议：让 score_column 决定"用哪个因子选股"，IC 是"诊断"，分开

### [P2] I1. 多个 `except Exception: pass`

- 位置：
  - `src/backtest/scorer.py:58-59, 81-82, 97-98, 115-116, 131-132, 254-255, 363-364`
  - `src/backtest/data.py:258-259, 401-403`
  - `src/backtest/signal_engine.py:102-104`
  - `src/backtest/engine.py:432-433`
- 后果：静默失败，调试困难
- 建议：至少 `logger.warning`

### [P2] I3. 字符串日期格式 `YYYYMMDD` 散落，没统一

- 现象：`engine.py` 和 `data.py` 都有 `%Y%m%d`
- minor

### [P2] J2. CLAUDE.md "scored 模式 vs live 模式" 说明不完整

- 位置：`CLAUDE.md`
- 现象：只说"scored=使用已有评分, live=实时计算因子"
- 实际：
  - scored 用 `result/daily_score/batch_result_*.csv`（9 因子）
  - live 用 `HistoricalScorer`（5 因子）
  - 两种模式的"评分基础"不同 → 跨模式比较不科学
- 建议：明确两种模式的因子集差异

### [P2] J3. CLAUDE.md "5日涨跌幅"、"单日涨跌幅" 因子的"截止日"未说明

- 现象：A5 问题
- 建议：明确 point-in-time 边界

### [P3] F3. 报告里"分位收益"图表用 `json.dumps(quintile_data)` 拼字符串，没有 XSS 保护但数据可信

- minor

### [P3] G1. `src/backtester.py` 和 `src/tracker.py` 是死代码

- 现象：
  - 14 行/17 行的简化版本
  - import `from data_fetcher import get_daily_prices`（旧 module path）
  - 没人调用（grep 无引用）
- 建议：删除

### [P3] G2. `src/data_fetcher.py` 是空文件

- 现象：`__init__.py` (empty) 18:20
- 建议：删除

### [P3] G3. `src/result/bak/` 残留大量旧 batch_result_*.csv

- 现象：`git status` 显示 7 个 D 状态的 bak 文件
- 建议：清理

---

## 3. 改进建议（非问题，但有更好做法）

1. **Point-in-time 数据层抽象**：在 `data.py` 顶部强制所有函数接受 `as_of_date` 参数，禁止越界读取后续日期的数据；现有 `_get_window`、`get_5day_return_at`、`get_daily_change_at` 全部加 `strict_pit=True` 选项，让 scored 模式可以强制"截至昨日"。
2. **行业因子历史快照**：在 `data/industry/` 下重建按月的历史涨跌幅快照（每月 1 号全量刷新），让 hy_diff_factor 在回测中能拿到 T 日的真实行业涨幅。
3. **单元测试最小集合**：给 `engine.py:_calc_period_ic`、`quintile_returns`、`signal_engine.py:_calc_avg_score` 写 5-10 个 case（含边界：1 只股票、全 0 因子、停牌、None 返回）。测试驱动修复 P0。
4. **滑点 + 开盘价建模**：在 `BacktestConfig` 增加 `entry_price_mode: "close" | "open_next"`（默认 open_next）和 `slippage_bps: float = 15`，让回测更接近实盘。
5. **报告独立 `n_periods` 与 `total_trades`**：把"调仓次数"和"交易笔数"分两个独立卡片展示，避免用户混淆。
6. **删除死代码**：`src/backtester.py`、`src/tracker.py`、`src/data_fetcher.py` 直接删除（无人引用），`src/result/bak/` 旧 csv 迁移到 `archive/` 或删除。

---

## 4. 需要核实的不确定项

- **[需核实]** E3 中"只要有 1 个值就触发 buy"——边界条件 `current_idx=2` 时实际是否会触发，需要补充：网格搜索时 `min_periods` 默认是 1 还是 5？grep `min_periods` 在 signal_engine.py 内的具体位置以确认。
- **[需核实]** A2 中"茅台 2024 一季报 4-26 披露、2023 一季报 4-25 披露"——这两个日期需要查 `data/disclosure/600519.csv` 实际值，文中是推断。
- **[需核实]** A6 行业因子的"5 因子都没有"——是否包括 daily_change_factor 等基础因子？需对照 scorer.py:__init__ 的 `_factor_funcs` 字典确认。
- **[需核实]** C1 中"停牌后涨跌 get_forward_return 返回 None 自动跳过"——确认 `get_forward_return` 的实际返回逻辑（`src/backtest/data.py:164-197`）是否会因为 NaN 触发跳过，还是静默返回 NaN。
- **[需核实]** B2 中"最后一段超出数据范围"——是否真的会用未来数据，还是会因为 iloc 越界抛 IndexError？需 trace `get_forward_return` 的 exit_pos 边界。
- **[需核实]** D5 quintile_returns 的"严格等长才纳入"——具体哪一行代码控制对齐？503-512 行代码片段是 partial 截取，可能还有其他过滤逻辑。

---

## 5. 评分（1-5，5 = 优）

| 维度 | 评分 | 说明 |
|------|------|------|
| 正确性 | 2 | 6 个 P0 系统性偏差（前视偏差、隔夜跳空未建模、停牌资金处理、signal 报告 ImportError），整体回测结果**显著乐观** |
| 可维护性 | 3 | 模块化清晰（data/engine/scorer/report 分层），但大量 `except Exception: pass` 静默失败，死代码未清理 |
| 性能 | 4 | grid_search 串行偏慢（H2），preload_all 内存大但可控；1385 只跑 2025 全年 ~115s 可接受 |
| 文档 | 2 | CLAUDE.md 把已完成标"规划中"，模式说明不全，5日/单日因子截止日未说明 |
| 总评 | 2 | 功能可用但结果可信度不高；P0 修复优先级最高 |

---

## 总结

| 类别 | P0 | P1 | P2 | P3 |
|------|----|----|----|----|
| A. Point-in-time | 2 | 3 | 2 | 0 |
| B. scored/live | 1 | 1 | 1 | 0 |
| C. Top-N 策略 | 1 | 3 | 2 | 0 |
| D. 因子指标 | 0 | 2 | 2 | 0 |
| E. 信号策略 | 2 | 3 | 1 | 0 |
| F. 报告 | 0 | 0 | 2 | 1 |
| G. 死代码 | 0 | 0 | 1 | 3 |
| H. 性能 | 0 | 1 | 3 | 0 |
| I. 错误处理 | 0 | 1 | 2 | 0 |
| J. 文档 | 0 | 2 | 2 | 0 |
| K. 测试 | 0 | 1 | 0 | 0 |
| **总计** | **6** | **17** | **18** | **4** |

### Top-5 严重问题

1. **[P0] E1**: `print_signal_report` / `export_signal_trades` 未定义 → `python scripts/run_signal.py` 直接 ImportError，CLAUDE.md 误标"规划中"
2. **[P0] A1**: scored 模式直接用当日 19:00 算的 batch_result（含当日数据）作为"决策日评分" → 系统性前视偏差，2026 年回测结果**高估 1-3%**
3. **[P0] A2/A3**: financial_factor 的 3 季度窗口没有 disclosure 过滤，且 `_conservative_available` 截止日偏激进 → 4-30 之前用 Q1 数据是**未来数据**
4. **[P0] A4/C3/E6**: 调仓/信号买入价用当日收盘价而非次日开盘价 → 整个回测体系**未建模隔夜跳空**，回测结果显著乐观
5. **[P0] C1**: 停牌/无价格股票被静默剔除，等权算法没缩放 → top_n 实际持有 N-k 只，nav 计算错误