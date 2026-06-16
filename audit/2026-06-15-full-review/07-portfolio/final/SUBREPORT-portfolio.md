# 子报告：持仓管理 + 信号系统（#7）

> 范围：`src/portfolio/`（database.py、trading.py、__init__.py）、`scripts/calc_signals.py`、`scripts/sim_trader.py`、`scripts/stock_analysis.py`、`api/main.py` 持仓端点、`data/portfolio.db` 实际 schema、`web/stock-system/src/views/Portfolio.vue`
> 严重程度评级：P0=功能错误 / P1=性能或安全 / P2=可改进 / P3=小问题
> 审查日期：2026-06-16

## 1. 概览

持仓管理模块本轮核心观察：**上一轮 6 个 P0 中仅 1 个修复**（SELL 信号集成），其余 5 个原封不动再次出现，**最严重的 schema 漂移（`accounts.strategy_id`）用 ctypes 直查实 DB 仍报 `no such column`**。换言之：本轮并未对持仓端做实质修复，主要是给信号系统加了 SELL 集成（`generate_sell_signals`），并补齐了 strategies 表相关的 API/CLI 路由（信号策略版本注册表 `v1/v2` 独立工作）。

整体结构是好的：单事务 buy/sell、FIFO 配对 + 双账本（positions + trade_lots）、WAL 模式 + busy_timeout、A 股规则常量、API 加 token 鉴权。但 **DB schema 不迁移 = 任何引用 `account['strategy_id']` 的路径上线即 KeyError** —— 模块已"完成"但**实际跑不通**。`accounts` 表在实测数据库中只有 7 列（id/name/mode/initial_capital/current_capital/created_at/updated_at），没有 strategy_id。

**整体评价：信号侧进步明显（+0.5 档），持仓侧 5 个 P0 仍阻塞实盘/重启用 sim_trader；本轮净评分与上次持平。**

## 2. 关键发现（按严重程度降序）

### [P0] `accounts.strategy_id` schema 漂移仍未修复
- 位置：`/home/admin/AUTO-STOCK/src/portfolio/database.py:74`（代码定义 8 列） vs 实际 `data/portfolio.db`（7 列）
- 现象：上一轮已发现此问题；本轮复查代码已就位（`set_account_strategy` L264-268、`get_strategy` L88-93 trading.py、API 端点 api/main.py:1027-1034），但**没有 ALTER TABLE 迁移**，导致实际 DB 仍只有 7 列。
- 后果：所有引用 `account['strategy_id']` 的代码**会 KeyError**：
  - `trading.py:88-93 get_strategy`：`if not account.get('strategy_id')` 走 else（默认策略，**不会 KeyError**——但若账户绑定到非默认策略就拿不到）
  - `api/main.py:1032 set_account_strategy`：`UPDATE accounts SET strategy_id = ?` 直接 SQL 错误
  - `calc_signals.py:298 generate_sell_signals`：`sim_account.get('strategy_id')` → `None` → fallback default strategy（**功能降级但不会崩**）
  - `trading.py:64-76 _ensure_account`：`create_account(..., strategy_id=default_strategy_id)` → INSERT 失败 `accounts.strategy_id` 列不存在
- 证据（ctypes 直查）：
  ```
  $ PRAGMA table_info(accounts)
  0|id|INTEGER|0|NULL|1
  1|name|TEXT|1|NULL|0
  2|mode|TEXT|1|'SIM'|0
  3|initial_capital|REAL|1|1000000|0
  4|current_capital|REAL|1|1000000|0
  5|created_at|TEXT|1|datetime(...)|0
  6|updated_at|TEXT|1|datetime(...)|0

  $ UPDATE accounts SET strategy_id = 2 WHERE id = 1
  rc: 1 err: no such column: strategy_id
  ```
- 建议（一行 ALTER 即可）：
  ```python
  # _init_db 末尾，CREATE INDEX 之后
  for stmt in [
      "ALTER TABLE accounts ADD COLUMN strategy_id INTEGER",
  ]:
      try: c.execute(stmt)
      except sqlite3.OperationalError: pass  # 已存在
  ```
  或更稳妥：维护 `schema_version` 表，启动时按 `version -> ALTER` 链迁移。

