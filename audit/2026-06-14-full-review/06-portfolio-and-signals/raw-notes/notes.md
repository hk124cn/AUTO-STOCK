# 子报告（草稿）：持仓管理与信号

> 审查文件：
> - `/home/admin/AUTO-STOCK/src/portfolio/database.py`（528 行）
> - `/home/admin/AUTO-STOCK/src/portfolio/trading.py`（660 行）
> - `/home/admin/AUTO-STOCK/src/portfolio/__init__.py`
> - `/home/admin/AUTO-STOCK/scripts/calc_signals.py`（295 行）
> - `/home/admin/AUTO-STOCK/scripts/sim_trader.py`（339 行）
> - `/home/admin/AUTO-STOCK/scripts/stock_analysis.py`（579 行）
> - `/home/admin/AUTO-STOCK/api/main.py`（portfolio 端点 757-1014）
> - `data/portfolio.db`（实际 schema）

---

## A. 持仓数据库 (database.py)

### A1. 严重：实盘 DB 缺少 `accounts.strategy_id` 列（**P0**）
- 现象：`data/portfolio.db` 实际只有 7 列（id, name, mode, initial_capital, current_capital, created_at, updated_at），但 `database.py` 的 `_init_db` 在 `accounts` 表中定义了 `strategy_id INTEGER` 列（line 74）。
- 后果：所有依赖 `account['strategy_id']` 的代码（`set_account_strategy` L264、`trading.py:90-93` get_strategy、`sim_trader.py:172` get_strategy、`api/main.py` 策略切换端点）只要先跑过一次 `_init_db`，**对旧 DB 会执行 `CREATE TABLE IF NOT EXISTS`**——SQLite 不会给已存在的表加列，结果 `account['strategy_id']` 抛 `KeyError`，整个持仓模块崩溃。
- 证据：实测 schema（`PRAGMA table_info(accounts)`）显示 7 列无 strategy_id。代码 `accounts.strategy_id` 引用 11+ 处。
- 建议：
  1. 用 `ALTER TABLE accounts ADD COLUMN strategy_id INTEGER` 兼容老 DB
  2. 或加 schema 版本号，检测到不匹配时 `ALTER` + 索引
  3. 在 `_init_db` 后立刻执行兼容性 ALTER

### A2. `add_position` / `trading.buy` 双写持仓+trade_lots（**P1**）
- 现象：同一买入事务中 `add_position` (database.py:305-332) 和 `TradingManager.buy` (trading.py:120-225) 都执行了：
  - SELECT/UPDATE/INSERT positions
  - INSERT trade_lots
  - INSERT trades（仅 trading.py）
- 后果：业务层调 `TradingManager.buy` 是正确路径，但 `PortfolioDB.add_position` 仍被 `trading.add_position` 等老代码引用，可能导致**重复加仓**和**双 trade_lots**。需要 grep 确认。
- 证据：grep `add_position` 见 `sim_trader.py` 不直接调，但 `database.py:add_position` 与 `trading.py:buy` 内联逻辑有重叠。
- 建议：要么在 `PortfolioDB.add_position` 内部去掉 trade_lots/trades 写入（只动 positions），要么删除重复的 `TradingManager.buy` 内联 SQL，统一调 `db.add_position`。

### A3. 净值快照的"重算"风险（**P1**）
- 现象：`save_snapshot` 写 `daily_nav`（`INSERT OR REPLACE`），但 `get_stats`（L413-458）每次实时算 `total_assets = cash + position_value`。
- 后果：
  - 如果隔夜有未更新 `current_price` 的持仓，NAV 用 cost 价计算 → 与实际可变现价值不一致；
  - `get_stats` 是"实时"算而不是从 `daily_nav` 读，导致 Stats 页和历史曲线可能不一致（前端用 `daily_nav`，后端 stats 实时算）。
  - `daily_nav.nav = total_assets / initial_capital` 用了**初始资金**做分母，**不随存取款调整**——`add_capital` 不动 initial_capital 是对的（区别于 `update_initial_capital`），但 `add_capital` 后 NAV 含义变成"相对初始资金 + 净入金"，无文档说明。
- 建议：
  1. `get_stats` 也读 `daily_nav` 最新一行
  2. 加 `net_contribution` 字段跟踪净入金
  3. 文档化 NAV 公式

