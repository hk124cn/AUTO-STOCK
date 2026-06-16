# 持仓 + 信号 — 原始观察笔记（子报告 #7）

> 审查范围：`src/portfolio/`（database.py、trading.py、__init__.py）、`scripts/calc_signals.py`、`scripts/sim_trader.py`、`scripts/stock_analysis.py`、`api/main.py` 持仓端点、`data/portfolio.db` 实际 schema
> 审查日期：2026-06-16（与上次审查 2026-06-14 间隔 1 天）
> 上一轮 P0：6 个（schema 漂移 / TOCTOU / delete_trade 错位 / 胜率漏算 / A 股 transfer_fee 漏算 / 无卖出信号）

---

## 0. 数据库实际状态（ctypes 直查 portfolio.db）

`accounts` 表 CREATE 语句（实际落盘的 SQL）：
```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'SIM' CHECK(mode IN ('SIM', 'REAL')),
    initial_capital REAL NOT NULL DEFAULT 1000000,
    current_capital REAL NOT NULL DEFAULT 1000000,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(name, mode)
)
```

**列：id / name / mode / initial_capital / current_capital / created_at / updated_at — 共 7 列。无 `strategy_id` 列。**

代码 `_init_db` 写了 8 列（多了 `strategy_id`），但 `CREATE TABLE IF NOT EXISTS` 对已存在表不会补列。

实测写入验证：
```
$ UPDATE accounts SET strategy_id = 2 WHERE id = 1
rc: 1 err: no such column: strategy_id
```

**结论：上一轮 P0#1（schema 漂移）未修复。**

### accounts 实际数据
| id | name | mode | initial_capital | current_capital |
|----|------|------|-----------------|------------------|
| 1 | 模拟仓 | SIM | 1,000,000.0 | **14,958.2600000001** |
| 2 | 实盘 | REAL | 100,000.0 | 100,000.0 |

**`current_capital=14958.2600000001` 是浮点尾数伪影** — 反复加/减非整除金额导致。建议 `round(..., 2)` 持久化。

### strategies 表实际数据
- 1: 默认策略, 30.0/0.20/0.08/1d/0.20/5 — is_default=1
- 2: 稳健, 40.0/0.15/0.05/3d/0.15/3
- 3: 激进, 25.0/0.30/0.12/0d/0.30/8

### positions 数据（部分）
| id | account_id | code | shares | cost | current_price | buy_date | closed_at |
|----|------------|------|--------|------|---------------|----------|-----------|
| 4-7 | 1 | 601138/000100/003004/600176 | … | 真实值 | **1.0** | 2026-06-14 | 2026-06-14 |

**问题**：positions 4-7（已平仓）`current_price=1.0` — 应该是 `NULL` 或卖出价；遗留 1.0 默认值会导致 `get_stats` 把"未实现盈亏"算成 -99.9%。

### trades 数据
- 5 条 trades（id 15-19，2026-06-15），全是 BUY，无 SELL。
- fee=29.2x 4 条 + 29.15（其中 transfer_fee 列不存在）
- 没有 stamp_tax（SELL 才有，BUY 是 0 正确）

### trade_lots 数据
- 5 条（id 8-12），都是 buy_date=2026-06-15，无 sell_date。
- 这些都对应刚发生的 5 笔买入。

### daily_nav 数据
- 2026-06-11: 净值 1.0
- 2026-06-12: 净值 0.99985226，cash=**14958.2600000001**（同上伪影）

---

## 1. 上次 P0 修复状态