### [P0] 买入资金扣减 TOCTOU 仍未修复
- 位置：`/home/admin/AUTO-STOCK/src/portfolio/trading.py:142-171`（buy 函数）
- 现象：line 142 `account = self.db.get_account(acc_id)` 在事务**外**读 `current_capital`；line 155 `if total_cost > account['current_capital']:` 用旧值；line 167 `new_capital = account['current_capital'] - total_cost` 在事务**内**继续用旧值算写回。**没有用 `current_capital >= ?` 的条件 UPDATE，也没有 `rowcount` 校验**。
- 后果：两个并发 buy 都会读到 `current_capital=1,000,000`，A 扣 800,000、B 扣 800,000，最终 `current_capital = -600,000`（破产）。SQLite WAL 进程间无锁，cron（sim_trader）+ uvicorn worker（API）并发写时**必然触发**。
- 证据：
  ```python
  account = self.db.get_account(acc_id)               # L142: 事务外读
  ...
  if total_cost > account['current_capital']:          # L155: 用旧值
      return {'success': False, 'error': '资金不足'}
  with self.db.transaction() as conn:
      new_capital = account['current_capital'] - total_cost  # L167: 旧值 - cost
      cursor.execute('UPDATE accounts SET current_capital = ? WHERE id = ?', (new_capital, acc_id))
  ```
- 建议：原子条件 UPDATE：
  ```python
  cursor.execute(
      'UPDATE accounts SET current_capital = current_capital - ?, '
      '    updated_at = datetime("now", "localtime") '
      'WHERE id = ? AND current_capital >= ?',
      (total_cost, acc_id, total_cost)
  )
  if cursor.rowcount == 0:
      return {'success': False, 'error': '资金不足'}
  ```

### [P0] `delete_trade` 反转逻辑仍未修复
- 位置：`/home/admin/AUTO-STOCK/src/portfolio/trading.py:582-614`
- 现象：
  - BUY 反转（line 577-586）：`for lot in c.fetchall(): if trade['shares'] <= 0: break; take = min(trade['shares'], lot['buy_shares'] - lot['sell_shares']); c.execute("DELETE FROM trade_lots WHERE id = ?", (lot['id'],))` —— `trade['shares']` **从未递减**，`take` 算完**不累加**，循环退出条件**永真**；每个 lot 都执行 DELETE，**整段全删**。
  - SELL 反转（line 593-610）：同样 `trade['shares']` 不递减，UPDATE 计算的 `new_remaining` 用错配对数据；delete 条件 `new_remaining >= lot['buy_shares']` 永真。
- 后果：调 `delete_trade` 后 trade_lots 数据完全损坏——多删/漏删；positions 设 closed_at 后与 trade_lots 失关联。
- 证据：line 582 `if trade['shares'] <= 0: break` 永远不触发（trade['shares'] 是原 BUY 数量，未变）。
- 建议（统一 FIFO 循环）：
  ```python
  remaining = trade['shares']
  for lot in lots:
      if remaining <= 0: break
      avail = lot['buy_shares'] - lot['sell_shares']
      take = min(remaining, avail)
      new_remaining = avail - take
      if new_remaining == 0:
          c.execute("DELETE FROM trade_lots WHERE id = ?", (lot['id'],))
      else:
          c.execute("UPDATE trade_lots SET remaining_shares = ? WHERE id = ?",
                    (new_remaining, lot['id']))
      remaining -= take
  if remaining > 0:
      return {'success': False, 'error': f'lot 不足，剩余 {remaining} 未撤销'}
  ```

### [P0] 胜率统计仍未扣手续费
- 位置：`/home/admin/AUTO-STOCK/src/portfolio/database.py:488-494`（get_trade_stats）
- 现象：`returns.append((lot['sell_price'] - lot['buy_price']) / lot['buy_price'] * 100)` —— **只算价格差**。
- 后果：0.10% ~ 0.20% 微利交易被统计为 win，实际净亏损；胜率虚高约 5-10%。
- 证据：trade_lots 无 `sell_fee` / `sell_stamp_tax` 列；trading.py:359-365 sell 路径算 commission/stamp_tax 写 trades 但**不回填 trade_lots**。
- 建议：trade_lots 加 `sell_fee` / `sell_stamp_tax` 列，sell 路径同步回填；get_trade_stats 改：
  ```python
  ret = ((lot['sell_price'] * (1 - 0.001) - 2*5/max_amount) - lot['buy_price']) / lot['buy_price'] * 100
  ```
  或用净金额（amount-fee-stamp_tax）。

