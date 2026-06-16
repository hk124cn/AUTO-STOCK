# 子报告：stock-system 信号系统（v1/v2 切换 + 卖信号集成）

> 范围：
> - 后端：`scripts/calc_signals.py` (463 行)、`scripts/sim_trader.py` (343 行)、`src/backtest/signal_engine.py` (399 行)、`src/backtest/strategies.py` (102 行)、`src/portfolio/database.py`、`src/portfolio/trading.py`、`api/main.py`（信号 + 策略相关段）
> - 前端：`web/stock-system/src/views/Signals.vue` (592 行)、`Strategies.vue` (729 行)、`Portfolio.vue` (1088 行)、`Stats.vue` (510 行)、`data/loader.js`
> - 数据：`result/signals/v1/signals_*.csv`、`v2/signals_*.csv`、SQLite `data/portfolio.db`
> - 流水线：`scripts/evening_pipeline.sh`、`MAINTENANCE.md`
>
> 严重程度评级：P0=功能错误或重大隐患 / P1=性能/安全/可维护性 / P2=可改进 / P3=小问题
> 审查日期：2026-06-16

## 1. 概览

本轮要审查的"v1/v2 信号版本切换 + 卖信号集成"是用户特别标注的重点。代码本身写得不错——`strategies.py` 用 frozen dataclass 注册表 + 文档说明如何扩展 v3/v4、API 自动从注册表读、前端用 localStorage + 缓存键加 version 维度防止串数据——这是**有设计感的工程实现**。

**但有两个致命结构性问题**：
1. **关键脚本从未 commit**：calc_signals.py、sim_trader.py、signal_engine.py 都是 `git status` 中的 Untracked 文件。这意味着它们**不在 git 历史的视野里**——任何 rollback、对比、code review 都看不到完整变更，可能随时被覆盖或丢失。
2. **完全没接 cron**：evening_pipeline.sh 只有"评分→分析→报告"3 步，**既不调 calc_signals 也不调 sim_trader**。MAINTENANCE.md 承诺的"19:30 信号计算"和"19:00 晚间流水线"在 git 里都没有对应实现。整套信号系统在仓库内是个"孤立模块"，依赖仓库外的系统 cron 才能跑起来。

**对 V1/V2 切换的评价**：合理且工程化，扩展点清晰，文档质量高（strategies.py 顶部 22 行注释解释了"加 v3 改哪里、不用改哪里"）。**对卖信号集成的评价**：有坑——calc_signals 与 sim_trader 各自独立扫描持仓止盈/止损，数据源不同、判定时机不同，**可能双重平仓或漏平仓**。此外"卖信号"写入了 signals CSV 但**前端只展示不执行**，sim_trader 不消费 signals 里的 SELL 列，自己做独立止盈止损扫描——"卖信号集成"其实是 calc_signals 算出来给 Signals.vue 看用，并不真的驱动平仓。

总评：**3/5**。代码好，但缺少工程闭环（未 commit、未接 cron、卖信号"集成"语义不闭环）。

## 2. 关键发现（按严重程度降序）

### [P0-1] 关键脚本全部 untracked，git 历史完全缺失

- **位置**：`scripts/calc_signals.py`、`scripts/sim_trader.py`、`src/backtest/signal_engine.py`
- **现象**：`git status` 显示三个文件全部 `Untracked files`，从未被 `git add` 过。`strategies.py` 已 commit 但只是把"策略注册表"提交了，计算引擎本身没进库。
- **后果**：
  - 任何代码审查、PR diff、回滚、对比分支都看不到这些文件的完整历史
  - 用户记的 "2026-06-12 接续任务完成" HANDOVER 写"信号计算脚本"已交付，但交付物不在 git 里
  - 服务器上能跑 ≠ 仓库里有版本控制；新机器 clone 后这三个文件直接缺失，sim_trader / calc_signals 完全跑不起来
  - 与同目录其它脚本（evening_pipeline.sh、daily_report.py 等）的版本基线脱节
