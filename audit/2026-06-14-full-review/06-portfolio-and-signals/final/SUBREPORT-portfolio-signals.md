# 子报告：持仓管理与信号

> 范围：`src/portfolio/`（database.py、trading.py、__init__.py）、`scripts/calc_signals.py`、`scripts/sim_trader.py`、`scripts/stock_analysis.py`、`api/main.py` 持仓端点、`data/portfolio.db` schema
> 严重程度评级：P0=功能错误 / P1=性能或安全 / P2=可改进 / P3=小问题
> 审查日期：2026-06-14

## 1. 概览

持仓管理模块是 AUTO-STOCK 中连接"评分系统"和"实盘/模拟交易"的核心，由 7 张 SQLite 表（accounts / strategies / positions / trades / trade_lots / daily_nav / dividends）支撑，配套 API（`/api/v1/portfolio/*`）和 sim_trader 自动交易脚本。模块整体设计思路（双账本 positions + trade_lots 用于 FIFO 配对，A 股佣金+印花税规则化，WAL 并发）是合理的。

但本次审查发现**实盘数据库 schema 与代码不匹配**（最严重问题，`accounts.strategy_id` 在 Python 端定义但 SQLite 实际表中缺失，导致所有策略相关操作 KeyError 崩溃），以及 6 个 P0 级功能性错误（含 TOCTOU 资金竞态、delete_trade 反转错位、净值统计 SQL 漏算等）。模块虽已"完成"，但**未在生产环境真实跑通过买入→持仓→卖出→净值循环**，更未跑过夜流水线 + Web 前端并发。

**整体评价：模块功能链路完整，但 P0 级问题未被发现/修复即上线，定位"基本完成，仍需硬修复"**。

## 2. 关键发现（按严重程度降序）

### [P0] 实盘 DB 缺少 `accounts.strategy_id` 列
- 位置：`/home/admin/AUTO-STOCK/src/portfolio/database.py:74`（代码） vs 实际 `data/portfolio.db`（数据库）
- 现象：`_init_db` 在 `accounts` 表定义了 `strategy_id INTEGER` 列，但 `data/portfolio.db` 实际只有 7 列（`id, name, mode, initial_capital, current_capital, created_at, updated_at`），无 `strategy_id`。`CREATE TABLE IF NOT EXISTS` 对已存在的表**不会补列**。
- 后果：所有引用 `account['strategy_id']` 的代码（`TradingManager.get_strategy` L88-93、`db.set_account_strategy` L264、`sim_trader.get_strategy` L172、`api/main.py` 的策略切换端点）会抛 `KeyError: 'strategy_id'`，**实盘模拟自动交易整体不可用**。
- 证据：
  ```
  PRAGMA table_info(accounts):
  (0, 'id', 'INTEGER', 0, None, 1)
  (1, 'name', 'TEXT', 1, None, 0)
  (2, 'mode', 'TEXT', 1, "'SIM'", 0)
  (3, 'initial_capital', 'REAL', 1, '1000000', 0)
  (4, 'current_capital', 'REAL', 1, '1000000', 0)
  (5, 'created_at', 'TEXT', 1, "datetime('now', 'localtime')", 0)
  (6, 'updated_at', 'TEXT', 1, "datetime('now', 'localtime')", 0)
  ```
  代码引用 11+ 处；accounts 表已有 2 行（模拟仓/实盘），strategies 表已有 3 行。
- 建议：
  1. 在 `_init_db` 末尾加兼容性 ALTER：
     ```python
     for stmt in [
         "ALTER TABLE accounts ADD COLUMN strategy_id INTEGER",
         # 加其他列同理
     ]:
         try: c.execute(stmt)
         except sqlite3.OperationalError: pass  # 列已存在
     ```
  2. 或维护 `schema_version` 表，启动时按版本迁移
  3. 在 README 写明"首次运行会自动 ALTER 现有表"