| 上次 P0 | 状态 | 证据 |
|---------|------|------|
| **#1 accounts.strategy_id 漂移** | **未修** | DB 仅 7 列，UPDATE 报 no such column |
| **#2 TOCTOU 资金竞态** | **未修** | trading.py:142 `account = self.db.get_account(acc_id)` 在事务外读；L167 `new_capital = account['current_capital'] - total_cost` 用旧值算 |
| **#3 delete_trade 反转错位** | **未修** | trading.py:582-586 `if trade['shares'] <= 0: break` 永真（trade['shares'] 未递减），L585 `take` 算完不累加，L586 `DELETE FROM trade_lots WHERE id = ?` 直接全删（错位） |
| **#4 胜率不扣手续费** | **未修** | trading.py:489-494 `get_trade_stats` 仍 `(sell_price - buy_price) / buy_price * 100` |
| **#5 A 股 BUY 漏算 transfer_fee** | **部分修** | 仍无 transfer_fee 列；`calc_buy_fee` (L22-25) 注释明确"过户费：仅沪市，简化忽略"。数据库未加列。 |
| **#6 无卖出信号** | **已修** | `scripts/calc_signals.py:277-364` 新增 `generate_sell_signals()` 检查持仓的止盈/止损；main() L429-433 合并到输出 CSV |

**修复率：1/6（17%）。** SELL 信号是 6 个 P0 里唯一修了的，且修得合理。

---

## 2. 其他发现（与上次对比）

### 2.1 代码已改进的部分
- `_init_db` 创建了 `strategies` 表（L81-95），`get_default_strategy` / `get_strategy` / `set_account_strategy` 都接好了；只是 `accounts.strategy_id` 列未做迁移
- `sim_trader.py:233-241` 在持仓卖出后**重新读** `current_capital` 和 `position_value`，现金守门用 `total_assets` 不再循环外冻结
- `sim_trader.py:319-332` 加了 SIM/REAL 安全锁：拒绝实盘真实下单
- `TradingManager.buy` L138-211 把 SELECT/UPDATE 移到单事务内（修复了 P1#1 双写）
- `api/main.py` 持仓端点都加了 `verify_token` 鉴权

### 2.2 B 卖信号集成评价
- `calc_signals.generate_sell_signals` 用 `portfolio.db.get_positions(SIM)` + `score_price_history` 当日 close_price
- 卖出价用 `current_price`（K 线收盘价），**非市价/止损价** — 与 sim_trader 自己的"按目标价"不一致
- 止盈/止损参数从 `strategies` 表取（正确）— 但 `sim_account.get('strategy_id')` 会 KeyError，因为实际无该列
- 触发条件：return ≥ take_profit（20%）或 ≤ -stop_loss（8%）
- 写回 CSV 用 `drop_duplicates(subset=['code'], keep='last')` 让 SELL 覆盖 BUY（同 code 已有 BUY 不再买）

**问题**：
- 卖信号只能检测 **SIM 账户持仓** — 实盘账户的 SELL 不参与
- 持仓里的 `current_price` 字段经常是 1.0（默认值）或 None（未更新） — 会让 return_pct 计算爆炸
- 持仓 `cost_price` 与 trade_lots 的 buy_price 可能不一致（多次加仓平均）— `pos.get('avg_cost', 0)` 取不到，fallback 到 `pos.get('buy_price', 0)` 也取不到（positions 表无这两个字段名），最终走 `pos.cost_price` 是字段名巧合；语义脆弱

### 2.3 C V1/V2 路由
- `sim_trader.py:152` 入参 `strategy_version: str = 'v1'`，通过 `get_strategy(version)` 拿 `output_subdir` 拼路径
- **CLI 不暴露 `--strategy-version` 参数** — 看 main() L311-316，只有 `--date` / `--dry-run` / `--mode`，版本被硬编码为 v1
- 想跑 v2 必须改源码或外部调用 `run_auto_trade(date, mode='SIM', strategy_version='v2')`
- **账号绑定的 strategy_id**（v1/v2/v3 数据库策略表）**与** 信号策略版本（v1/v2 calc_signals 注册表）**是两套概念**，目前无任何关联代码

### 2.4 D 数据库新增
- **未新增** signals 表（信号仍落 CSV）
- **未新增** strategy_version 字段
- accounts 仍无 strategy_id（核心 P0 未修）