### A4. `get_trade_stats` SQL 严重错误（**P0**）
- 现象：line 484 `SELECT buy_price, sell_price, sell_shares FROM trade_lots WHERE ... AND remaining_shares = 0 AND sell_shares > 0 AND sell_price IS NOT NULL` 接着 line 495 `SELECT buy_price, sell_price, sell_shares, remaining_shares FROM trade_lots WHERE ... AND remaining_shares > 0 AND sell_shares > 0 AND sell_price IS NOT NULL`。
- 后果：第二段 SQL 用 `remaining_shares > 0`（部分平仓的 lot）+ `sell_shares > 0` 计算 `partial_count`，**但 `partial_count` 的统计对象只是 lot 行数，不是真实交易笔数**。一笔买入 N 卖 N-M，剩 M 算一个 partial_lot；多笔同价位合并 partial_count 仍 = 1，会偏低。
- 证据：line 513 `partial_count` 直接 `len(partial_lots)`，没归一化。
- 建议：从 `trades` 表统计 SELL 总笔数与 BUY 总笔数取差，或在 trade_lots 加 `partial` 标志。

### A5. 缺 `trades.stamp_tax` 写入路径（**P0**）
- 现象：`trades` 表有 `stamp_tax REAL` 列（line 122），但 `add_trade`（database.py:417-432）只接受 `fee` 和 `stamp_tax` 入参，**不写 `transfer_fee`**——且 schema `transfer_fee_rate` 常量从未写入任何记录。
- 后果：trades 表 stamp_tax 字段 0 值（除 SELL 路径外），数据失真。
- 证据：`trading.py:120-225` `buy` INSERT trades 时**省略** `stamp_tax`（默认 0，正确，因为买入无印花税），但 `sell` 路径写入了 stamp_tax 字段（line 359-365）；BUY 也未计算/写入 `transfer_fee`。A 股深市过户费实际需要计入成本。
- 建议：BUY 时按沪/深加 transfer_fee，写入 trades 表新列。

### A6. trade_lots 与 trades 双账本同步风险（**P1**）
- 现象：FIFO 配对逻辑在 `reduce_position`（database.py:334-392）和 `sell`（trading.py:227-392）两处独立实现，且 `add_position` 单独写 trade_lots，但 `add_trade` 单独写 trades——**没有一致性约束**。
- 后果：
  - 如果直接调 `db.add_position` 而不调 `tm.buy`，`trades` 表会缺记录，统计 wins/losses 漏数
  - `reduce_position` 不写 trades，纯数据库层操作无法审计
  - `delete_trade` 反转 trades，但**不反转 trade_lots 的 sell 部分**（line 596-610 看似有，但只取 first 配对，剩余会丢失）
- 证据：line 587-610 `delete_trade` 写得很乱，`take = min(trade['shares'], lot['sell_shares'])` 后用 `sell_shares - take` 还原，但 `take` 后续不再用于累加；如果 SELL 跨多个 lot，第二个 lot 完全不会处理。
- 建议：合并到 `TradingManager.buy/sell` 唯一入口；`delete_trade` 应按 FIFO 遍历所有 lot 同步扣减。

### A7. `_get_conn` 线程模型与 WAL 的隐患（**P2**）
- 现象：`PortfolioDB.__init__` 实例级别，`_local` 用 `threading.local()` 缓存 conn，但 `get_db()` 是模块级单例 `_db_instance`。
- 后果：单进程多线程安全（线程局部 conn + WAL + busy_timeout），但**多进程（cron + uvicorn worker）共享同一 DB 文件**——`sim_trader.py` 在 cron 中跑 + `api/main.py` 在 uvicorn 中跑 = 两个进程同时打开 portfolio.db，WAL 模式能容忍读阻塞，但写并发会触发 `SQLITE_BUSY`（已有 busy_timeout 5s，能缓解但非根治）。
- 建议：写操作前重试，或用文件锁；写明"单写多读"约束。

---

## B. 交易逻辑 (trading.py)

