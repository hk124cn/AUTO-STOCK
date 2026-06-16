# 03-回测系统+V2 — 原始审查笔记

## 0. 文件清单（增量对比 2026-06-14）

| 文件 | 行数 | 状态 | 关键变化 |
|------|------|------|---------|
| src/backtest/__init__.py | 14 | 改 | 新增 `STRATEGIES` 导出 |
| src/backtest/data.py | 403 | -1 | 无变化 |
| src/backtest/engine.py | 604 | -1 | 无变化 |
| src/backtest/grid_search.py | 186 | +3 | 新增 `first_break_only/max_pos_pct_basis/build_days` 参数透传 |
| src/backtest/report.py | 368 | -1 | 无变化 |
| src/backtest/scorer.py | 472 | -1 | **A2 仍未修复**（disclosure 兜底仍用 4-30） |
| src/backtest/signal_engine.py | 398 | +62 | 新增 v2 三参数（first_break_only/max_pos_pct_basis/build_days）；补全 2 天建仓逻辑；新增年报评分字段（finance_dicts） |
| **src/backtest/strategies.py** | 101 | **新** | v1/v2 策略注册表（frozen dataclass） |
| scripts/calc_signals.py | 463 | +168 | 新增 v2 首次突破过滤、新增 SELL 信号（generate_sell_signals）、pool 过滤、min_periods、版本注册 |
| scripts/run_backtest.py | 230 | -1 | 无变化 |
| scripts/run_grid_search.py | 75 | -1 | 无变化 |
| scripts/run_launch_backtest.py | 201 | -1 | 无变化 |
| **scripts/run_v2_backtest.py** | 320 | **新** | v2 保守策略回测入口（基于注册表取 v2 参数） |
| scripts/run_signal.py | 108 | -1 | **E1 仍未修复**（仍 import `print_signal_report` / `export_signal_trades`） |
| api/main.py | 1219 | +200+ | 新增 `/api/v1/strategies/versions`、`/api/v1/signals/latest?version=`、DB 策略 CRUD 端点（`/api/v1/strategies`） |

## 1. 上次 P0 修复情况

### A1 (scored 模式前视偏差) — **未修复**
- `engine.py:236-379` `_run_scored` 仍直接 `load_batch_scores(entry_date)`，**用 entry_date 当日 19:00 算出的 batch_result 做决策**
- 证据：grep "load_batch_scores" 在 engine.py:27, 294 仍是当日取
- 修复建议 1（"用 T-1 数据"）未采纳
- 修复建议 2（"主推 live 模式"）未采纳
- 修复建议 3（"明文说明"）未采纳
- **结论：A1 完整未修复，所有 scored 模式回测结果仍含 T 日数据 → 系统性乐观 1-3%**

### A2 (financial_factor 4-30 截止日) — **未修复**
- `scorer.py:397-413` `_conservative_available` 仍是法定截止日 4-30
- 证据：grep 仍是 ddl 4-30 模板
- 修复建议（"用真实公告日"）部分采纳：scorer.py:248-255 **优先**用 `disclosure_map`，只有缺失时才 fallback 到 `_conservative_available`
- 但 fallback 路径仍保留 → 新股票/缺公告日时仍有 4-30 截止日问题
- **结论：A2 部分缓解但未根治；主要财报因子现在用真实公告日，但 fallback 路径仍存在 30 天前视窗口**

### A4 (调仓价用 T 日收盘而非 T+1 开盘) — **未修复**
- `data.py:191-192` `get_forward_return` 仍用 `df.iloc[entry_pos]['收盘']`
- `signal_engine.py:168-182` `get_price` 取 `price_cache.get(date)`，**无 T+1 处理**
- `signal_engine.py:307` 买入价 `bp = get_price(code, date)` 仍用 T 日收盘
- `get_next_trade_day` 函数**已存在** (`data.py:47-55`) 但**未被任何地方使用**
- **结论：A4 完整未修复，隔夜跳空未建模，信号策略 + Top-N 全部高估收益**