### [P0] A 股 transfer_fee 仍未实际计算
- 位置：`/home/admin/AUTO-STOCK/src/portfolio/trading.py:22-25`（calc_buy_fee）+ `trading.py:28-38`（calc_sell_fee）+ `database.py:28`（常量定义）
- 现象：`TRANSFER_FEE_RATE = 0.00001` 已定义；`calc_buy_fee` 注释"过户费：仅沪市，简化忽略"——**未实际使用该常量**；sell 同。
- 后果：模拟交易成本低估 0.01%~0.02%（沪市 0.1‱ 双向 / 深市 0.1‱ 单向卖出）。年化收益偏差 ~0.1%。
- 建议：trades 表加 `transfer_fee` 列（已可加，`ADD COLUMN` 不影响老数据）；buy/sell 函数按 code 前缀（6/9 沪市 / 0/3 深市）计算：
  ```python
  def calc_buy_fee(amount, code):
      commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
      transfer = amount * TRANSFER_FEE_RATE if code[0] in '69' else 0
      return round(commission + transfer, 2)
  ```

### [P1] sim_trader `total_assets` 循环内仍未重算
- 位置：`/home/admin/AUTO-STOCK/scripts/sim_trader.py:241-265`
- 现象：line 241 `total_assets = cash + position_value` 在循环**外**算一次；line 263 `if cash <= total_assets * 0.05: break` 在循环**内**用旧值；line 274 `target_amount = total_assets * strategy['max_position_pct']` 同样用旧值。
- 后果：每次成功 buy 后 cash 已减（L286 `cash -= result['total_cost']`），但 `total_assets` 不变——5% 守门和 20% 单股上限都用**首轮**总值，第一只股票按 20% 买，第二只又按 20% 买，最后可能买到 60%+，超策略上限。
- 证据：line 241 算一次后再没更新；cash 局部更新了。
- 建议（移到循环开头）：
  ```python
  for _, row in buy_signals.iterrows():
      cash = tm.get_account()['current_capital']
      positions = tm.get_positions()
      position_value = sum((p.get('current_price') or p['cost_price']) * p['shares'] for p in positions)
      total_assets = cash + position_value
      if cash <= total_assets * 0.05: break
      ...
  ```

### [P1] sim_trader CLI 不暴露 `--strategy-version`
- 位置：`/home/admin/AUTO-STOCK/scripts/sim_trader.py:152`（函数签名有 `strategy_version='v1'` 默认）+ main() L311-316（无对应 argparse）
- 现象：`run_auto_trade` 接受 `strategy_version` 参数，但 main() 的 argparse **没有 `--strategy-version`**，外部调用必须改源码。
- 后果：v2 信号无法用 sim_trader 自动跑通；v1/v2 注册表实际只服务于 calc_signals。
- 建议：
  ```python
  parser.add_argument('--strategy-version', type=str, default='v1',
                      choices=['v1', 'v2'],
                      help='信号策略版本（v1=每日触发 / v2=首次突破）')
  ...
  run_auto_trade(date, dry_run=args.dry_run, mode=args.mode,
                 strategy_version=args.strategy_version)
  ```

### [P1] `sim_trader` 加权成本 vs FIFO 配对不一致
- 位置：`/home/admin/AUTO-STOCK/scripts/sim_trader.py:204`（用 `pos['cost_price']` 加权平均）+ `trading.py:278-325`（sell 用 FIFO trade_lots 配对）
- 现象：检查 TP/SL 用加权平均成本，sell 路径用 FIFO 批次成本——两端基准不同。
- 后果：分批买入时，第一批到 TP 但第二批到 SL，加权平均在 TP-SL 中间，TP 触发后按加权成本计算收益偏低（或偏高），与 FIFO 实际配对盈利不一致。
- 建议：trade_lots 逐 lot 检查 TP/SL（一次卖出可能触发多个 lot），sim_trader 改为遍历 trade_lots 调 `check_take_profit_stop_loss`。