- **证据**：
  ```
  $ git status
  Untracked files:
      scripts/calc_signals.py
      scripts/sim_trader.py
      src/backtest/signal_engine.py
  ```
- **建议**：立即 `git add scripts/calc_signals.py scripts/sim_trader.py src/backtest/signal_engine.py src/backtest/strategies.py && git commit -m "feat(signals): calc_signals + sim_trader + signal_engine + v1/v2 策略注册表"`。如果担心敏感信息（如密码、token）已硬编码，先 grep 一遍确认。

### [P0-2] 信号流水线未接入 evening_pipeline.sh，"19:30 信号计算"是文档承诺而非代码事实

- **位置**：`scripts/evening_pipeline.sh` line 1-39
- **现象**：evening_pipeline.sh 只有 3 步——批量评分、kline_analyzer、daily_report。**完全没有调用 `calc_signals.py` 或 `sim_trader.py`**。但 `MAINTENANCE.md` 第 117 行明确写"19:30 信号计算 | `scripts/calc_signals.py`（v1 + v2）"。
- **后果**：
  - 仓库内可复现性：clone 此仓库后跑流水线，只会产生 batch_result 和 daily_report，**根本不会产生任何 signals_latest.csv**
  - 实际看到 result/signals/v1/signals_latest.csv 是 2026-06-16 08:32 的——说明服务器上有系统 cron 在调，但**这个 cron 不在仓库里**，本审查看不到
  - 如果运维误删服务器 cron，sim_trader 永远不跑，整个"实盘策略决策"决策 = 0
  - 之前 06-14 审查报告（`05-report-system/final/SUBREPORT-report-pipeline.md` line 92-105）已经指出过 sim_trader 在旧版 evening_pipeline.sh 中以 `|| echo` 静默失败被吞掉，**本轮发现：sim_trader 已经被从流水线里整个删掉了**——更糟
- **建议**：
  1. 在 evening_pipeline.sh 加上步骤 4 调用 calc_signals.py v1 + v2（两次调用）
  2. 在 evening_pipeline.sh 加上步骤 5 调用 sim_trader.py --mode SIM --dry-run（先 dry run 看持仓触达情况）
  3. 或者把 sim_trader 调成真下单（去掉 --dry-run），但用 `|| fail "sim_trader"` 严格失败模式
  4. 在 README/MAINTENANCE.md 写明"sim_trader 必须配 cron"或"已内置进 evening_pipeline.sh"

### [P0-3] 卖信号"集成"是伪命题：calc_signals 写 SELL 列但 sim_trader 不消费

- **位置**：
  - 写：`scripts/calc_signals.py:277-364` `generate_sell_signals()`
  - 消费：`scripts/sim_trader.py:188-231` `check_take_profit_stop_loss()`
- **现象**：
  - calc_signals.py 的 `generate_sell_signals()` 读 portfolio.db → 遍历持仓 → 比对 score_price_history 当天 close_price → 写 SELL 行到 signals CSV
  - sim_trader.py 第 244 行 `buy_signals = signals[signals['signal'] == 'BUY']` **只过滤 BUY**，完全不看 SELL 列
  - sim_trader.py 独立调用 `check_take_profit_stop_loss()` 扫描 data/price/{code}.csv K 线做止盈止损
  - 数据源不同：calc_signals 用 `score_price_history.csv` 当天 close_price，sim_trader 用 `data/price/{code}.csv` 全量 K 线（包括盘中 high/low）
  - 判定逻辑不同：calc_signals 用收盘价一次性对比，sim_trader 用盘中高低价多次扫描