### E1 (`print_signal_report`/`export_signal_trades` 未定义) — **未修复**
- `signal_engine.py:1-398` 全文搜索 `def print_signal_report|def export_signal_trades` → 空
- `run_signal.py:74-79` 仍 import 这两个名字
- 实测 `python -c "from src.backtest.signal_engine import print_signal_report"` → `ImportError: cannot import name 'print_signal_report'`
- 既然 v2 引入了新的 `signal_engine.py`，本来是修复 E1 的好机会，但**只补了 v2 业务逻辑，没补报告/导出函数**
- **结论：E1 完整未修复，`run_signal.py` 仍是死脚本**

## 2. V2 策略（新增）审查

### 2.1 入口 scripts/run_v2_backtest.py

**与 V1 区别**：
| 维度 | V1 | V2 |
|------|----|----|
| 买入信号 | 前 7 日均分 ≥ 30（每天判） | 前 7 日均分**首次**跨 30（昨 < 30 ≤ 今） |
| 单只上限基数 | `total_assets × 20%`（浮动） | `capital × 20%`（固定） |
| 建仓节奏 | 一次性打满 | 分 2 天建仓 |
| 首次突破过滤 | False | True |
| max_pos_pct_basis | "total_assets" | "capital" |
| build_days | 1 | 2 |

**是 Top-N 还是信号触发**：信号触发（v2 复用了 SignalEngine）

**同样有 A1/A2/A4 前视偏差问题吗？**
- **A1**：是的。`signal_engine.py:160` `score_dicts = self._precompute_score_dicts(all_scores, trade_dates)`，all_scores 来自 `grid_search.py:36-44` `load_backtest_data` 读取的预计算评分目录（`result/backtest/2024_1385_score/` 等），是历史已算好的，**含 T 日数据**。
- **A2**：是的。`signal_engine.py` 不调 `_calc_finance`（用预计算评分的 finance_score），但预计算评分生成时（即 `precompute_scores`）仍走 `scorer.py` 路径 → A2 仍在。
- **A4**：是的。`signal_engine.py:307` `bp = get_price(code, date)` 仍用 T 日收盘。
- **结论：V2 完整继承 V1 全部 P0 前视偏差，没有任何修正**

### 2.2 V2 新增的 3 个机制

#### 2.2.1 first_break_only（首次突破过滤）

- `signal_engine.py:285-291`：
```python
if cfg.first_break_only and i > 0:
    prev_avg = self._get_avg_score(
        code, i - 1, trade_dates, score_dicts, lookback=7
    )
    if prev_avg is None or prev_avg >= cfg.buy_threshold:
        continue
```
- **正确性**：要求"昨 7 日均分 < 30 且今 ≥ 30"才买
- **问题 1**：和 V1 共用 `_get_avg_score`，边界 `current_idx=2, lookback=7` 仍只取 j=0..1 实际 2 个值 → **有 1 个值也触发**（继承上次 P1 E3）
- **问题 2**：当 `i=0`（首日）整个过滤跳过 → 首日任何 `avg_score >= 30` 都触发买（无昨数据兜底）→ **与"V2 是首次突破"语义矛盾**

#### 2.2.2 max_pos_pct_basis="capital"（按剩余资金计）

- `signal_engine.py:311-314`：
```python
if cfg.max_pos_pct_basis == "capital":
    max_amount = capital * cfg.max_pos_pct / 100
else:
    max_amount = total_assets * cfg.max_pos_pct / 100
```
- **正确性**：实现清晰
- **问题**：和 V1 比，"资本型"会让组合**永远不满仓**（capital 随卖出而涨，但 max_amount 永远按当前 capital）—— 当持仓全涨时，组合实际现金=0 仍按 capital=0 限上限 → **实际上是好的风险控制**
- **无 P0 问题**

#### 2.2.3 build_days=2（分 2 天建仓）