### 2.5 E 持仓前端
- `web/stock-system/src/views/Portfolio.vue:101-138` 持仓表 8 列：代码/名称/持仓数量/成本价/现价/盈亏金额/收益率/操作
- **不展示 TP/SL 目标价列**（虽然后端 `get_positions` 在 L398-406 计算了 `target_take_profit` / `target_stop_loss` 字段 — 前端没用）
- **不展示策略版本列**
- 交易记录表 8 列：日期/类型/代码/名称/价格/数量/金额/费用/操作 — 同样无策略版本列
- signals_latest.csv 在 Signals 页有版本选择；Portfolio 页无此 UI

### 2.6 NAV 公式复查
- `trading.py:480` `nav = total_assets / account['initial_capital']` — 仍用固定 initial_capital 做分母
- add_capital 不会更新 initial_capital（语义上正确 — NAV 应该是"投入回报率"），但 P1#11 提到的"中途加金 5w 后 NAV 被摊薄"未修
- `get_daily_nav`（database.py:447-459）按 date 排序读，**未用 GROUP BY**（P0 误报）— 单 date/单 account 是 UNIQUE 约束（database.py:142），不存在重复，无须 GROUP BY
- daily_nav 只有 3 行（最新 2026-06-12），说明 2026-06-15 sim_trader 跑过但**没成功保存**或**没运行**（positions 4-7 buy_date=2026-06-14，trade id 15-19 buy_date=2026-06-15 → 2026-06-15 sim_trader 应有运行，但 daily_nav 没新增）

### 2.7 API 安全
- 持仓端点（L824-1032）除 GET 外都加 `Depends(verify_token)`
- `verify_token` 检查 `STOCK_API_TOKEN` env（CLAUDE.md 提到"密钥 env 化"）
- 但**不验证 mode 与 account_id 的归属** — 用户用 mode=REAL 传 account_id=1（SIM）也可通过
- `_get_tm` L767-770 创建 TradingManager 会自动找对应 mode 的第一个账户，**不查传入的 account_id 是否真属于该 mode**

### 2.8 sim_trader 现金守门复查
- L263 `if cash <= total_assets * 0.05: break` — 在循环**内**用循环**外**的 `cash` 和 `total_assets`
- 每次 buy 成功 L286 `cash -= result['total_cost']` 局部更新了 cash（下一轮 break 检测用新值）
- 但 `total_assets` **没在循环内重算**（持仓量增加后 total_assets 应变大，但用旧值）
- 后果：max_position_pct 算的 `target_amount = total_assets * 0.20` 用循环开始时的总资产，**可能买到超过当前总资产的 20%**
- 上次 P1#2 提到的"total_assets 循环内不更新" — 部分修了（cash 更新，total_assets 没修）

### 2.9 transfer_fee
- database.py:28 `TRANSFER_FEE_RATE = 0.00001` 已定义
- trading.py:22-25 `calc_buy_fee` 注释"过户费：仅沪市，简化忽略" — **沪市实际 0.1‱（含买卖双向）**，目前 0 计算
- trading.py:28-38 `calc_sell_fee` 同样没加 transfer_fee
- 影响：A 股交易成本低估 0.01%~0.02%，模拟收益系统性偏高 0.05%~0.10%（年化）
- P0#5 实际"半修" — 常量已定义，未使用

### 2.10 trade_lots.sell_fee 字段
- trade_lots 表 L146-162 无 `sell_fee` / `sell_stamp_tax` 列
- sell 路径 trading.py:359-365 把 commission/stamp_tax 写入 trades 表，但**不回填 trade_lots**
- get_trade_stats 算胜率时只算价格差，**未扣 fee**
- P0#4 完全未修