### B1. BUY 资金检查在事务外（**P0**）
- 现象：`buy` (line 142-162) 先 `account = self.db.get_account(acc_id)`，然后在事务内 `new_capital = account['current_capital'] - total_cost` 写入。
- 后果：**TOCTOU race**：两个并发请求都读到 `current_capital=1000`，A 扣 800，B 扣 800，最终 current_capital = 1000 - 800 - 800 = **-600**。SQLite WAL 模式在两个进程并发写时会丢更新。
- 证据：line 167 `new_capital = account['current_capital'] - total_cost` 是 Python 层算的，不是 SQL 层 `current_capital = current_capital - ?`。
- 建议：把扣减改为 `UPDATE accounts SET current_capital = current_capital - ? WHERE id = ? AND current_capital >= ?`，检查 `rowcount` 失败返回资金不足。

### B2. 加权平均成本公式数学上不严谨（**P2**）
- 现象：line 318 `new_cost = (old_cost * old_shares + price * shares) / new_shares`
- 后果：正确（这是经典加权平均）。但**没有考虑手续费**——买入手续费进了现金扣减，不进 cost_price，导致显示的"成本价"与"真实成本"（含费）有偏差，盈亏统计偏高。
- 建议：cost_price 用 `cost_amount / shares`，其中 `cost_amount = old_cost_amount + price*shares + fee`。

### B3. 部分卖出未校验 100 股整手（**P1**）
- 现象：`_validate_shares` 在 BUY 和 SELL 都强制 ≥100 且 100 整数倍（line 95-108）。这意味着"100 股/手"约束同样适用部分卖出。
- 后果：合理（A 股规则）。但 `reduce_position`（database.py:334-392）直接接受了任意整数，没调 `_validate_shares`——`reduce_position` 路径会绕过校验。
- 证据：`db.reduce_position` 没有 shares 校验。
- 建议：`reduce_position` 也加 shares 校验，或在文档中标注"此为数据库底层方法，调用方需保证整手"。

### B4. `sim_trader` 同步 `trades` 与 `trade_lots` 一致性（**P1**）
- 现象：line 4-5 注释说"模拟仓自动交易"，实际是基于信号 + 止盈止损真实下单到 SQLite（`tm.buy`/`tm.sell`），写 trades + trade_lots + positions 全套。
- 后果：与"实盘"账户共享一套表结构，但只对 `mode='SIM'` 账号工作（line 169 `tm = TradingManager(mode=mode)`）。"实盘"账户**只能人工录入**——文档（line 320-326）也是这么说的。安全锁 `if args.mode == 'REAL' and not args.dry_run: sys.exit(1)` 防止误操作。
- 评价：实现正确，但 `mode='REAL'` 路径不写入 `trades`——**实盘"实际成交价"在系统里是空白的**，必须人工录入。

### B5. `get_latest_price` 不存在的代码（**P3**）
- 现象：`scripts/sim_trader.py:145-149` `get_latest_price` 永远返回 None（看 `score_price_history.csv` 没有当前日时返回 None），但 sim_trader 实际用的是 `row['close_price']`（line 266），不调 `get_latest_price`。
- 后果：未使用死代码。
- 建议：删除。

### B6. `delete_trade` 反转逻辑错误（**P0**）
- 现象：line 538-614。BUG：
  1. BUY 反转 (line 552-586)：先 SELECT 持仓 → 扣 shares → 加 refund，但**遍历 trade_lots 时** `take = min(trade['shares'], lot['buy_shares'] - lot['sell_shares'])` **计算完没累加**：`take` 用作 DELETE 条件而不是 UPDATE 中的 `take` 字段。`for lot in c.fetchall()` 后 `if trade['shares'] <= 0: break`——`trade['shares']` 是原值，从未递减。
  2. 实际逻辑是：**只要 trade_lots 行存在就 DELETE**——所有同一 code+buy_date 的 lot 都会被删，与实际"删除的份额"不对等。
  3. SELL 反转 (line 587-610)：同样 `take` 不累加。
- 后果：调用 `delete_trade` 后：
  - trade_lots 数据损坏（可能多删或少删）
  - positions 已关闭（closed_at 被设），但 trade_lots 记录全没了，无法追溯
  - 资金退还计算错（`refund = amount + fee` 应为 `amount + fee` 但 positions 是 closed_at 直接设，cost_price 不调整）
- 建议：重写为统一的 FIFO 反转逻辑，每次循环都 `trade['shares'] -= take`，且根据交易 type 用对应的 `UPDATE trade_lots` 写法。

---

## C. 净值/收益统计