- `signal_engine.py:236-269` 处理已建仓股的剩余仓位补足
- `signal_engine.py:316-318` 处理新候选首日 1/N 仓位
- **正确性**：逻辑分支完整（区分首次建仓 vs 补足）
- **问题 1**：当 `build_days > 1` 时，`pos['target_pos_pct']` 是写死 `cfg.max_pos_pct`（line 335），没考虑后续调仓改 cfg → minor
- **问题 2**：连续多个 build_days 期间，v2 既不检查止盈也不检查止损（因为还没建满，但实际**持仓已存在**）—— 等等，重读代码：line 195-229 检查止盈止损对**所有**持仓遍历，与 build_days 状态无关 → **OK，止盈止损正常**
- **问题 3**：止盈止损触发卖出后，`pos` 被 `del positions[c]`（line 229），但**如果建仓中**（filled_days < build_days），则剩余建仓计划作废——但又没有 `target_pos_pct`/`build_days` 的清理 → minor

## 3. signal_engine.py（新版）

### 3.1 与 calc_signals.py 的关系

- `signal_engine.py`：回测用，模拟历史交易，逐日循环
- `calc_signals.py`：生产用，每日给实盘推送 BUY/SELL 信号
- **两者共享 `Strategy` 注册表**（strategies.py）— 这次的 V2 改动让两者**有了一致的参数源**
- **SELL 信号逻辑只在 calc_signals.py**（`generate_sell_signals`，line 277-364）— signal_engine 没对应 SELL 检查 → **回测和实盘 SELL 路径不一致**

### 3.2 信号计算

**买入（_get_avg_score + first_break_only）**：
- V1：前 7 日均分 ≥ 30 → 买
- V2：前 7 日均分**首次** ≥ 30（昨 < 30）→ 买

**卖出（line 195-229）**：
- 止盈：`ret_pct >= cfg.take_profit` (默认 20%)
- 止损：`ret_pct <= -cfg.stop_loss` (默认 8%)
- 年末平仓：line 346-363（强制清仓）
- **没有"评分跌破阈值"的卖出**（v1/v2 都不靠分数卖，只靠止盈止损）

**资金管理**：
- 单只上限：`max_pos_pct` (20%) × `cfg.max_pos_pct_basis` 基数
- 持仓数：`cfg.max_positions` (10)
- 冷却期：同股卖后 `cooldown_days` 内不再买

## 4. calc_signals.py 增量

### 4.1 +168 行加了什么

| 块 | 行号 | 功能 |
|----|------|------|
| `--strategy-version` 参数 + Strategy 注册 | 34, 371-373, 382, 403-409 | CLI 接受 `--strategy-version v1\|v2` |
| min_periods 修复 | 99-114, 127-128, 151 | 修复"有 1 个值就触发"边界（原 P1 E3 缓解） |
| 股票池过滤 | 142-146, 389-396 | 仅在 stock_self_selected 内出信号 |
| v2 首次突破（line 134-166） | 与 signal_engine 对齐 | first_break_only 实现 |
| sort_col 选择（line 198-199） | v2 用 finance_score 排序 | v1 用 avg7_score |
| SELL 信号 generate_sell_signals | 277-364 | **新增**：检查持仓止盈/止损生成 SELL 行 |
| SELL 合并到输出 | 428-440 | SELL 行覆盖同 code 的 BUY 行 |
| API/注册表 | line 33, 258, 409, 457 | 复用 strategies.STRATEGIES |

### 4.2 重点：SELL 信号怎么定义

- 来源：`PortfolioDB.get_positions(account_id)`（line 306）
- 价格：用 `score_price_history.csv` 的 `close_price`（line 322-326）
- 触发：止盈 (`return_pct >= take_profit`，默认 20%) 或止损 (`return_pct <= -stop_loss`，默认 8%)
- 参数：从 `db.get_strategy(account.strategy_id)` 读（line 298）— **不是**从 `STRATEGIES` 注册表读
- 输出：SELL 行和 BUY 行合并到同一份 `signals_{date}.csv`（line 432-433）