### [P1] 持仓前端不展示 TP/SL 与策略版本
- 位置：`/home/admin/AUTO-STOCK/web/stock-system/src/views/Portfolio.vue:101-138`（持仓表）+ L150-191（交易记录表）
- 现象：持仓表 8 列（代码/名称/数量/成本/现价/盈亏/收益率/操作），**无"目标止盈价"列、无"目标止损价"列、无"策略版本"列**。后端 `trading.py:398-406 get_positions` 已算 `target_take_profit` / `target_stop_loss` —— Vue 未用。
- 后果：用户看不到"该股目标止盈/止损价"——止盈止损靠 K 线自动触达，用户无法在持仓页直接感知。
- 建议：在 <th>中加 "目标止盈" / "目标止损" / "策略" 三列；后端 `get_account_strategy` 已在 `currentStrategy.value`，可绑定到行。

### [P1] sim_trader 双触达未持久化
- 位置：`/home/admin/AUTO-STOCK/scripts/sim_trader.py:217-225`
- 现象：`both_triggered` 仅 print 到 stdout，**不写数据库**；进程退出后丢失。
- 后果：复盘困难，无法统计"同日双触达"频率。
- 建议：trade_lots 加 `events TEXT` JSON 列；`both_triggered` 事件 UPDATE trade_lots。

### [P1] API 持仓端点不验证 `account_id` 与 `mode` 归属
- 位置：`/home/admin/AUTO-STOCK/api/main.py:767-770`（`_get_tm`）+ 持仓 buy/sell/dividend 端点 L824-898
- 现象：传 `mode=REAL, account_id=1`（实际是 SIM 账户）—— `_get_tm` 直接 `TradingManager(account_id=1, mode='REAL')` 创建，**不查 account_id 是否真属于该 mode**。
- 后果：API 鉴权 token 通过后，跨账户读写无法防御（虽然 token 限定了用户，但 mode/account 不一致时数据错位）。
- 建议：`_get_tm` 内查 `db.get_account(account_id)`，校验 `account['mode'] == mode` 否则 400。

### [P1] 净值 NAV 公式分母固定（add_capital 摊薄）
- 位置：`/home/admin/AUTO-STOCK/src/portfolio/trading.py:480`（`nav = total_assets / account['initial_capital']`）
- 现象：中途 `add_capital(+50000)` 后 `initial_capital` 不变，NAV 增长被人为摊薄。
- 后果：纯利被算少；回测 add_capital 场景下曲线失真。
- 建议：accounts 加 `net_contribution REAL` 列，nav 公式改 `(cash + position_value) / (initial_capital + net_contribution)`；`add_capital` 同步累计。

### [P1] 持仓 `current_price=1.0` 默认值污染统计
- 位置：`data/portfolio.db positions 表 id 4-7`（已平仓但 `current_price=1.0`）
- 现象：平仓后 `current_price` 字段没清回 NULL，沿用买入默认值 1.0。
- 后果：`get_stats` 把这些已平仓的 `(current_price or cost_price)` 计算时 `current_price=1.0` 真值非空，分母用 1.0 算出 -99.9% 收益（虽然 closed_at 非 NULL 不进 positions 列表，但 daily_nav 重算时仍可能误用）。
- 建议：sell 路径 trading.py:341-356 平仓时 `UPDATE positions SET current_price = ?` 设为 sell_price（已有）；检查 update_initial_capital 重置时是否也清。

### [P1] `sim_trader` `sim_account` get('strategy_id') 假阳性
- 位置：`/home/admin/AUTO-STOCK/scripts/calc_signals.py:298`（`generate_sell_signals`）
- 现象：`sim_account.get('strategy_id')` 因 `accounts` 表无该列返回 `None`，走 `db.get_default_strategy()` 兜底 —— **silently degrade**。
- 后果：若用户切换账户到非默认策略，SELL 信号仍按默认策略（30/20%/8%）算止盈止损，与持仓实际策略不一致；前端看 Stats 切换策略不生效。
- 建议：get_strategy 缺 strategy_id 时**返回错误而非默认**；或用 SQL `SELECT strategy_id FROM accounts` 显式查（无列会抛错，比静默更安全）。