- **后果**：
  - "卖信号集成"在 calc_signals 和 sim_trader 之间是**断开的**：calc_signals 算的 SELL 信号只是写到 CSV 供 Signals.vue 展示，不会触发 sim_trader 平仓
  - **真正的平仓决策在 sim_trader 独立扫描 K 线**——calc_signals 的 SELL 是冗余的装饰品
  - 两个独立扫描可能导致：同一天一个持仓既被 calc_signals 标记 SELL、又被 sim_trader 也触发 sell()，在 trade 表里出现两条 SELL 记录（虽然 sim_trader 的 sell 内部会检查 remaining_shares 防御，但语义重复）
  - 用户问题问的"sim_trader 是否消费卖信号自动平仓"：**答案是 NO**
- **建议**（择一）：
  - **方案 A（推荐）：明确职责分离**——calc_signals 算的 SELL 仅作"提示信号"给前端；sim_trader 独立做平仓决策。文档明确两边各自定义，并在 calc_signals 顶部 docstring 写"SELL 信号仅供 Signals.vue 展示，不触发实际交易"
  - **方案 B：真集成**——calc_signals 算 SELL 后写入 DB 一张 `pending_sell_orders` 表，sim_trader 启动时先消费这张表，再做盘后扫描。两个扫描合并为一个决策点
  - 当前方案的"半集成"是最差的：用户期望"信号触发自动平仓"，实际只有 Signals.vue 看到 SELL 徽章，平仓靠 sim_trader 独立逻辑

### [P0-4] signals 文档/数据漂移：MAINTENANCE.md 描述与实际数据不一致

- **位置**：`MAINTENANCE.md` line 35-37 / `CLAUDE.md` 第 65 行 / `result/signals/signals_latest.csv` 符号链接
- **现象**：
  - `MAINTENANCE.md` line 35-37：`result/signals/` 下 v1/v2 目录
  - 实际 `result/signals/signals_latest.csv` 是一个**符号链接**指向 `v1/signals_latest.csv`：
    ```
    lrwxrwxrwx ... signals_latest.csv -> v1/signals_latest.csv
    lrwxrwxrwx ... signals_20260612.csv -> v1/signals_20260612.csv
    ```
  - calc_signals.py:267-272 用 `os.replace()` 写 `signals_latest.csv`，并**不维护符号链接**
  - 即：v1 永远会"覆盖"根目录的 signals_latest.csv 软链接指向的目标，v2 永远从自己子目录读
  - 但任何想直接读 `result/signals/signals_latest.csv`（不指定版本）的客户端，会**永远拿到 v1 数据**，永远不会拿到 v2
- **后果**：
  - 如果有人写脚本读 `result/signals/signals_latest.csv` 而不带 version，会被锁死在 v1
  - v2 的"首次突破"信号实际**没有人能看到**——除非显式走 API 的 `?version=v2`
  - 6-14 审查（`05-report-system/final/SUBREPORT-report-pipeline.md` line 19）已经指出"signals_latest.csv 实际不是软链接而是覆盖式普通文件"，本轮发现**软链接这次确实存在，但 calc_signals 用 os.replace 会破坏它**：因为 `os.replace(tmp, latest_file)` 是在 `SIGNALS_BASE_DIR / output_subdir` 即 `v1/signals_latest.csv`，**不会**修改根目录的软链接。软链接一直指向 v1 内的 signals_latest.csv，行为正确但**很容易让人误解**
- **建议**：
  - 删掉根目录的软链接 signals_latest.csv 和 signals_20260612.csv（避免误读）
  - MAINTENANCE.md / CLAUDE.md 明确"必须通过 API 选 version"，根目录不再放软链接
  - 或保留软链接但写明"==v1 signals_latest.csv 的别名，仅为向后兼容"

### [P1-1] 卖信号判定用 `score_price_history` 收盘价，可能与 sim_trader 实际成交价偏差

- **位置**：`scripts/calc_signals.py:326` `current_price = float(code_data.iloc[0]['close_price'])`
- **现象**：calc_signals 算 SELL 时从 score_price_history 取当天收盘价，但 sim_trader 真实成交用的是 K 线的最高/最低/收盘扫描。
- **后果**：
  - calc_signals 标记某持仓 SELL 时，前端展示"今日触发止盈"
  - sim_trader 实际可能用比 close_price 更优的 high 价成交（但可能已经在昨天就触发了）
  - 同一持仓出现"信号日 ≠ 成交日"的认知差异