### 4.3 SELL 信号的关键问题

- **Q1**：SELL 价格用 `score_price_history.csv` 的 close_price（当日收盘）→ SELL 信号是"在当天价格上触发了止盈/止损"——但实际 SELL 是在**次日开盘**成交（P4/A4 同样问题）
- **Q2**：SELL 触发了，但**sim_trader 怎么响应？** —— `sim_trader.py` 是否在 `calc_signals.py` 之后读 signals 文件执行卖出？需要查
- **Q3**：如果某持仓不在 score_price_history.csv 中（停牌/无评分），`code_data.empty` → continue → **永不出 SELL 信号**（即使已经暴跌）→ **P1 风险**

## 5. 策略版本切换（用户重点关注）

### 5.1 strategies.py 注册表

- v1：first_break_only=False, max_pos_pct_basis="total_assets", build_days=1
- v2：first_break_only=True, max_pos_pct_basis="capital", build_days=2
- **frozen=True**：注册后不可改
- 注释：加 v3 只改这里（设计意图明确）

### 5.2 api/main.py 的策略 CRUD

**两套并存的策略系统**：

| 系统 | 端点 | 数据源 | 字段 |
|------|------|--------|------|
| **DB 策略** | `/api/v1/strategies` (CRUD) | `portfolio.db.strategies` 表 | buy_threshold, take_profit, stop_loss, cooldown_days, max_position_pct, max_positions, description, is_default |
| **注册表策略** | `/api/v1/strategies/versions` | `STRATEGIES` (strategies.py) | + first_break_only, max_pos_pct_basis, build_days, output_subdir |

**问题 1：DB 策略表**没有 v2 字段（`first_break_only`/`max_pos_pct_basis`/`build_days`）→ **前端切换到"v2"后，DB 取出来的策略参数仍是 V1 默认**（take_profit 20%, stop_loss 8%）

**问题 2：两套系统未互联**：
- `set_account_strategy(req.account_id, req.strategy_id)` 设的是 DB 里的 strategy_id
- `get_strategy(version)` 取的是注册表
- 实际 sim_trader 用 `tm.get_strategy()` 读 DB 策略 → 跟 v1/v2 注册表无关
- 用户在 UI 选"v2"但实际执行的还是 DB 默认参数

**问题 3：注册表 endpoint 没鉴权**（`/api/v1/strategies/versions` 是 GET，无 `verify_token`），但 DB CRUD 都有（OK）

**问题 4：`/api/v1/signals/latest?version=v2`** 需要先运行 `calc_signals.py --strategy-version v2` 生成 `result/signals/v2/signals_*.csv` —— 这没问题，文档也提示了

### 5.3 sim_trader.py 的策略版本支持

- `sim_trader.py:153-157` 接受 `--strategy-version` 参数并 `get_strategy(strategy_version)` 取注册表
- 但**实际执行**用 `tm.get_strategy()`（line 176）— 这是**读 DB 策略**
- **结论：sim_trader 的 --strategy-version 参数和 tm.get_strategy() 是两个独立来源，--strategy-version 仅用于校验 signals 文件路径**

## 6. P0/P1/P2 候选清单

### P0（系统性正确性错误）

1. **A1 仍未修复** — scored 模式仍用 T 日 batch_result → 系统性前视偏差
2. **E1 仍未修复** — `print_signal_report`/`export_signal_trades` 未定义，`run_signal.py` ImportError
3. **A4 仍未修复** — 买入价用 T 日收盘而非 T+1 开盘 → 系统性高估收益
4. **A2 fallback 路径** — 缺公告日时仍用 4-30 截止日 → 部分股票 Q1 数据滞后
5. **V2 首次突破首日盲区** — i=0 时无昨数据，整个 first_break 跳过 → 首日任何 avg≥30 都买

### P1（重要问题）