### [P0] 买入资金扣减存在 TOCTOU race
- 位置：`src/portfolio/trading.py:142-171`（buy 函数）
- 现象：line 142 `account = self.db.get_account(acc_id)` 在事务**外**读 current_capital；line 167 `new_capital = account['current_capital'] - total_cost` 在事务**内**用 Python 算的旧值写回。
- 后果：两个并发请求同时读 `current_capital=1000`，A 扣 800、B 扣 800，最终 `current_capital = -600`（破产式下挫）。SQLite WAL 模式进程间无锁，cron（sim_trader） + uvicorn worker（API 端点）并发写时**必然触发**。
- 证据：
  ```python
  account = self.db.get_account(acc_id)
  # ... 计算 total_cost
  if total_cost > account['current_capital']:  # 旧值
      return {'success': False, 'error': '资金不足'}
  with self.db.transaction() as conn:
      new_capital = account['current_capital'] - total_cost  # 仍是旧值！
      cursor.execute('UPDATE accounts SET current_capital = ? ...', (new_capital, ...))
  ```
- 建议：原子化扣减 + 行锁：
  ```python
  cursor.execute(
      'UPDATE accounts SET current_capital = current_capital - ? '
      'WHERE id = ? AND current_capital >= ?',
      (total_cost, acc_id, total_cost)
  )
  if cursor.rowcount == 0:
      return {'success': False, 'error': '资金不足'}
  ```

### [P0] `delete_trade` 反转逻辑严重错位
- 位置：`src/portfolio/trading.py:538-614`
- 现象：BUY 反转（line 552-586）遍历 trade_lots 时 `take = min(trade['shares'], lot['buy_shares'] - lot['sell_shares'])` 计算后**未累加**到 `trade['shares']`，循环退出条件 `if trade['shares'] <= 0: break` 永远不触发（trade['shares'] 是原值）；最终 `c.execute("DELETE FROM trade_lots WHERE id = ?", ...)` 逐行删除，不考虑份额。
  SELL 反转（line 587-610）同样 `take` 不累加，循环用 `if trade['shares'] <= 0: break` 兜底但**变量不更新**。
- 后果：调用 `delete_trade` 后 trade_lots 数据完全损坏——可能多删或漏删，无法追溯；positions 设 closed_at 后与 trade_lots 失去关联。
- 证据：line 582-586、line 598-610，循环逻辑只取 first 配对。
- 建议：重写为统一 FIFO 循环：
  ```python
  remaining = trade['shares']
  for lot in lots:
      if remaining <= 0: break
      take = min(remaining, lot['buy_shares'] - lot['sell_shares'])
      new_remaining = lot['buy_shares'] - lot['sell_shares'] - take
      if new_remaining == 0:
          c.execute("DELETE FROM trade_lots WHERE id = ?", (lot['id'],))
      else:
          c.execute("UPDATE trade_lots SET remaining_shares = ? WHERE id = ?", (new_remaining, lot['id'],))
      remaining -= take
  ```

### [P0] `get_trade_stats` 胜率统计不扣手续费
- 位置：`src/portfolio/database.py:476-514`
- 现象：line 488-494 `returns.append((sell_price - buy_price) / buy_price * 100)` 只算价格差，**未扣 0.15% 佣金 + 0.1% 印花税 = 0.25% 最低成本**。
- 后果：0.10% ~ 0.20% 的微利交易会被统计为 win，但实际净亏损；胜率虚高约 5-10%。
- 证据：trade_lots 存 `buy_price` / `sell_price`，未存 `sell_fee`；`sell` 路径 line 327 算 fee + stamp_tax 写入 trades 表，但**没回填 trade_lots**。
- 建议：trade_lots 加 `sell_fee` / `sell_stamp_tax` 列，sell 时同步回填，stats 用净收益。

### [P0] A 股 BUY 未计算/写入 transfer_fee（过户费）
- 位置：`src/portfolio/database.py:28`（常量定义） vs `trading.py:120-225`（buy 函数）
- 现象：`TRANSFER_FEE_RATE = 0.00001` 已定义，但 buy 全路径**不计算过户费**——深市股票买入实际有 0.1‱ 过户费，沪市 0.1‱ 双向。
- 后果：交易成本低估 0.02%（沪市）/ 0.01%（深市）双向，**模拟交易与实盘有偏差**。
- 证据：trades 表 `stamp_tax` 列对 BUY 永远 0（正确，无印花税），但 `transfer_fee` 没有对应列；add_trade 入参也无 transfer_fee。
- 建议：trades 表加 `transfer_fee` 列；buy 按 code 前缀判断沪/深（6/9 开头沪市，0/3 开头深市）计算过户费。

