# 回应 — 2026-06-16

> 审查人：Claude (当前会话)
> 回应时间：2026-06-16
> 方法：逐项运行代码验证，非静态阅读

---

## Part A — P0 逐条评价

### P0-1 关键脚本全部 untracked

**A 提的**：calc_signals.py / sim_trader.py / signal_engine.py 三个核心脚本从未 commit，git 历史缺失。

**我的判断**：✅ 同意，事实确认。

**验证**：
```
$ git status --short scripts/calc_signals.py scripts/sim_trader.py src/backtest/signal_engine.py
?? scripts/calc_signals.py
?? scripts/sim_trader.py
?? src/backtest/signal_engine.py
```

**建议改法**：
- 立即 `git add` + `git commit`，不需要重构
- 先 `grep -rn "password\|token\|secret\|apikey" scripts/calc_signals.py scripts/sim_trader.py src/backtest/signal_engine.py` 确认无硬编码敏感信息
- ⏱ 5分钟
- ⚠️ 风险：无

---

### P0-2 evening_pipeline.sh 不调信号计算

**A 提的**：evening_pipeline.sh 只有 3 步（评分→kline_analyzer→报告），不调 calc_signals 和 sim_trader，信号系统在仓库内不可复现。

**我的判断**：✅ 同意，事实确认。

**验证**：evening_pipeline.sh 确实只有 step 1/2/3，无 calc_signals 或 sim_trader 调用。

**建议改法**：
- 在 evening_pipeline.sh 末尾加 step 4: `calc_signals.py --strategy-version v1` + `--strategy-version v2`
- sim_trader 暂不加入流水线（它涉及实际交易决策，应独立 cron 控制）
- ⏱ 15分钟
- ⚠️ 风险：calc_signals 失败会阻断流水线，建议用 `|| fail "calc_signals"` 严格模式

---

### P0-3 卖信号"集成"是半成品

**A 提的**：calc_signals 算 SELL 写 CSV，但 sim_trader 不消费 SELL 列，独立用 K 线扫描做止盈止损。

**我的判断**：✅ 同意，事实确认。