- **建议**：calc_signals 的 SELL 信息只用于前端展示，**不应该用 close_price 反推"止盈价/止损价"**。建议字段改为：
  ```python
  'sell_reason': f"触发于 {check['trigger_date']}，信号日收盘 {current_price:.2f}"
  ```
  明确告知用户触发日是历史某日，不是信号当日。

### [P1-2] calc_signals SELL 信号只看 SIM 账户，未看 REAL

- **位置**：`scripts/calc_signals.py:291` `sim_account = db.get_account_by_mode('SIM')`
- **现象**：卖信号生成硬编码只查 SIM 账户；REAL 持仓的止盈止损**完全没被监控**。
- **后果**：用户问题里说"实盘策略决策 10万本金 v1+总评分"，如果实盘真的持仓了，**没有任何自动机制监控止盈止损**。CLAUDE.md 也说 sim_trader "绝不能给实盘下单"，但**实盘持仓连监控都没有**是更糟的事。
- **建议**：
  - 把 SELL 信号生成逻辑放到 sim_trader.py 之外，做一个 `scripts/check_real_positions.py`，独立监控 REAL 持仓并通过 webhook 推送到用户
  - 或者在 api/main.py 加一个 `/api/v1/portfolio/real/check-stops` 端点，前端 Portfolio.vue 实盘 Tab 自动定期调用并弹窗

### [P1-3] 前端 Signals.vue 排序切换字段逻辑硬编码，扩展性差

- **位置**：`web/stock-system/src/views/Signals.vue:177-178`
  ```js
  const sortField = ref(currentVersion.value === 'v2' ? 'finance_score' : 'avg7_score')
  ```
- **现象**：v1 永远按 avg7_score 排序，v2 永远按 finance_score 排序。如果新增 v3，开发者必须改 Signals.vue 才知道按什么排序。
- **后果**：违背 strategies.py 顶部注释"加 v3/v4 只改注册表"的设计意图。
- **建议**：在 `/api/v1/strategies/versions` 返回里加 `sort_field` 字段（如 v1→avg7_score, v2→finance_score），前端读 API 设置默认 sort。

### [P1-4] calc_signals.py 不带 audit 日志，SELL 信号写入没追溯

- **位置**：`scripts/calc_signals.py:432`
- **现象**：calc_signals 把 SELL 信号 concat 到 BUY 后 `drop_duplicates(subset=['code'], keep='last')`——如果某持仓同一天既被 calc_signals 标记 SELL、又已经出现在前一日 BUY 流水中（重复出现在 BUY 候选），SELL 会"覆盖"BUY（因为 keep='last'）。这本身是合理的（SELL 优先），但**没有任何日志说明发生了什么**。
- **后果**：事后调试"为什么某 code 今天没出现在 BUY"很困难。
- **建议**：在覆盖前打印 `print(f"  ⚠️ {code}: BUY 被 SELL 覆盖（sell_reason={sell_reason}）")`，并考虑写一份 `signals_latest.diagnostics.json` 记录被覆盖/被合并/被冷却过滤的每个 code 的去向。

### [P1-5] sim_trader 不消费 SELL 信号，但与 calc_signals 形成事实上的双重平仓

- **位置**：`scripts/sim_trader.py:204-228`
- **现象**：sim_trader 自己扫 K 线检查止盈止损，与 calc_signals SELL 完全独立。同一持仓可能被两个流程都判定为 SELL。
- **后果**：
  - 实际平仓只发生一次（sim_trader 调 `tm.sell()` 检查 remaining_shares），但 Signals.vue 看到的"SELL 信号"是 calc_signals 算的，**与 sim_trader 实际行为可能不同步**
  - 例如：某持仓昨天就触发了止盈，sim_trader 昨天已平仓；今天 calc_signals 还把它算进 SELL 池（因为 portfolio.db 已 closed，**但 generate_sell_signals 只查 get_positions 不包含已平仓**，所以这条会过滤掉——✅ 防御到位）
  - 但**仍有风险**：sim_trader 独立扫描可能发现 calc_signals 没标的止盈机会（因为 calc_signals 只看 score_price_history 当天，没扫描历史 K 线）