### [P0] 信号系统只输出"买入"，无卖出信号
- 位置：`scripts/calc_signals.py:150` + 整套 sim_trader
- 现象：calc_signals 仅 `signal: 'BUY' if avg7_score >= 30 else ''`；卖出完全靠 sim_trader K 线扫描（硬规则 tp=20% / sl=8%）。
- 后果：
  1. 评分从 60 跌到 10 不会触发任何"减仓"提示
  2. 行业恶化、新闻利空等动态因素**无法反映在卖出决策中**
  3. sim_trader 卖出 K 线扫描在**收盘后**做，盘中无法止损（止盈/止损本质是事后检查）
- 证据：calc_signals.py 中无 `SELL` 信号输出；`signals_*.csv` 全是 `BUY` 或空。
- 建议：calc_signals 增加 SELL 信号规则（评分跌破 30 且 5 日均线下穿 20 日均线 / 行业相对收益转负 / 财务因子大幅恶化），写入 CSV；sim_trader 优先按信号卖出，K 线 tp/sl 作为兜底。

### [P1] `add_position` 与 `TradingManager.buy` 双写持仓/账本
- 位置：`src/portfolio/database.py:305-332`（add_position） vs `src/portfolio/trading.py:120-225`（buy）
- 现象：两个入口都执行了 SELECT/UPDATE positions + INSERT trade_lots；只有 buy 写 trades。
- 后果：业务调用方若直接调 `db.add_position` 而跳过 `tm.buy`，`trades` 表会缺记录，胜率/胜笔统计漏数；`reduce_position`（database.py:334-392）同样只动 positions + trade_lots，**不写 trades**——纯数据库层操作无审计。
- 建议：合并为单一入口，DB 层只暴露 `add_position`（已存在）但**去掉 trade_lots 写入**，统一由 `TradingManager.buy` 调 `add_position` 后再写 trade_lots + trades。

### [P1] sim_trader 现金守门 `total_assets` 循环内不更新
- 位置：`scripts/sim_trader.py:237-282`
- 现象：line 237 `total_assets = cash + position_value` 在循环**外**算一次；line 259-260 `if cash <= total_assets * 0.05: break` 在循环**内**用旧值。
- 后果：第一只 buy 后 cash 已减，但 total_assets 还是初始值，**5% 守门失效**——可能超买到 0% 甚至负。
- 建议：循环内重算：
  ```python
  for _, row in buy_signals.iterrows():
      cash = tm.get_account()['current_capital']
      positions = tm.get_positions()
      position_value = sum((p.get('current_price') or p['cost_price']) * p['shares'] for p in positions)
      total_assets = cash + position_value
      if cash <= total_assets * 0.05: break
  ```

### [P1] sim_trader 止盈止损用加权平均成本，非 FIFO 批次成本
- 位置：`scripts/sim_trader.py:191-194`、`check_take_profit_stop_loss` L45-140
- 现象：用 `pos['cost_price']`（加权平均）作为基准检查 tp/sl，**但 sell 路径用 FIFO trade_lots 配对**——两端不一致。
- 后果：分批买入时，第一批到 tp 而第二批到 sl，用平均成本可能卖在 tp-sl 中间；且 trade_lots 配对返回的"成本"与检查 tp/sl 的"成本"不同。
- 建议：用 trade_lots 逐 lot 检查 tp/sl（一次卖出可能触发多个 lot）。

### [P1] sim_trader 卖出时机"按目标价"假设未文档化
- 位置：`scripts/sim_trader.py:91-133` + L107-133
- 现象：检测到 `high >= target_tp` 即按 `target_tp` 价成交——**与"真实盘中可能先冲到 tp 又回落按更低价卖"的现实不符**。
- 后果：模拟收益系统性偏高（每次都按最理想价格成交）。
- 建议：明确"条件单假设"在 docstring 和 README；或加 `execution_mode = 'ideal' | 'vwap' | 'open'` 选项。