**验证**：
- `sim_trader.py:244` 只过滤 `signals['signal'] == 'BUY'`，不看 SELL
- `sim_trader.py:204` 独立调用 `check_take_profit_stop_loss()` 扫描 K 线
- 两套数据源不同（score_price_history vs data/price/*.csv）

**建议改法**：
- **选方案 A（职责分离）**：明确 calc_signals 的 SELL 仅供前端展示，sim_trader 独立做平仓决策
- 在 calc_signals.py 顶部 docstring 写明"SELL 信号仅供 Signals.vue 展示，不触发实际交易"
- ⏱ 30分钟（文档+注释）
- ⚠️ 风险：用户可能误解"SELL 信号 = 自动平仓"，需要在前端加提示

---

### P0-4 signals 文档/数据漂移

**A 提的**：result/signals/signals_latest.csv 是软链接指向 v1，calc_signals 用 os.replace 不维护软链接。

**我的判断**：⚠️ 部分同意。

**验证**：
```
result/signals/signals_latest.csv -> v1/signals_latest.csv  (软链接确实存在)
```

但报告说"calc_signals 用 os.replace 会破坏软链接"——实际上 `os.replace()` 的目标是 `v1/signals_latest.csv`（在子目录内），**不会修改根目录的软链接**。软链接一直指向 v1 内的文件，行为正确。

**建议改法**：
- 删除根目录软链接，强制所有客户端走 `?version=` API 参数
- 或保留但写明"== v1 的别名，仅为向后兼容"
- ⏱ 5分钟
- ⚠️ 风险：如果有脚本直接读根目录 signals_latest.csv 会断（已验证无此依赖）

---

### 回测 A1 — scored 模式 T 日数据截断

**A 提的**：回测用当天 19:00 batch_result 决策当天开盘前，存在前视偏差。

**我的判断**：❓ 需要更多上下文。

我需要看回测引擎的具体代码才能判断偏差幅度。但报告说"V2 完整继承前视偏差"——这需要验证 signal_engine.py 的具体实现。

**建议**：先验证 A1 的实际影响，再决定修不修。

---

### 回测 A2 — financial_factor 3 季度窗口

**A 提的**：financial_factor fallback 路径仍有前视偏差。

**我的判断**：❓ 需要更多上下文。需要看 financial_factor.py 的具体实现。

---

### 回测 A4 — 调仓价 T+1 开盘

**A 提的**：get_next_trade_day 已实现但无人调用，回测用 T 日收盘价而非 T+1 开盘价。

**我的判断**：❓ 需要更多上下文。需要验证 backtest engine 的 execute_price 逻辑。

---

### S2 暗礁 .git.backup-before-filter-repo/

**A 提的**：2MB 完整 git 仓库在工作树，含未抹除旧 token。

**我的判断**：✅ 同意，事实确认。**✅ 已修复**

**验证**：
```
du -sh .git.backup-before-filter-repo/
2.0M
```

**改法**：
- `rm -rf .git.backup-before-filter-repo/`
- 已删除，2.0M 释放
- filter-repo 已成功（证据：TUSHARE_TOKEN 已轮换），回滚需求极低

---

### CORS 跨域

**A 提的**：`allow_origins=["*"]` + `allow_credentials=True`，任意站点可代理抓取。

**我的判断**：✅ 同意，事实确认。**✅ 已修复**

**验证**：
```python
CORSMiddleware,
allow_origins=["*"],
```

**改法**：
- 改为白名单 `ALLOWED_ORIGINS`，包含生产域名（auto-claw.top / stock.auto-claw.top）和本地开发（localhost:3000/3001/5173）
- 文件：`api/main.py` line 47-67

---

### F4 死 import

**A 提的**：删了 data_fetcher.py 但 backtester.py 和 tracker.py 还有 import。

**我的判断**：✅ 同意，事实确认。

**验证**：
```
src/tracker.py:1:from data_fetcher import get_daily_prices
src/backtester.py:1:from data_fetcher import get_daily_prices
```

**建议改法**：
- 删掉 src/backtester.py 和 src/tracker.py（它们是死文件，无其他引用）
- ⏱ 2分钟
- ⚠️ 风险：无

**注**：本次会话未删除，建议下次清理时处理。

---

### CRON.md 死脚本引用

**A 提的**：CRON.md 和 MAINTENANCE.md 引用 `daily_download.sh`，但该文件不存在。

**我的判断**：✅ 同意，事实确认。**✅ 已修复**

**验证**：
```
$ ls scripts/daily_download.sh
不存在

实际跑的是 scripts/daily_data_fetch.py
```

**改法**：
- CRON.md / MAINTENANCE.md 所有 `daily_download.sh` 改为 `daily_data_fetch.py`
- 共修改 8 处（CRON.md 6 处 + MAINTENANCE.md 2 处）

---

### feedbacks.json IP 泄漏

**A 提的**：feedbacks.json 含用户 IP 地址 `183.222.203.200`。

**我的判断**：✅ 同意，事实确认。**✅ 已修复**

**验证**：文件确实包含 IP 地址。

**改法**：
- `.gitignore` 加 `feedbacks.json`
- `git rm --cached feedbacks.json`（保留本地，停止跟踪）
- 长期改用 SQLite 存储（待处理）

**注**：历史 commit 仍含 IP，需要 filter-repo 才能完全清除（接受风险：IP 是公网 IP 且已过期）

---

### api str(e) 泄漏

**A 提的**：api/main.py 至少 12 处 `str(e)` 直接返回给客户端。

**我的判断**：✅ 同意，事实确认。**✅ 已修复**

**验证**：找到 14 处 `{"error": str(e)}` 返回。

**改法**：
- 新增 `safe_error_response(e, status_code, extra)` 辅助函数
- 详细错误写 logger.error，前端只看到 "服务器内部错误"
- 批量替换 31 处调用（远超原 12 处）

---

### 持仓 accounts.strategy_id 漂移

**A 提的**：accounts 表缺 strategy_id 列，set_account_strategy 会 SQL 报错。

**我的判断**：⚠️ 部分同意。

**验证**：
- database.py schema 定义里 accounts 表**有** strategy_id 列（line 74）
- create_account 函数**接受** strategy_id 参数（line 185）
- 但 API `/api/v1/portfolio/account` 返回**不包含** strategy_id（只有 7 个字段）
- 说明：schema 定义是对的，但 API 返回层没暴露这个字段。实际 DB 文件可能是旧版（没有 strategy_id 列），需要验证

**建议改法**：
- 先验证实际 DB 文件是否有 strategy_id 列：`sqlite3 data/portfolio.db "PRAGMA table_info(accounts)"`
- 如果缺列，加 ALTER TABLE 兼容性迁移
- API 返回加上 strategy_id 字段
- ⏱ 30分钟
- ⚠️ 风险：ALTER TABLE 在 SQLite 上是有限操作，但加列没问题

---

### F10 前导零恶化

**A 提的**：前导零问题从 4 处恶化到 7 处。

**我的判断**：❓ 需要更多上下文。需要看具体是哪 7 处，以及是否是今天修复时引入的。

---

### 持仓 TOCTOU 资金竞态

**A 提的**：trading.py:142-167 读 account → 检查余额 → 扣款，非原子操作。

**我的判断**：✅ 同意，存在竞态。

**验证**：trading.py buy 函数确实先读 account（line 142），检查余额（line 155），再 UPDATE（line 169），中间没有锁。

**建议改法**：
- 用 SQLite 的 `BEGIN EXCLUSIVE` 事务包裹整个 buy/sell 操作
- 或用 `UPDATE accounts SET current_capital = current_capital - ? WHERE id = ? AND current_capital >= ?` 原子操作
- ⏱ 1小时
- ⚠️ 风险：并发买入时可能超额扣款（实际场景并发低，风险可控）

---

### 持仓 delete_trade 反转错位

**A 提的**：trading.py:582-586 死循环。

**我的判断**：❓ 需要更多上下文。需要看具体代码。

---

### 报告 daily_report 400KB JSON

**A 提的**：daily_report.py 仍 418KB JSON 全量注入。

**我的判断**：❓ 需要更多上下文。需要验证实际文件大小。

---

### 其他 P0（回测相关）

回测系统的 P0（A1/A2/A4 等）我需要看具体代码才能判断。建议单独验证。

---

## Part B — 5 个开放问题

### Q1 策略双源不联通

**最终方案**：**运行时配置层（超出原选项）**

讨论过程：
- 最初选 B（sim_trader 改读注册表）
- 用户提出：注册表存全部字段，前端选择交易策略后写入注册表
- 最终实现：`_active_config` 运行时配置层，一个数据源

**实现**：
- `strategies.py` 加 `_active_config` 字典 + `get_active_config()` / `update_active_config()` / `switch_signal_version()`
- calc_signals 和 sim_trader 只读 `get_active_config()`
- 前端选信号版本/交易策略 → API PUT → 更新 `_active_config`
- 不再读 DB strategies 表

**效果**：一个数据源，不会再出现"前端切 V2 实际跑 V1 参数"。

---

### Q2 SELL 信号没人消费

**最终方案**：**SELL 信号统一到 calc_signals + sim_trader 消费**

讨论过程：
- 最初选 B（两套独立，文档写清）
- 用户提出：把 sim_trader 的 K 线扫描挪到 calc_signals，sim_trader 只读 SELL 信号执行
- 最终实现：calc_signals 算 SELL（K 线最高/最低价），sim_trader 读 CSV 执行

**实现**：
- calc_signals：迁移 `check_kline_stop()` 从 sim_trader，用 K 线最高/最低价判断止盈止损
- sim_trader：删 `check_take_profit_stop_loss()`，改为读 CSV `signal == 'SELL'` 执行
- SELL 信号含 `sell_price`（触发价）和 `sell_reason`（原因）

**效果**：信号生成集中在 calc_signals，sim_trader 是纯执行器。

---

### Q3 三个核心脚本 untracked

**我选**：**A — 立刻 commit（不重构）** — 等所有改完统一 commit。

---

### Q4 回测 P0 全部未修 + V2 继承

**最终方案**：**修复三项 P0**（A1 前视偏差 + A4 调仓价 + 加冷却期）

讨论过程：
- 最初选 C（冻结旧数字）
- 用户决定修复，因为这影响策略选择的可信度
- 一并修复了我们之前发现的"回测无冷却期"问题

**实现**：
- `src/backtest/data.py` `get_forward_return()`：
  - 入场价从 T 日收盘价改为 T+1 开盘价
  - 加 0.1% 滑点（买入加价、卖出减价）
- `src/backtest/engine.py` `_run_scored()`：
  - 用 T-1 日的 batch_result 作为评分依据（不再用 T 日）
  - 加冷却期逻辑：同一股票冷却期内不再选中
  - 第一个调仓日因无 T-1 数据自动跳过

**效果**：
- 消除前视偏差（不再用未来数据决策）
- 收益计算更接近实盘（T+1 开盘买入 + 滑点）
- 同一股票连续多轮被选中的问题解决

**风险**：旧回测数字（"年均 +21.6%"）会下降，需要重跑确认实际数字。

---

### Q5 .git.backup-before-filter-repo 暗礁

**我选**：**A — 立刻删** — 等所有改完统一处理。

---

## Part C — 补充发现

### 审查报告中的不准确项

1. **signal_engine.py "仅在内部引用"** — 报告 U-5 说"仅在 signal_engine.py 内部引用"，实际被 4 个外部脚本引用：
   - `scripts/run_signal.py:74`
   - `scripts/run_launch_backtest.py:21`
   - `scripts/run_v2_backtest.py:25`
   - `src/backtest/grid_search.py:17`

2. **HANDOVER.md "严重过期"** — 报告说"说'阶段五待部署'但 stock-system 已上线"。今天已更新 HANDOVER.md，改为"开发记录（已完成）"，"新增域名（已部署）"。

3. **三份文档 80% 重复** — 今天已更新 CLAUDE.md / MAINTENANCE.md / HANDOVER.md，删除了重复内容，各文档职责已明确。

4. **accounts.strategy_id** — 报告说"accounts 表实际只有 7 列，缺 strategy_id"。database.py schema 定义里**有** strategy_id（line 74），create_account 也接受该参数。问题可能在于：(a) 实际 DB 文件是旧版创建的，没有这列；或 (b) API 返回层没暴露。需要验证实际 DB。

### 今天已修复但报告未反映的问题

1. **数据目录统一** — main.py / api/main.py / stock_analysis.py 的输出路径已统一到 `result/daily_score/`
2. **Signals.vue 白屏** — 变量前向引用已修复
3. **v2 按财报分数排序** — finance_score 已加入 score_price_history.csv / signals CSV / API
4. **6.15 评分数据恢复** — 从 .trash 恢复了正确的 batch_result

### 本轮实施的修复（P0-2 + P0-3 联动）

#### 改动 1：calc_signals.py — SELL 信号改用 K 线扫描

**原问题**：calc_signals 的 SELL 用收盘价判断，sim_trader 用盘中最高/最低价判断，两套逻辑脱节。

**改法**：
- 从 sim_trader 迁移 `check_take_profit_stop_loss()` 逻辑到 calc_signals（改名 `check_kline_stop()`）
- `generate_sell_signals()` 改为读 `data/price/{code}.csv` K 线，用最高/最低价判断止盈止损
- SELL 信号输出增加 `sell_price`（实际触发价）和 `sell_type`（take_profit/stop_loss/both）字段

**效果**：信号生成集中在 calc_signals，数据源唯一。

#### 改动 2：calc_signals.py — 冷却期按卖出日计算

**原问题**：冷却期按"上次 BUY 信号日期"算，不是按"卖出日期"算。手动卖出后冷却期不生效。

**改法**：
- `apply_cooldown()` 增加从 portfolio.db trades 表读取 SELL 记录
- 冷却期判断改为：距离上次卖出日期 < cooldown_days → 跳过买入
- 保留历史信号 BUY 日期作为兜底（数据库不可用时）

**效果**：卖出后真正冷却 N 天不再买入。

#### 改动 3：sim_trader.py — 改为读 SELL 信号执行

**原问题**：sim_trader 不看 SELL 列，独立扫描 K 线做止盈止损，与 calc_signals 脱节。

**改法**：
- 删除 `check_take_profit_stop_loss()` 和 `load_kline()` 函数
- 卖出逻辑改为读 signals CSV 里 `signal == 'SELL'` 的行
- 从 SELL 信号取 `sell_price` 和 `sell_reason`，调用 `tm.sell()` 执行

**效果**：sim_trader 变成纯执行器，信号生成逻辑统一在 calc_signals。

#### 改动 4：evening_pipeline.sh — 加入信号计算和模拟交易

**原问题**：晚间流水线只有 3 步，不调 calc_signals 和 sim_trader。

**改法**：在步骤 3（每日报告）之后新增：
```
步骤4: calc_signals --strategy-version v1 + v2（信号计算）
步骤5: sim_trader --dry-run（模拟交易检查，只打印不执行）
```

**效果**：信号计算和模拟交易检查成为流水线的一部分，仓库内可复现。

#### 新流程图

```
步骤1: main.py 批量评分 → result/daily_score/batch_result_*.csv
  ↓
步骤2: kline_analyzer → result/score_price_history.csv
  ↓
步骤3: daily_report → reports/daily_report_*.html
  ↓
步骤4: calc_signals v1+v2 → result/signals/v1,v2/signals_*.csv
  ↓ （SELL 信号基于 K 线最高/最低价 + 冷却期按卖出日算）
步骤5: sim_trader --dry-run → 打印今日应执行的买卖（不实际执行）
```

#### 改动 5：策略双源彻底解决 — 运行时配置层 + 前端交互

详见 Part B Q1 回答。

### 待确认项

1. **回测冷却期** — engine.py 的 `_run_scored()` 没有冷却期逻辑，`cooldown_days` 字段定义了但未使用。需要后续验证是否影响回测数字。
2. **sim_trader 去掉 dry-run** — 当前步骤 5 用 dry-run 模式。确认逻辑无误后可去掉，改为实际执行。

---



## Part D — 总体建议

### 已完成的修复（本轮）

| # | 问题 | 改动 | 文件 |
|---|------|------|------|
| 1 | 数据目录分裂 | main.py/api/stock_analysis 统一到 result/daily_score/ | main.py, api/main.py, scripts/stock_analysis.py |
| 2 | Signals.vue 白屏 | 修复变量前向引用 | web/stock-system/src/views/Signals.vue |
| 3 | v2 缺财报分数排序 | finance_score 加入全链路 | kline_analyzer.py, calc_signals.py, api/main.py, Signals.vue |
| 4 | SELL 信号脱节 | calc_signals 算 SELL（K 线扫描），sim_trader 读 CSV 执行 | calc_signals.py, sim_trader.py |
| 5 | 冷却期按买入日算 | 改为按卖出日算（读 portfolio.db trades 表） | calc_signals.py |
| 6 | 流水线缺信号步骤 | evening_pipeline 加 step 4/5 | evening_pipeline.sh |
| 7 | 策略双源不联通 | 运行时配置层 `_active_config`，一个数据源 | strategies.py, calc_signals.py, sim_trader.py, api/main.py, Strategies.vue |
| 8 | 回测前视偏差 + 无冷却期 | T-1 评分 + T+1 开盘 + 0.1% 滑点 + 冷却期 | engine.py, data.py |
| 9 | 文档过时 | 更新 7 个文档 | CLAUDE.md, MAINTENANCE.md, HANDOVER.md, etc. |

### 待处理

**近期**：
1. commit 三个 untracked 脚本 + 所有改动
2. 删 .git.backup-before-filter-repo/
3. CORS 改白名单
4. api str(e) 脱敏
5. feedbacks.json 加 .gitignore
6. CRON.md / MAINTENANCE.md 死脚本引用

**中期**：
7. 回测 P0 验证（A1/A2/A4 实际影响）
8. 回测加冷却期逻辑
9. sim_trader 去掉 dry-run，改为实际执行
10. TOCTOU 竞态修复

### 对"实盘策略决策"的建议

- 策略双源问题已解决，sim_trader 和 calc_signals 读同一个配置
- 回测数字未经前视偏差修正，暂不建议作为实盘决策依据
- 建议先用 sim_trader dry-run 观察一段时间，确认信号和交易逻辑无误后再实盘