### C1. NAV 公式隐含假设（**P2**）
- 现象：`nav = total_assets / initial_capital`
- 后果：纯利收益 = `(1+NAV_pct) * initial_capital - initial_capital`——但**忽略了净入金**。如果用户中途 `add_capital`，NAV 增长会被人为"摊薄"。
- 证据：`save_snapshot` 用 initial_capital 不变，但 `add_capital` 只动 current_capital。
- 建议：加 `net_contribution` 列，NAV = (cash + position_value) / (initial_capital + net_contribution)。前端需要同步显示。

### C2. 已实现 vs 未实现收益未分离（**P1**）
- 现象：`get_trade_stats` 只算了**已平仓 lot**的 win/loss。持仓中浮盈浮亏体现在 `position_value - cost_basis` 中。
- 后果：
  - 前端 Stats.vue 没有已实现/未实现分离
  - 胜率 = 已平仓 win / 已平仓 total——**不含浮盈**（合理，但应说明）
  - 不便于跟踪"开仓-平仓回路"
- 建议：API 增加 `realized_pnl` 和 `unrealized_pnl` 字段。

### C3. 最大回撤、夏普比率在前端算（**P2**）
- 现象：`Stats.vue:215-222` 在前端用 `for` 循环算 `maxDd`，没有夏普比率。
- 后果：
  - 前端有"实时"特征，但每次重算要拉全量历史（O(n)）
  - 无夏普比率——业界标配风险调整收益指标缺失
  - **最大回撤是峰值回撤（peak-to-trough）**而非基于时间权重的回撤期
- 建议：
  1. 后端增加 `/api/v1/portfolio/risk_metrics` 计算 Sharpe, Sortino, Calmar
  2. 前端改为显示"年化波动率"等指标

### C4. stats 中 `win_count` 含部分平仓 lot（**P1**）
- 现象：`get_trade_stats` line 493-494 `wins = [r for r in returns if r > 0]` 用 `(sell_price - buy_price) / buy_price * 100`——**未考虑手续费和印花税**。
- 后果：胜率偏高（+0.15% 佣金 + 0.1% 印花税未扣除，0.25% 以上的微利会显示为 win 但实际亏）。
- 建议：收益率改为 `(net_sell_proceeds - cost_basis) / cost_basis` 含费。

---

## D. 信号 vs 持仓衔接 (calc_signals.py / sim_trader.py / api/main.py)

### D1. 信号只算"买入"，无卖出信号（**P0**）
- 现象：`calc_signals.py` 只输出 `signal: 'BUY' if avg7_score >= 30 else ''`，没有 SELL 信号。
- 后果：止盈/止损完全由 sim_trader 的 K 线扫描（line 45-140）负责——**这是"硬规则"**，无法根据评分恶化动态卖出。
- 证据：`sim_trader.py:200-204` 检查 tp/sl，与评分脱钩。
- 建议：calc_signals 加 SELL 信号（评分跌破阈值 + K 线回撤 + 行业恶化等组合条件），写入 signals.csv。

### D2. 冷却期实现 read 所有历史文件（**P2**）
- 现象：`apply_cooldown` line 173-189 遍历 `signals_dir.glob('signals_*.csv')`，读每个 CSV，**无视 cutoff 限制**——`if date_str < cutoff: continue` 后再读取（OK），但 `history.append` 把所有 BUY 行都加进去，最后用 `groupby last` 取最后一次，逻辑正确但低效。
- 后果：信号文件累积后（每日一个），启动脚本会读所有历史 CSV。
- 建议：维护一个 `signals_history.parquet` 索引文件。

### D3. 买入信号与 sim_trader 衔接：单点失败（**P1**）
- 现象：evening_pipeline 步骤 3（calc_signals）成功后步骤 3.5（sim_trader）失败**不影响主流程**（line 77 `|| echo "⚠️"`），意味着 sim_trader 失败不会被重试也不会报警。
- 后果：自动交易静默失败——可能资金不足 / DB 锁 / 价格缺失，但用户不会感知。
- 建议：发送告警邮件 / 微信通知。

### D4. 卖出时机"保守=止损优先"未持久化（**P2**）
- 现象：sim_trader 同日双触达时（line 213-214）只打印警告 + 强制止损，**不写"both_triggered"到任何表**。
- 后果：复盘困难——`both_triggered` 列表只是局部变量，进程退出即丢失。
- 建议：写 `trade_lots` 或独立 `events` 表记录同一天双触达。