### [P1] sim_trader 双触达警告不持久化
- 位置：`scripts/sim_trader.py:213-221` + `both_triggered` 局部变量
- 现象：同日双触达时只 print 警告到 stdout，**不写数据库**；进程退出后复盘困难。
- 建议：加 `events` 表或 trade_lots 标记位记录同一天双触达。

### [P1] 已实现 vs 未实现收益未分离
- 位置：`src/portfolio/trading.py:413-458`（get_stats）
- 现象：只返回 win_rate / avg_win / avg_loss（已平仓），无 `realized_pnl` 和 `unrealized_pnl` 分离字段。
- 后果：投资者看不到"账面浮盈 vs 实际到手收益"。
- 建议：API 增加 `realized_pnl` / `unrealized_pnl` 字段，Stats.vue 显示两个 KPI。

### [P1] evening_pipeline 步骤 3.5 sim_trader 失败不报警
- 位置：`scripts/evening_pipeline.sh:77`
- 现象：`|| echo "⚠️ 模拟仓交易失败（不影响主流程）"`——失败仅 stdout 一行，无重试、无通知。
- 后果：自动交易静默失败（资金不足 / DB 锁 / K 线缺失）用户不会感知。
- 建议：发邮件 / 微信通知；或加 exit code 区分"预期失败"和"异常失败"。

### [P1] NAV 公式隐含 `add_capital` 摊薄假设
- 位置：`src/portfolio/trading.py:480`、`save_daily_nav`（database.py:439）
- 现象：`nav = total_assets / initial_capital` 用**固定**初始资金做分母。
- 后果：中途 `add_capital(+50000)` 后 NAV 增长被人为摊薄，纯利会被算少。
- 建议：加 `net_contribution` 列，nav 公式改 `(cash + position_value) / (initial_capital + net_contribution)`；`add_capital` 同步更新 net_contribution。

### [P2] 净值/统计前后端路径不一致
- 位置：`src/portfolio/trading.py:413-458`（实时算） vs `daily_nav` 表（持久化） + `Stats.vue:215-222`（前端算 maxDd）
- 现象：`get_stats` 实时计算 total_assets（用 current_price 或 cost_price），`Stats.vue` 从 daily_nav 读历史 NAV 后**前端**算 maxDd；前后端用不同数据源。
- 后果：实时 stats 与历史曲线可能不一致；夏普比率未实现（业界标配风险调整收益缺失）。
- 建议：后端统一从 `daily_nav` 读；增加 `/api/v1/portfolio/risk_metrics` 返回 Sharpe / Sortino / Calmar。

### [P2] `calc_signals.apply_cooldown` 读所有历史 CSV
- 位置：`scripts/calc_signals.py:173-189`
- 现象：line 173 `for f in signals_dir.glob('signals_*.csv')` 读**所有**每日 CSV。
- 后果：信号文件累积后（每日一个）启动慢；当前 5 文件不大，未来 200+ 文件会显著拖慢。
- 建议：维护 `signals_history.parquet` 索引文件。

### [P2] `stock_analysis.py` 全市场排名 O(n²)
- 位置：`scripts/stock_analysis.py:192-200`
- 现象：line 195 `scores.sort` + 197-199 遍历，对每只股票重排。
- 影响：5200 只股票 × 21 天 = ~110k 次排序，单只分析可能 5+ 秒。
- 建议：预算 rank 一次（用 pandas `rank`）。

### [P2] `sim_trader` 卖出后无反向冷却（刚止损又买入）
- 位置：`scripts/sim_trader.py` 全局
- 现象：止盈/止损卖出后无额外冷却；只要评分再次 ≥30 可立即再买入。
- 后果：可能"止损-评分回升-再买入-再止损"循环亏损。
- 建议：止损后 N 天内同股票不买入（独立于买入信号 cooldown）。

### [P3] `get_latest_price` 死代码
- 位置：`scripts/sim_trader.py:145-149`
- 现象：定义但未使用，实际 sim_trader 用 `row['close_price']`。
- 建议：删除。