- **建议**：明确两边职责——calc_signals 的 SELL 是"今日信号扫描"，sim_trader 的平仓是"盘中触达执行"，文档说清。

### [P2-1] Strategies.vue 文本"⚠️ 期望值为负，仅供回测研究"写死，扩展性差

- **位置**：`web/stock-system/src/views/Strategies.vue:35`
- **现象**：硬编码了 v2 的负面评价文本。
- **建议**：把"推荐搭配"和"风险提示"作为 Strategy 字段（如 `risk_note: str = ""`）放入 dataclass，通过 API 返回。

### [P2-2] Stats.vue 没有"信号触发次数/命中率"统计

- **位置**：`web/stock-system/src/views/Stats.vue` 整文件
- **现象**：用户问题问"是否有信号相关图表"——答案是**没有**。Stats.vue 只显示净值曲线 + 交易统计，看不到"过去 30 天 BUY 信号触发次数、SELL 触发次数、信号后 5 日平均涨跌"。
- **建议**：加一张"信号 vs 实际成交"的对照图（用 signals_latest.csv 历史数据 join trades 表）。

### [P2-3] Signals.vue "卖出信号"按钮颜色用 `btn-danger`（红色），但实际语义是橙色（止盈止损中性行为）

- **位置**：`web/stock-system/src/views/Signals.vue:36`
  ```html
  <button :class="filter === 'sell' ? 'btn-danger' : 'btn-outline'">
  ```
- **现象**：btn-danger 是红色（#ff4757），通常用于"删除""重置"等破坏性操作。卖出信号本身是"系统自动平仓"中性行为，不应使用 danger 色。
- **建议**：改用 `btn-warning` 或中性色，与下方 SELL 徽章（橙色 #ffa500）保持一致。

### [P2-4] calc_signals.py 生成 SELL 行时 `current_score/avg7_score/finance_score` 都填空字符串

- **位置**：`scripts/calc_signals.py:352-356`
- **现象**：SELL 行的评分字段全部空，API 输出后前端显示 `-`，但用户无法从这条 SELL 信息推断"为什么这支会被卖出"。
- **建议**：SELL 行至少填 `current_score`（卖出日的当日评分），并加上"卖出日评分"列让用户对比"买入日评分 vs 卖出日评分"。

### [P3-1] calc_signals.py:178 finance_score NaN 时静默置 0，可能误导前端

- **位置**：`scripts/calc_signals.py:177-178`
  ```python
  if pd.isna(finance_score):
      finance_score = 0
  ```
- **现象**：NaN 财务评分被静默替换为 0，前端会显示"财务评分 0 分"，但实际是数据缺失而非零分。
- **建议**：保持 NaN，API 层返回 None，前端显示"暂无"。

### [P3-2] result/signals/ 根目录有 2 个软链接容易误导

- **位置**：`result/signals/signals_20260612.csv`、`signals_latest.csv`
- **现象**：两者都是软链接指向 v1。任何读根目录 signals_latest.csv 的脚本（包括 calc_signals 的兼容代码）只会拿到 v1。
- **建议**：删除根目录软链接，强制所有客户端走 `?version=` API 参数。

### [P3-3] sim_trader.py:236 `current_price or cost_price` 在 0 时回退

- **位置**：`scripts/sim_trader.py:238`
  ```python
  position_value = sum(
      (p.get('current_price') or p['cost_price']) * p['shares']
      ...
  )
  ```