### 2.11 sim_trader 持仓 table
- `tm.get_positions()` (L394-406 trading.py) 读 `positions` 表 + 算 `target_take_profit` / `target_stop_loss`
- sim_trader:204 `check_take_profit_stop_loss(pos['code'], pos['cost_price'], pos['buy_date']..., end_date=date)` 用 cost_price
- 但 `add_position` 是加权平均成本，**不是 FIFO 批次成本** — 上次 P1#3 提到的"加权 vs FIFO 不一致"未修

### 2.12 sim_trader 双触达
- sim_trader:217-225 记录到 `both_triggered` 列表，**未写数据库**
- 进程退出后即丢 — 上次 P1#4 未修

### 2.13 calc_signals 全量读
- apply_cooldown L222 `for f in signals_dir.glob('signals_*.csv')` — 读所有历史文件
- 当前 v1: 3 文件 / v2: 3 文件，不大
- P2#1 未修

### 2.14 stock_analysis.py
- 仍完全无 portfolio.db 集成
- 投资建议硬编码分级（L334-343 / L475-486）— 上次 P3#2 未修
- 跑全市场排名 O(n²) — 上次 P2#2 未修

### 2.15 get_latest_price
- sim_trader:145-149 定义但**未使用**（sim_trader:269 用 `row['close_price']`） — 上次 P3#1 未修

---

## 3. 关键路径验证（CTypes 直查）

实测 ctypes 查询示例：
```
$ SELECT * FROM accounts
1 | 模拟仓 | SIM | 1000000.0 | 14958.2600000001 | 2026-06-12 23:20:24 | 2026-06-15 08:55:00
2 | 实盘 | REAL | 100000.0 | 100000.0 | 2026-06-12 23:20:24 | 2026-06-12 23:53:04

$ UPDATE accounts SET strategy_id = 2 WHERE id = 1
rc: 1 err: no such column: strategy_id
```

**关键证据**：`sim_trader` 实际跑过（trades 15-19 2026-06-15 写入），但 `daily_nav` 仍停在 2026-06-12 — save_snapshot(L465 trading.py) 写库失败？还是没运行 save_snapshot？看代码 L290 `snapshot = tm.save_snapshot(date)` 调了，应落 daily_nav。可能 portfolio.db 是只读快照或 save_snapshot 期间 portfolio 进程重启。

---

## 4. 修复建议汇总（与 P0 优先级排序）

### A. schema 漂移（最严重 — 一行迁移脚本）
在 `_init_db` 末尾加：
```python
for stmt in [
    "ALTER TABLE accounts ADD COLUMN strategy_id INTEGER",
]:
    try: c.execute(stmt)
    except sqlite3.OperationalError: pass
```

### B. TOCTOU（资金竞态）
把 `UPDATE accounts SET current_capital = ?` 改成原子：
```python
cursor.execute(
    'UPDATE accounts SET current_capital = current_capital - ? '
    'WHERE id = ? AND current_capital >= ?',
    (total_cost, acc_id, total_cost)
)
if cursor.rowcount == 0:
    return {'success': False, 'error': '资金不足'}
```

### C. delete_trade 错位
按剩余量正确递减 `trade['shares']` / `lot['sell_shares']`，仅在 `new_remaining == 0` 时 DELETE。

### D. transfer_fee + get_trade_stats 净收益
trade_lots 加 `sell_fee` / `sell_stamp_tax` 列，sell 路径回填，get_trade_stats 用 `(sell_price*shares - sell_fee - sell_stamp_tax - buy_price*shares) / (buy_price*shares)`。

### E. sim_trader 5% 守门 + total_assets 循环内重算
```python
for _, row in buy_signals.iterrows():
    cash = tm.get_account()['current_capital']
    positions = tm.get_positions()
    position_value = sum((p.get('current_price') or p['cost_price']) * p['shares'] for p in positions)
    total_assets = cash + position_value
    if cash <= total_assets * 0.05: break
```

### F. 信号策略版本 CLI
sim_trader.py main() 加 `--strategy-version` 参数透传。