### [P3] `stock_analysis.py` HTML 报告"投资建议"硬编码
- 位置：`scripts/stock_analysis.py:334-343` + `475-486`
- 现象：纯基于 total_score 阈值分级，**不读 portfolio.db**，投资者无法知道"我已持仓 X，评分 Y，建议加/减/平"。
- 建议：可选地读 portfolio.db 接入策略和持仓。

## 3. 改进建议（非问题，但有更好做法）

1. **统一 nav/drawdown 计算位置**：建议后端在 `daily_nav` 表上聚合计算（`/api/v1/portfolio/risk_metrics`），前端只展示；避免前后端算法分裂。
2. **加 schema 版本管理**：`schema_version` 表 + 启动迁移脚本，避免 `accounts.strategy_id` 漂移问题。
3. **FIFO 配对用 CTE**：trading.sell 中的 FIFO 循环可改为 SQLite CTE 一次查询，O(n) 改 O(1) 往返。
4. **sim_trader 加 `--since-buy-date` 模式**：如果想验证历史策略，应支持"从 buy_date 起每日回放 K 线"——目前只能当日调用。
5. **`stock_analysis.py` 缓存粒度**：cache key 加时间戳（`{code}:{date}:{ts}`），避免清缓存。
6. **A 股规则集中在 `constants.py`**：MIN_SHARES / SHARES_LOT / COMMISSION_RATE / STAMP_TAX_RATE / TRANSFER_FEE_RATE 已分散在 `database.py` 常量 + 代码内常量，可集中导入。
7. **实盘账户价格自动同步**：增加 `/api/v1/portfolio/update-prices` 定时任务（实盘价格来源需用户配置，避免混用模拟价）。

## 4. 需要核实的不确定项

- **net_contribution 字段**：是否计划在 v2 加入？目前 NAV 公式假定用户不增减资金，但 sim_trader 测试场景可能涉及。
- **实盘账户的实际价格来源**：用户通过券商 App 手动录入？还是通过券商 API 拉取？影响 `update_prices` 设计。
- **`stock_analysis.py` 是否要接入 portfolio**：CLAUDE.md 提到"投资建议"硬编码，是否打算做"基于持仓的智能建议"？
- **sim_trader 是不是回测的替代品**：从代码看不是，但用户期望是？
- **`delete_trade` 业务价值**：用户是否会主动删除某笔错误交易？如果不会，整个函数可以删；如果会，需要重写正确版本。

## 5. 评分（1-5，5 = 优）

| 维度 | 评分 | 理由 |
|------|------|------|
| 正确性 | 2/5 | 6 个 P0（schema 漂移、TOCTOU、delete_trade 错位、胜率漏算费、A 股 transfer_fee 漏算、无卖出信号）尚未修复 |
| 可维护性 | 3/5 | 模块拆分清晰（database / trading 分离），但双账本/双 SQL 实现维护成本高，且未文档化 |
| 性能 | 3/5 | WAL + busy_timeout 缓解并发；FIFO O(n) 配对可接受；calc_signals 全量重读会随时间退化 |
| 文档 | 2/5 | sim_trader docstring 与实际行为不符；NAV 公式无说明；A 股规则常量未文档化；FIFO 逻辑无注释 |
| 总评 | 2.5/5 | 模块已"完成"但 P0 未修即上线；建议先硬修复 A1/A4/B1/B6/D1，再谈优化 |

---

**附录：审查统计**

- P0: **6** 个
- P1: **6** 个
- P2: **4** 个
- P3: **2** 个

**Top-3 严重问题**：
1. **DB schema 漂移**（`accounts.strategy_id`）—— 部署级阻塞，所有策略相关操作崩溃
2. **TOCTOU 资金竞态**（buy 函数）—— 并发场景下会超扣到负值
3. **delete_trade 反转错位** —— 触发后 trade_lots 数据完全损坏，无法追溯

**整体评分：2.5/5** — 核心逻辑骨架完整，但未在生产环境跑通买入→持仓→卖出→净值循环，6 个 P0 需立即修复后才能上实盘/重启用 sim_trader。