1. **DB 策略 vs 注册表策略不联通** — UI 选 v2 但实盘跑 V1 默认
2. **SELL 信号永不触发（停牌）** — score_price_history 缺数据时 continue，永不报 SELL
3. **sim_trader 的 --strategy-version 与 tm.get_strategy() 双源** — 实际跑 V1 参数
4. **signal_engine SELL 路径与 calc_signals SELL 路径不一致** — 回测无 SELL（只靠止盈止损），生产有 SELL（generate_sell_signals）
5. **A7 仍在** — `signal_engine.py:307` 买入价当日收盘（同 A4 同一处）

### P2（次要问题）

1. calc_signals.py:217 `cooldown_days * 2` magic number
2. signal_engine.py:217-218 `cooldown_until[code] = i + cfg.cooldown_days` 没考虑重入
3. signal_engine.py:335 `target_pos_pct: cfg.max_pos_pct` 写死（应该按本次建仓时的 cfg）
4. calc_signals.py:432 SELL 合并 `drop_duplicates(subset=['code'], keep='last')` — 当 SELL 是 last 时 OK，但当 BUY 是 last 时会被 SELL 覆盖 → **P1 风险**
5. api/main.py DB StrategyRequest 没 `is_default=1` 唯一性约束
6. V2 README 文档（`result/backtest/v2_首次突破_资金固定_2天建仓/{year}/README.md`）声称"按总评分排序"/"按财报评分排序"——但实际 sort_col 取决于 `first_break_only`，sort_col 选择混在 calc_moving_avg 里 → **不直白**
7. A3 _conservative_available 仍存在但只在 fallback → 修了一半
8. calc_signals.py:155-163 v2 首次突破时无 prev 数据 → continue（V2 拒绝首日交易）— 但 i=0 时也走 prev_window_df is None → 跟 signal_engine.py:285 不一致！

## 7. 总结

### Top-5 本轮发现
1. **【P0】E1 仍未修复** — run_signal.py 仍 ImportError
2. **【P0】A1/A4 完全未修复** — scored 模式前视偏差 + 买入价 T 日收盘，所有回测系统性乐观
3. **【P0】V2 完整继承 V1 前视偏差** — run_v2_backtest.py 没有任何 PIT 修正
4. **【P1】DB 策略与注册表策略不联通** — UI 选 v2 实际跑 V1 默认（take_profit 20%, stop_loss 8%）
5. **【P1】calc_signals 新增 SELL 信号在 score_price_history 缺数据时静默 continue** — 停牌股永远不报 SELL

### 上次 P0 修复状态
| P0 编号 | 主题 | 状态 |
|---------|------|------|
| A1 | scored 模式前视偏差 | ❌ 未修复 |
| A2 | financial_factor 3 季度窗口 | ⚠️ 部分（disclosure 优先，fallback 仍 4-30）|
| A3 | _conservative_available | ❌ 未修复（fallback 路径仍在）|
| A4 | 调仓价 T+1 开盘 | ❌ 未修复 |
| C1 | 停牌等权 | ❌ 未修复（top_n - n_traded 后等权）|
| B1 | scored/live 都用 T 日数据 | ❌ 未修复 |
| E1 | print_signal_report 未定义 | ❌ 未修复 |
| E6 | 信号策略买入价当日收盘 | ❌ 未修复 |

**8 个 P0 全部未修复 / 部分修复**——本轮重点是新增 V2 业务逻辑，**P0 修复被搁置**

### V2 是否同样有前视偏差
**是的，V2 完整继承 V1 全部前视偏差**：
- A1（scored 模式）：V2 用预计算评分（`load_backtest_data` 读 scores_*.csv）→ 含 T 日数据
- A2（财务因子）：V2 用 score 中的 finance_score（来自 precompute_scores）→ fallback 路径仍在
- A4（买入价）：`signal_engine.py:307 bp = get_price(code, date)` 仍用 T 日收盘
- 此外 V2 自身有"首日盲区"新 P0（first_break_only 在 i=0 时跳过）