- **现象**：如果 `current_price == 0`（数据库写入 0 表示未更新），会回退 cost_price，但 cost_price 也不一定是真实现价，导致估值虚高。
- **建议**：加显式 None 判断 `if p.get('current_price') is None: continue`。

## 3. 改进建议（非问题，但有更好做法）

### S-1：SignalConfig 应支持"移动止盈"而非固定止盈
当前 take_profit/stop_loss 是固定百分比（相对 avg_cost）。更好的做法是 trailing stop（移动止盈）：盈利达到 X 后，止损线提高到成本价 + Y，避免坐电梯。建议在 `Strategy` dataclass 里加 `trailing_stop_pct: float = 0` 字段，0 表示禁用。

### S-2：v1/v2 策略应该有 A/B test 框架
v1 和 v2 同时跑两份 signals，但 sim_trader 只读一个版本（`--strategy-version`）。理想是跑两套模拟仓对比收益。建议增加 `scripts/run_ab_test.py`，同时跑 v1 + v2 各 60 天，对比收益曲线。

### S-3：SignalEngine 的 _get_pb_ratio 对 None 处理不优雅
signal_engine.py:114-116 `if bvps is None or bvps <= 0: return None`——但调用方（candidates.append）没检查 None，sort key 会爆炸（虽然当前 sort_by_pb=False 所以不进 sort 分支，但耦合不清晰）。

### S-4：sim_trader 用 score_price_history 的 close_price 计算 position_value，但 K 线扫描用的是 data/price/{code}.csv
两份价格源**可能不同步**——score_price_history 是经过 kline_analyzer 处理过的（含 finance_score 注入），data/price 是原始 K 线。如果价格基准不一致，平仓金额算出来会偏差。建议统一从 score_price_history 取价。

### S-5：calc_signals 的 cooldown 计算有边界问题
`calc_signals.py:217` `cutoff = (target_dt - timedelta(days=cooldown_days * 2)).strftime('%Y%m%d')`——用 `cooldown_days * 2` 作为截止，但实际 cooldown 判定是 `(target_dt - last_date).days < cooldown_days`。这里 cutoff 是"忽略太老的信号历史"，建议改成 `(cooldown_days * 2) + 5` 留 buffer，否则当 cooldown_days=3 时 cutoff=6 天前可能刚好漏掉第 7 天前但仍在 cooldown 内的旧信号。

## 4. 需要核实的不确定项

| # | 项 | 影响 | 核实方法 |
|---|---|---|---|
| U-1 | 服务器上是否有 cron 调 calc_signals.py 和 sim_trader.py？ | P0：决定整个信号系统是否真的在跑 | 登录服务器 `crontab -l`、`ls /etc/cron.d/`、`systemctl list-timers` |
| U-2 | result/signals/signals_latest.csv 软链接是否在生产环境真有客户端依赖？ | P1：决定删除软链接的风险 | `grep -rn "signals_latest.csv" /home/admin/AUTO-STOCK --include="*.py" --include="*.sh"`（已查：仅 calc_signals.py 内部，无其它客户端） |
| U-3 | portfolio.db 的 SIM 账户当前是否有持仓？ | P1：决定 SELL 信号能否真实触发 | `sqlite3 data/portfolio.db "SELECT count(*) FROM positions WHERE closed_at IS NULL"` |
| U-4 | strategies.py 已 commit 之前的版本里 v1/v2 是同一个 dataclass 还是分开？ | P2：决定 strategies.py 是否需要拆分 commit | `git log --oneline src/backtest/strategies.py` |
| U-5 | signal_engine.py 是 v2 专用还是通用？calc_signals 是否会调用它？ | P2：决定 signal_engine.py 是不是"死代码" | `grep -rn "from src.backtest.signal_engine" /home/admin/AUTO-STOCK --include="*.py"`（已查：仅在 signal_engine.py 内部引用） |

## 5. 评分（1-5，5 = 优）