### [P2] stock_analysis.py 完全不读 portfolio
- 位置：`/home/admin/AUTO-STOCK/scripts/stock_analysis.py` 全文
- 现象：投资建议（L334-343 / L475-486）纯基于 total_score 阈值分级，**不读 portfolio.db**，投资者看不到"我已持仓 X，评分 Y，建议加/减/平"。
- 建议：可选地 `PortfolioDB(mode='SIM').get_positions()`，建议模板加 "持仓状态：X 股 / 成本 ¥Y / 当前收益 Z%"。

### [P2] `calc_signals.apply_cooldown` 读所有历史 CSV
- 位置：`/home/admin/AUTO-STOCK/scripts/calc_signals.py:222`
- 现象：`for f in signals_dir.glob('signals_*.csv')` 读所有每日 CSV。
- 影响：当前 3 文件不大；未来 200+ 文件启动慢。
- 建议：维护 `signals_history.parquet` 索引文件（按 strategy_id 分）。

### [P2] 浮动尾数伪影 `current_capital=14958.2600000001`
- 位置：`data/portfolio.db accounts 表 id=1`
- 现象：反复 buy/sell 加减后浮点尾数累积到 13 位精度。
- 影响：UI 显示 ¥14958.2600000001 不友好；净值算 0.99985226 而不是 0.9999。
- 建议：update_capital / buy / sell 路径最终写库前 `round(new_capital, 2)`；或加数据库 trigger。

### [P2] stock_analysis.py 全市场排名 O(n²)
- 位置：`/home/admin/AUTO-STOCK/scripts/stock_analysis.py:198-200`
- 现象：sort 后 197-199 遍历对每只股票重排。
- 影响：5200 只 × 21 天 = ~110k 次排序，单只分析 5+ 秒。
- 建议：用 `pd.Series.rank()` 一次算。

### [P3] sim_trader get_latest_price 死代码
- 位置：`/home/admin/AUTO-STOCK/scripts/sim_trader.py:145-149`
- 现象：定义但**未使用**。
- 建议：删除。

### [P3] `sim_trader` 卖出后无反向冷却
- 位置：`/home/admin/AUTO-STOCK/scripts/sim_trader.py` 全局
- 现象：止盈/止损卖出后无额外冷却；评分再 ≥30 可立即买入。
- 后果：可能"止损-回升-再买入-再止损"循环。
- 建议：止损后 N 天内同 code 不买入（独立于 cooldown）。

## 3. 改进建议（非问题，但有更好做法）

1. **统一策略版本**：当前"信号策略版本"（`v1/v2` 注册表 in `src/backtest/strategies.py`）和"账户绑定策略"（`strategies` 表 in `accounts.strategy_id`）是两套概念。建议在 sim_trader 启动时优先用账户绑定的策略，CLI 缺省走默认策略。
2. **加 schema_version 表**：避免 `accounts.strategy_id` 这类漂移问题。
3. **FIFO 配对 CTE**：trading.sell 的 FIFO 循环可改为 SQLite CTE 一次查询，O(n) → O(1) 往返。
4. **daily_nav 自动落库**：`sim_trader.py:290 save_snapshot` 应**每次都成功**（目前 2026-06-15 trades 已写但 daily_nav 没新增 — 需排查）。
5. **stock_analysis.py 接 portfolio.db**：CLAUDE.md 提到"投资建议"应感知持仓。
6. **A 股规则集中 constants.py**：MIN_SHARES / COMMISSION_RATE / STAMP_TAX_RATE / TRANSFER_FEE_RATE 已分散在 database.py + 代码内常量。

## 4. 需要核实的不确定项

- **2026-06-15 sim_trader 跑过但 daily_nav 没更新**：trades 15-19 / trade_lots 8-12 已落库（2026-06-15 08:55），daily_nav 仍 3 行（最新 2026-06-12）。是 save_snapshot 期间 portfolio 进程重启？还是 sim_trader 跑的是 `python main.py` 而非 `sim_trader.py`？
- **实盘账户 (id=2) 价格来源**：用户如何录入？CLAUDE.md 未说明。
- **sim_trader 是不是回测的替代品**：从代码看不是，但用户期望是？
- **delete_trade 业务价值**：用户是否真的需要删除交易？若不需要可删函数；需要则重写。