### D5. sim_trader 现金守恒不严（**P1**）
- 现象：line 270-272 `buy_amount = min(target_amount, cash * 0.95)`；`shares = int(buy_amount / price / 100) * 100`；line 282 `cash -= result['total_cost']`。
- 后果：`tm.buy` 内部又扣 `current_capital`，**但 sim_trader 在扣减后又用 `total_cost` 减 cash**——cash 是局部的，但调用 `tm.buy` 时 db 内的 current_capital 也会被扣，等于**双扣**？让我看清楚。

实际：sim_trader 调用 `tm.buy` 后，db.current_capital 已扣 total_cost；sim_trader 局部 `cash` 也减 total_cost——**OK 一致**。但 `total_cost` 含 fee，**fee 计算在 tm.buy 内部**，sim_trader 不知道 fee 多少——`result['total_cost']` 是 buy 返回的，没问题。

**真正的 BUG**：line 282 `cash -= result['total_cost']`，但循环里**多个 buy 都基于 `cash` 的递减**——OK。但如果第一个 buy 成功，第二个 buy 又检查 `if cash <= total_assets * 0.05: break`——`total_assets` 是循环开头算的（line 237），**未减去第一个 buy 的 total_cost**。
- 后果：现金 5% 守门用旧的 total_assets，可能超买。
- 建议：循环内 `total_assets = cash + position_value` 重算。

### D6. sim_trader 用 cost_price 而非 FIFO cost（**P2**）
- 现象：line 192-193 `pos['cost_price']` 是**加权平均**成本，FIFO 配对用的是**买入批次**成本（trade_lots）。检查 tp/sl 用加权平均。
- 后果：止盈止损用平均成本——如果分批买入，第一批到止盈、第二批到止损，但用平均成本可能"卖"在两者之间。
- 建议：用 trade_lots 逐 lot 检查 tp/sl。

### D7. 卖出无"持仓后冷却"（**P2**）
- 现象：卖出后 1 天冷却买入是 `calc_signals.py:31 COOLDOWN_DAYS=1`，但卖出后立即又满足买入信号 → 同一只股票"卖-买-卖"快速反转？实际 sim_trader 卖完后该股票在 `held_codes` 已剔除（line 241-242），不会被买入。
- 后果：OK，但**没有"刚止损的股票短期内不再买入"的反向冷却**——可能止损后立刻因评分上升又买入，循环亏损。
- 建议：止损后 N 天内同股票不买入。

---

## E. sim_trader.py

### E1. sim_trader 是"模拟真实交易"还是"回测验证"？（**事实陈述**）
- 答案：**模拟真实交易**——基于实时 signals 触发下单到 SIM 账户 SQLite。
- 不是回测：没有历史 K 线 replay；只对**当天**收盘后做止盈止损检查 + 按当晚信号买入。
- 评价：定位清晰，但**不能在历史时段验证策略**——`--date` 参数允许传任意日期，但**只是给信号文件名+对账日**用，逻辑是"用今天的信号给 SIM 账户下单"，不是"模拟 2025-01-02 那天的真实交易"。
- 文档缺陷：脚本 docstring 写"策略：买入：当前 strategy 定义的 buy_threshold 触发"——不准确，实际是"前7日均分≥30"。

### E2. sim_trader 的"止盈/止损"是收盘后单点检查（**P1**）
- 现象：line 91-133 遍历 [buy_date, end_date] 每天检查 high/low，但**只用一根 K 线触发一次卖出**，没有"持续触达"概念。
- 后果：
  - 触达当天之后不再检查（因为 sell 后 return）
  - 如果买入当天就触达 tp，且当天也触达 sl，line 101 走 both 分支——但**止盈也可能没触达目标价**（用 high 检查）——OK
  - **真实盘中可能先冲到 tp 又回落**，脚本用当天 high >= tp 即认为"触达"——可能当天没卖在 tp（更早卖在更低价），但脚本强制按 tp 价卖——**与现实不符**。
- 建议：明确假设"按目标价成交"（即条件单假设）。

### E3. sim_trader 的 BUY 跳过"现金不足 5%"的"检查点"不更新（**P1**）
- 现象：见 D5 详细分析。
- 建议：循环内重算 `total_assets`。

---