| 维度 | 评分 | 理由 |
|---|---|---|
| 正确性 | **3** | 卖信号"集成"语义不闭环（P0-3）；evening_pipeline.sh 根本没接 cron（P0-2）；signals_latest.csv 软链接与 calc_signals 行为不一致（P0-4） |
| 可维护性 | **2** | 三个核心脚本完全 untracked（P0-1）；Strategies.vue / Signals.vue 写死版本逻辑（P1-3）；版本切换与策略注册表耦合弱 |
| 性能 | **4** | calc_signals 用了向量化的 groupby + apply、score_dicts 预计算、np.mean 都 OK；sim_trader 的 iterrows 慢但只在 N≤10 的持仓范围 |
| 文档 | **3** | strategies.py 顶部注释清晰（22 行解释 v3/v4 怎么加）；但 MAINTENANCE.md 文档与代码脱节（19:30 信号计算在代码里没实现）；CLAUDE.md "每日晚间流水线" 章节未提 sim_trader |
| 安全性 | **3** | signal API 是只读无需鉴权（合理）；sim_trader 拒绝 REAL 实盘下单（合理 --mode REAL 防护）；但 generate_sell_signals 直接读 portfolio.db 跨模块耦合，没有最小权限隔离 |
| **总评** | **3.0** | **代码好但工程闭环不完整**。最严重的是"未 commit + 未接 cron"，这两个加起来让整套信号系统在仓库内不可复现；其次是"卖信号集成"语义断裂，用户期望的"信号→平仓"链路在 calc_signals 和 sim_trader 之间是断的 |

## 6. 对 V1/V2 切换 + 卖信号集成的明确评价

### V1/V2 策略版本切换：**合理（有小坑）**
- **优点**：strategies.py 用 frozen dataclass 注册表 + 完整字段（threshold/lookback/cooldown/first_break_only/build_days/output_subdir），扩展性极好；前端通过 localStorage + API ?version= + 缓存键加 version 维度三层防御串数据；strategies.py:1-22 顶部注释堪称教科书；Strategies.vue 把版本卡片设计得直观（含三年回测数据 + 推荐搭配 + 风险提示）。
- **小坑**：
  1. Signals.vue:177-178 排序字段硬编码（v2→finance_score, v1→avg7_score）—— 违背"加 v3 只改注册表"承诺
  2. Strategies.vue:35 风险提示文本硬编码"⚠️ 期望值为负，仅供回测研究"—— 应作为 Strategy 字段
  3. cron 没接——evening_pipeline.sh 完全不调 calc_signals.py，v1/v2 信号需要仓库外 cron 才能产出

### 卖信号集成：**有大坑**
- **坑 1（P0-3）**：calc_signals 算 SELL 写 CSV，sim_trader 不消费 SELL 列而独立扫描 K 线。"集成"在数据流上是断的——calc_signals 的 SELL 只给 Signals.vue 看，sim_trader 的平仓决策完全独立。两套逻辑可能不同步。
- **坑 2（P1-1）**：calc_signals 用 score_price_history 当天 close_price 判定 SELL，但实际平仓价由 sim_trader 用 K 线扫描得到。信号日和成交日可能不同，前端显示"SELL 触发于 20260616" 但实际 sim_trader 可能在 20260615 就已平仓。
- **坑 3（P1-2）**：calc_signals 只看 SIM 账户，**REAL 账户持仓完全没有止盈止损监控**。结合 sim_trader 拒绝 REAL 模式的事实，实盘持仓完全暴露在无监控状态。
- **坑 4（P0-2）**：sim_trader 没接 cron。evening_pipeline.sh 完全不调用它。模拟仓 100% 依赖仓库外 cron 才能自动交易。

**综合结论**：卖信号"集成"是一个**半成品功能**——calc_signals 的 SELL 算得很好，但 sim_trader 完全没接它。如果用户真正期待"看到 SELL 信号就自动平仓"，需要把 sim_trader 改成"先消费 SELL 信号再做盘后扫描"，并确保 cron 调起来。