## 5. 评分（1-5，5 = 优）

| 维度 | 上次 | 本次 | 理由 |
|------|------|------|------|
| 正确性 | 2/5 | **2/5** | 5/6 P0 仍未修（schema 漂移、TOCTOU、delete_trade 错位、胜率漏算、transfer_fee 漏算）；SELL 信号是唯一修的 |
| 可维护性 | 3/5 | 3/5 | 模块拆分清晰，API 鉴权 + SELL 集成良好；但双账本维护成本高 |
| 性能 | 3/5 | 3/5 | WAL + busy_timeout 缓解并发；FIFO O(n) 可接受；apply_cooldown 退化未修 |
| 文档 | 2/5 | 2.5/5 | calc_signals docstring 增补了 SELL 段；sim_trader 注释到位；NAV 公式无说明 |
| 总评 | 2.5/5 | **2.5/5** | 持平。SELL 集成 +0.5，schema 漂移未修 -0.5，互相抵消 |

---

**附录：审查统计**

- P0: **5** 个（schema 漂移、TOCTOU、delete_trade 错位、胜率漏算、transfer_fee 漏算）
- P1: **7** 个（total_assets 不重算、CLI 缺 strategy-version、加权 vs FIFO、前端无 TP/SL、双触达未持久、API 缺 account/mode 校验、NAV 摊薄、current_price 1.0 污染、sim_trader strategy_id 静默）
- P2: **4** 个（stock_analysis 不接 portfolio、apply_cooldown 全量读、浮点尾数伪影、O(n²) 排名）
- P3: **2** 个（get_latest_price 死代码、sim_trader 卖出后无冷却）

**Top-3 严重问题**：
1. **`accounts.strategy_id` schema 漂移仍未迁移** — 用 ctypes 直查 `UPDATE accounts SET strategy_id = 2` 返回 `no such column: strategy_id`，所有 set_account_strategy 端点上线即 SQL 错误
2. **TOCTOU 资金竞态仍未修** — buy 函数 `new_capital = account['current_capital'] - total_cost` 在事务内继续用事务外读的旧值；并发场景下 current_capital 会被减成负值
3. **delete_trade 反转错位仍未修** — BUY 反转 `for lot in c.fetchall(): if trade['shares'] <= 0: break` 永真（trade['shares'] 未递减），整段 trade_lots 全删

**SELL 信号集成评价（重点）**：
- `generate_sell_signals` 逻辑合理：读持仓 + 算 return_pct + 触发条件（≥tp / ≤-sl）
- 数据源用 portfolio.db 的 SIM 账户 + score_price_history 当日收盘价
- 与 sim_trader 自己的"按目标价"卖出价不一致 —— sim_trader 卖按 tp/sl 目标价，calc_signals 卖按 close_price
- 实盘账户（mode=REAL）持仓**不参与** SELL 信号生成
- 持仓 `current_price` 字段经常是 1.0（默认） 或 None，return_pct 算式脆弱
- `sim_account.get('strategy_id')` 静默失败（无列 → None → default strategy），非阻塞但策略不生效
- 整体：**信号已通气，但仓位端阻塞下整链路无法验证** —— 持仓 P0 修了 SELL 才真正可用

**上次 P0 修复状态**：
| # | 标题 | 状态 |
|---|------|------|
| 1 | accounts.strategy_id 漂移 | **未修**（用 ctypes 实测确认） |
| 2 | TOCTOU 资金竞态 | **未修**（代码未变） |
| 3 | delete_trade 反转错位 | **未修**（代码未变） |
| 4 | 胜率不扣手续费 | **未修**（get_trade_stats 未变） |
| 5 | transfer_fee 漏算 | **未修**（常量定义但未使用，DB 无列） |
| 6 | 无卖出信号 | **已修**（calc_signals 新增 generate_sell_signals） |

**整体评分：2.5/5** — 信号侧进步（+SELL 集成）但持仓侧 5 个 P0 未修，本轮净评分与上次持平；阻塞实盘/重启用 sim_trader。建议先硬修复 schema 漂移 + TOCTOU + delete_trade，再启用 SELL 信号进入实盘。