## F. stock_analysis.py（与持仓弱相关）

### F1. 角色定位（事实）
- 股票分析：单只股票 9 因子拆解 + 趋势 + 投资建议
- 与持仓**无任何接口**——不读 portfolio.db
- 评价：与本次审查主题"持仓+信号"弱相关，仅"评分+投资建议"是上游输入
- 严重问题：报告中"投资建议"硬编码（line 334-343 推荐关注 / 关注 / 中性 / 谨慎 / 回避）——**不接入策略和持仓**——投资者无法看到"我已持仓 X，评分 Y，建议加仓/减仓"

### F2. 价格文件读取 NaN 处理吞错（**P2**）
- 现象：line 105 `except: pass` 完全吞噬异常——`prev_close != 0` 后默默忽略。
- 评价：能容忍错误但调试难。

### F3. `load_cache` 缓存粒度粗（**P2**）
- 现象：cache 用 `code: today_str` 字典，**一天只能生成一次**。如果想重新生成要清缓存。
- 建议：cache key 加时间戳。

---

## G. 集成问题（api/main.py + sim_trader + calc_signals）

### G1. /api/v1/portfolio/buy 走 sim_trader 路径不存在（**事实**）
- 现象：api/main.py 提供 `/api/v1/portfolio/buy` 端点，前端 Web 可直接下单。
- 但 **evening_pipeline.sh 步骤 3.5 自动跑 sim_trader 也下单**——两者并发覆盖同一 SIM 账户。
- 后果：无并发控制。Web 端下单 + 流水线下单可能同时扣减资金。
- 建议：加分布式锁（`posix_ipc` 或文件锁 `/tmp/portfolio.lock`）。

### G2. 前端 Stats.vue NAV 数据来源不一致（**P2**）
- 现象：`stats.value = statData`（实时计算）+ `navHistory.value = navs`（从 daily_nav 读）。两条路径可能不一致（见 A3）。
- 评价：会让用户困惑。

### G3. update_capital 重置但不删 trade_lots 链（**P0**）
- 现象：trading.py `update_initial_capital` line 510-521：
  - positions 软删（closed_at）
  - trade_lots 硬删
  - trades 硬删
  - daily_nav 硬删
- 后果：
  - trade_lots 硬删，但 trades 也硬删——OK
  - 删 daily_nav 后**账户 history 曲线消失**——可接受
  - **dividends 表**没删——残留历史
  - **accounts.strategy_id** 没重置（实际 schema 没这列）
- 评价：基本正确但少删 dividends 表。

---

## H. 其他

### H1. `sim_trader` 不更新实盘价格（**事实**）
- 现象：sim_trader 只在 SIM 模式写数据；REAL 模式只读持仓 + 检查 tp/sl（dry-run）。
- 后果：实盘账户的 `current_price` 永远是 None，profit_rate = -100%（成本价对比）。
- 建议：加 `/api/v1/portfolio/update-prices` 自动调用脚本（实盘价格需要手动/外部拉取）。

### H2. calc_signals 重新跑会覆盖 signals_latest.csv（**P2**）
- 现象：line 218-219 `os.replace(tmp, latest)` 是原子操作，**但如果计算中途崩溃，tmp 文件残留**。
- 建议：try/except 清理 tmp。

### H3. StockAnalysis 的 HTML 报告里"全市场排名"计算复杂度 O(n²)（**P2**）
- 现象：line 197 `scores.sort` + 197-199 遍历，**对每只股票都重排**——O(n²)。
- 影响：5200 只股票 × 21 天 = ~110k 次排序，单只分析可能 5+ 秒。
- 建议：预算 rank 一次。

---

## 总结评分

| 维度 | 评分 | 理由 |
|------|------|------|
| 正确性 | 2/5 | A1 schema 不匹配、A4/A5 trade stats 错误、B1 TOCTOU、B6 delete_trade 反转错 |
| 可维护性 | 3/5 | 命名清晰但双账本/双 SQL 实现维护成本高 |
| 性能 | 3/5 | WAL 模式 + busy_timeout 缓解并发；FIFO O(n) 配对可接受 |
| 文档 | 2/5 | sim_trader docstring 不准；A 股规则备注在常量未文档化；NAV 公式无说明 |
| 总评 | 2.5/5 | schema 漂移是部署级问题；多 P0 待修 |
