# 代码审查报告 - 股票操作系统 (Stock System)

> 审查范围：HANDOVER.md 列举的 HANDOVER 阶段一~四 全部产出
> 审查日期：2026-06-12
> 审查对象：`scripts/calc_signals.py`、`src/portfolio/`、`web/stock-system/`、`web/stock-alert/`、`scripts/evening_pipeline.sh` 等

按严重程度分级（🔴严重 / 🟠中度 / 🟡轻微），每条都附定位 (`file:line`) 和复现/修复方向。

---

## 1. 持仓管理后端 `src/portfolio/`

### 🔴 1.1 `get_trade_stats` 的 SQL JOIN 产生笛卡尔积，盈亏统计完全错误

**位置**：`src/portfolio/database.py:369-381`

```sql
FROM trades t1
JOIN trades t2 ON t1.code = t2.code AND t2.type = 'BUY'
WHERE t1.account_id = ? AND t1.type = 'SELL'
```

每一条 SELL 都会和该股票历史上**所有 BUY** 笛卡尔配对。假设 600519 买过 3 次、卖过 2 次：
- 每次 SELL 配 3 个 BUY，返回 6 行（其中只有 3 行匹配对应的那次 BUY）
- `return_rate` 用 `t1.price - t2.price`，全部汇总后求和直接错
- win/loss 计数会膨胀

**影响**：`TradingManager.get_stats()` 返回的胜率、平均盈亏、盈亏比都是错的。前端 `Stats.vue` 实际没接这个接口（写死随机数），所以没爆；但一旦接通就会显示假数据。

**修复方向**：用 FIFO/LIFO 配对逻辑（用子查询或窗口函数定位到匹配的那次 BUY）；或维护一张 `trade_lots` 中间表。

---

### 🔴 1.2 印花税计算逻辑错误（A 股印花税卖出时一律收取，与盈亏无关）

**位置**：`src/portfolio/trading.py:125`

```python
stamp_tax = amount * 0.001 if price > position['cost_price'] else 0  # 印花税（仅盈利时）
```

A 股印花税卖出方单边 0.1%（千分之一），**与是否盈利无关**。亏损卖出也收。注释里的"仅盈利时"是错的。

**修复**：
```python
stamp_tax = amount * 0.001  # A股卖出单边千分之一
```

---

### 🔴 1.3 资金/持仓操作无事务、无锁，竞态可能导致超额买入

**位置**：`src/portfolio/trading.py:46-74`、`database.py:_get_conn`

整个模块每次方法单独开连接、单独 commit。多步业务（读 current_capital → 计算 → 写 current_capital → 写 positions → 写 trades）横跨多个连接，没有显式事务，两个并发请求理论上都读到相同余额并各自扣减，导致超额。

**修复**：
- 启用 WAL 模式：`conn.execute("PRAGMA journal_mode=WAL")` + `PRAGMA foreign_keys=ON`
- 用 `with conn:` 进入事务
- 关键操作加 `BEGIN IMMEDIATE` 或 `asyncio.Lock`

---

### 🔴 1.4 卖出时清仓后历史持仓不可追溯

**位置**：`src/portfolio/database.py:215-217`

```python
if shares >= row['shots']:  # typo? 实际是 'shares'
    cursor.execute('DELETE FROM positions WHERE id = ?', (row['id'],))
```

清仓时直接 DELETE 行，已清仓股票的入场价、首次买入日、买入分数全部丢失，无法做历史复盘；下次再买同代码会当成新仓。

**修复**：
- 软删除（加 `closed_at` 字段）或
- 保留 `trade_lots` 表（每笔买入独立行，卖出时减 shares 不删行）

---

### 🟠 1.5 外键约束未启用

**位置**：`src/portfolio/database.py:_get_conn`

```python
conn = sqlite3.connect(self.db_path)
conn.row_factory = sqlite3.Row
return conn
```

SQLite 的外键默认是关闭的。Schema 里的 `FOREIGN KEY (account_id) REFERENCES accounts(id)` 形同虚设——可以删除 account 后留下孤儿 positions/trades/daily_nav。

**修复**：连接后立即 `conn.execute("PRAGMA foreign_keys=ON")`。

---

### 🟠 1.6 清仓时未校验卖出数量

**位置**：`src/portfolio/database.py:200-226`

`reduce_position` 接收 `shares: int`，未检查：
- 负数（`shares=-100` 会变成"加仓"——`shares - (-100) = shares + 100`）
- 字符串（会抛异常但没保护）
- 浮点（shares 字段是 INTEGER，但 Python 端不强制）

**修复**：方法入口加 `if shares <= 0: raise ValueError`。

---

### 🟠 1.7 单例 `get_db()` 在多线程下不安全

**位置**：`src/portfolio/database.py:401-409`

```python
def get_db() -> PortfolioDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = PortfolioDB()
    return _db_instance
```

FastAPI 是异步多线程的，两个并发请求同时进入 `if _db_instance is None` 都为真，会创建两个 `PortfolioDB` 实例，连接池分裂。

**修复**：用 `threading.Lock` 或在模块级初始化时直接创建（依赖注入）。

---

### 🟠 1.8 A 股最小买入 100 股约束未校验

**位置**：`src/portfolio/trading.py:30`

`shares: int` 不检查 `>= 100` 也不检查是 100 的整数倍。前端 `Portfolio.vue` 的买入表单也没校验。

**修复**：方法入口加 `if shares < 100 or shares % 100 != 0: raise ValueError`。

---

### 🟠 1.9 手续费未做最低 5 元处理

**位置**：`src/portfolio/trading.py:51, 124`

```python
fee = amount * 0.0015  # 万分之1.5佣金
```

A 股大多数券商规定佣金不足 5 元按 5 元收。这里按 1.5‱ 算，1 万元的买入佣金是 1.5 元，**实际会被收 5 元**，导致 `current_capital` 扣减不足。

**修复**：
```python
fee = max(amount * 0.0015, 5.0)
```

---

### 🟠 1.10 不支持分红派息、送股除权

`trading.py.buy/sell` 直接按 `price * shares` 算金额。持仓期间：
- 现金分红不入账（导致 `current_capital` 比实际少，`daily_nav` 偏差）
- 送股/转股不调整 `shares`

**影响**：长期持仓的统计会系统性失真。

**修复**：增加 `dividend_event` 入账方法、复权处理逻辑。

---

### 🟡 1.11 account_id 总是 default，假装支持多账户

**位置**：`src/portfolio/trading.py:28, 47, 103, 164, 169, 174, 195, 204, 228`

所有方法都 `get_default_account()`，传 `account_id` 的接口都未真正生效。如果 `account_id=2` 的请求到来，仍会操作 account 1。

**修复**：把 `account_id` 做成方法参数；或当前阶段显式不支持多账户，去掉 API 里 `account_id` 字段。

---

### 🟡 1.12 add_position 加仓时 buy_score 字段不更新

**位置**：`src/portfolio/database.py:178-184`

加仓时只更新 shares/cost_price/current_price，不更新 `buy_score`。但 `buy_score` 字段语义是"首次买入的信号分"，保持不变是对的；但代码里没有注释说明，后人可能误改。

**修复**：加一行注释 `buy_score 保留首次买入分数`；或重命名 `initial_buy_score`。

---

## 2. 信号计算 `scripts/calc_signals.py`

### 🟠 2.1 日期格式未做 `20160104.0` 浮点归一化

**位置**：`scripts/calc_signals.py:40`

```python
df['date'] = df['date'].astype(str)
```

若 `score_price_history.csv` 的 date 列是 pandas 读出的 float64（如 `20160104.0`），转 str 后是 `'20160104.0'`，后续 `target_date` 比较、`groupby` 全部失败——可能 0 个信号。

前端 `loader.js:36-39` 的 `normalizeDate` 做了 `replace(/\.0$/, '')`，但 Python 端没有。

**修复**：
```python
df['date'] = df['date'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
```

---

### 🟠 2.2 用 groupby 取 target_date 行只取第一条，潜在数据漂移

**位置**：`scripts/calc_signals.py:91-98`

```python
target_row = group[group['date'] == target_date]
if target_row.empty:
    continue
```

`groupby('code')` 后，同一 code 在同一日理论上只有一行。但 `kline_analyzer` 历史上有过同 code 重复写入的 bug，重复行未被去重。

**修复**：先 `df.drop_duplicates(['code', 'date'], keep='last')` 再计算。

---

### 🟠 2.3 `signals_latest.csv` 注释说"软链接"，实际是覆盖写入

**位置**：`scripts/calc_signals.py:124-127`

```python
# 同时保存最新信号的软链接/副本
latest_file = SIGNALS_DIR / "signals_latest.csv"
signals_df.to_csv(latest_file, index=False, encoding='utf-8-sig')
```

跨平台/重启时符号链接可能丢。注释写"软链接"误导——`to_csv` 不会创建符号链接。

**修复**：改成 `os.replace()` 原子替换；或 `Path.symlink_to` 配合 try/except 失败则 copy。

---

### 🟡 2.4 早盘/尾盘数据缺失时窗口长度变短

**位置**：`scripts/calc_signals.py:70-78`

`target_idx < lookback - 1` 时用 0 开头计算，**信号可能被早期少量高分拉高**。比如 7 天数据只有 2 天，其中一天 100 分，7 日均 = 50 分，会触发假信号。

**修复**：窗口不足时该股票直接跳过，或 `np.mean` 加 `min_periods`。

---

### 🟡 2.5 没有去重 BUY 信号冷却逻辑

signal 文件里只标记 `BUY` 或空，但同一只股票连续 3 天都 ≥30 分会产生 3 条 BUY。HANDOVER.md 说推荐"冷却 1 天"参数，但 calc_signals.py 完全没有实现。

**修复**：增加 `--cooldown-days` 参数，对比上次信号日期。

---

## 3. 前端 `web/stock-system/`

### 🔴 3.1 Portfolio.vue 完全没有接入后端 API

**位置**：`web/stock-system/src/views/Portfolio.vue:255-266`

```javascript
function saveData() {
  localStorage.setItem('portfolio_positions', JSON.stringify(positions.value))
  localStorage.setItem('portfolio_trades', JSON.stringify(positions.value))
}
```

**严重后果**：
- 持仓只存在浏览器 localStorage，多设备/多浏览器/清缓存/换电脑 → 全部数据丢失
- 后端 SQLite 实际上一直是空库
- 实际真金白银交易的前端和数据库**完全脱节**

**修复**：接 `api/main.py` 的 portfolio endpoints（目前 API 还没实现），先停用 Vue 里的 mock。

---

### 🔴 3.2 Portfolio.vue 三个核心功能都是 `alert('xxx 开发中')`

**位置**：`web/stock-system/src/views/Portfolio.vue:196-208`

```javascript
function lookupStock() {}                  // TODO
function refreshPrices() { alert('...') }  // TODO
function sellStock(pos) { alert('...') }   // TODO
```

**股票操作系统没有卖出功能、没有自动取价、没有股票名联想**。是"半成品"。

**修复**：接后端 API；至少 `sellStock` 弹窗 + 调用 `/api/v1/portfolio/sell`。

---

### 🔴 3.3 Stats.vue 收益曲线是 `Math.random()` 假数据

**位置**：`web/stock-system/src/views/Stats.vue:209-222`

```javascript
for (let i = 0; i < 300; i++) {
  ...
  value = value * (1 + (Math.random() - 0.48) * 0.02)  // 随机漫步！
  values.push(Math.round(value))
}
```

整张"年化 +35%、最大回撤 5%"的漂亮曲线**完全是随机数**。所有 stat 数字（`totalTrades`, `winTrades` 等）都是 `ref(0)` 默认值，UI 上看到的全是 `0`。

**风险**：用户（自己）以为系统跑起来了，看到红色正收益以为策略真的稳。**必须明确标注 MOCK** 或下掉整个 Stats 页面。

**修复**：
1. 暂时把标题改成"收益统计（待接通后端）"
2. 接入 SQLite 查询（`/api/v1/portfolio/stats`）

---

### 🟠 3.4 持仓统计中 `availableCash` 硬编码 100 万

**位置**：`web/stock-system/src/views/Portfolio.vue:181`

```javascript
const availableCash = ref('1,000,000.00')
```

任何时候都是 100 万，买入 N 次后仍显示 100 万。

**修复**：从 `account.current_capital` 动态算。

---

### 🟠 3.5 confirmBuy 没有数值校验

**位置**：`web/stock-system/src/views/Portfolio.vue:210-253`

- `price=""` 直接相乘 → `NaN`
- `shares="abc"` → `Number('abc')` = NaN
- `shares=50`（不足 100 股）也接受
- 负数价格也接受

**修复**：提交时校验 `Number(price) > 0 && Number(shares) >= 100 && Number(shares) % 100 === 0`。

---

### 🟠 3.6 Dashboard 解析 `财报/资金流向/行业相对强弱` 中文列名

**位置**：`web/stock-system/src/views/Dashboard.vue:104-110`

```vue
<td>{{ item['财报'] || '-' }}</td>
<td>{{ item['资金流向'] || '-' }}</td>
<td>{{ item['行业相对强弱'] || '-' }}</td>
```

`batch_result_*.csv` 的列名实际是 `financial_score`、`zj_flow_score`、`hy_diff_score`（英文下划线）。前端读中文 key 全是 `undefined`，最终显示 `-`。

**修复**：与 `batch_result.csv` 实际列名对齐，先 print 一行真实 CSV 确认。

---

### 🟠 3.7 loader.js 的 CSV 解析脆弱（字段含逗号会破）

**位置**：`web/stock-system/src/data/loader.js:14-36`、`web/stock-alert/src/data/loader.js:13-33`

```javascript
const vals = lines[i].split(',')
```

CSV 标准允许字段用 `"..."` 包裹并内部含逗号，例如 `name="中国,平安"`。当前 split 直接破坏。

股票名 `"比亚迪,002594"`、`"*ST,华映"` 都会让列错位。

**修复**：用简单 RFC4180 parser，或 `PapaParse` 库。

---

### 🟠 3.8 module-level `cache` 永不过期

**位置**：`web/stock-system/src/data/loader.js:12, 30`、`web/stock-alert/src/data/loader.js:11, 27`

```javascript
const cache = {}
async function fetchCSV(path) {
  if (cache[path]) return cache[path]   // 永远用第一次的结果
  ...
}
```

晚间流水线 19:00 更新了 `signals_latest.csv`，但前端只要加载过就一直显示昨天的数据，**没有手动刷新看不到新数据**。

**修复**：
- 加 `?v=${Date.now()}` 时间戳
- 或 cache TTL 60 秒
- 或干脆去掉 cache

---

### 🟡 3.9 Dashboard 排序按 `current_score` 字符串字典序

**位置**：`web/stock-system/src/views/Dashboard.vue:168-175`

```javascript
const sorted = scores
  .filter(s => s.total_score && !isNaN(Number(s.total_score)))
  .sort((a, b) => Number(b.total_score) - Number(a.total_score))
```

这个其实写对了（先 Number 转换）。但 `Signals.vue:182-185` 同样写法只对 `current_score/avg7_score/close_price` 三个 key 转换；`code`（如 "002001"）和 `name` 字段也走 Number → NaN → 0 比较。string code 排序会变成字典序："100" > "20"，但我们想的是 "002001"。

**修复**：`code` 字段直接字符串比较（已经是正确行为），去掉通用 Number 转换。

---

## 4. Nginx 配置 `web/stock-system/nginx.conf`

### 🔴 4.1 `/data/` alias 暴露整个项目根

**位置**：`web/stock-system/nginx.conf:38-58`

```nginx
location /data/ {
    alias /home/admin/AUTO-STOCK/;
    autoindex off;
    ...
}
```

`alias` 指向项目根，意味着：
- `https://stock.auto-claw.top/data/portfolio.db` → 直接下载持仓数据库（含真实账户和交易记录）
- `https://stock.auto-claw.top/data/.env` → 可能泄露配置
- `https://stock.auto-claw.top/data/result/batch_result_20260315.csv` → 评分结果

**修复**：
```nginx
location /data/signals/    { alias /home/admin/AUTO-STOCK/result/signals/; }
location /data/daily_score/{ alias /home/admin/AUTO-STOCK/result/daily_score/; }
location /data/price/      { alias /home/admin/AUTO-STOCK/data/price/; }
# 绝对不要 location /data/ 兜底
```
同时显式 `deny portfolio.db`、`deny *.py`、禁目录遍历。

---

### 🟠 4.2 没有 CORS 限制 / 鉴权

**位置**：`web/stock-system/nginx.conf:46-56`

`add_header Access-Control-Allow-Origin *;`——任何域名都能跨域读 CSV。

持仓系统如果将来加 `/api/v1/portfolio/...`，可能同样无鉴权暴露。

**修复**：
- API 加 JWT 或 session 鉴权
- 静态 CSV 仅允许同源或白名单域名

---

### 🟡 4.3 没有 CSP / HSTS 等现代安全头

**位置**：`web/stock-system/nginx.conf:20-23`

只设置了 `X-Frame-Options`、`X-Content-Type-Options`、`X-XSS-Protection`，缺：
- `Content-Security-Policy`（防 XSS）
- `Strict-Transport-Security`（强制 HTTPS）
- `Referrer-Policy`
- `Permissions-Policy`

**修复**：补齐。

---

## 5. 晚间流水线 `scripts/evening_pipeline.sh`

### 🟠 5.1 步骤 1 失败不会回滚步骤 0（数据准备）

cron `0 19 * * 1-5` 假设 17:00 `daily_data_fetch.py` 已经跑完。**如果 17:00 的下载任务因网络问题延迟，19:00 流水线直接对不完整数据评分**，会产出错误的 batch_result 进而污染 calc_signals 报告。

**修复**：在步骤 1 之前检查 `data/daily_market/YYYYMMDD.csv` 是否存在且非空；不存在则 abort。

---

### 🟠 5.2 calc_signals 失败但 daily_report 仍跑

**位置**：`scripts/evening_pipeline.sh:42-56`

步骤 3 失败时 `|| fail` 会终止整个 shell。但步骤 4 之前会先备份 `reports/index.html`，如果步骤 4 失败，旧 index.html 还在；问题是步骤 1/2/3 任何一步失败都不会更新 index.html，**但 3 之前已经更新过的 index.html 还指向昨天**。

**修复**：每日备份 `reports/index.html` → `reports/index.html.bak`；流水线全部成功后才覆盖。

---

### 🟡 5.3 日志文件名按日期，多进程同日会互相 append

**位置**：`scripts/evening_pipeline.sh:11`

```bash
LOG="logs/evening_pipeline_${TARGET_DATE}.log"
```

如果手动重跑（`bash evening_pipeline.sh 20260612`）两次，log 会追加，统计耗时会被 `tee` 重叠输出。

**修复**：用 `> ` 重定向 + 时间戳 `logs/evening_pipeline_${TARGET_DATE}_$(date +%H%M%S).log`，或加 `set -o noclobber`。

---

### 🟡 5.4 不区分交易日/节假日

cron `0 19 * * 1-5` 在节假日（如春节、国庆调休）也会跑。`calc_signals.py` 内部有"找不到日期就用最近交易日"逻辑，所以不会崩，但 `daily_report.py` 同样依赖 step1 写出非空 batch_result——节假日没有数据 → 报告可能显示"无数据"或直接报错。

**修复**：先检查 `data/calendar/trade_days.csv` 是否包含 TARGET_DATE，跳过非交易日。

---

## 6. 跨模块的横向问题

### 🟠 6.1 API 服务 `api/main.py` 没有 portfolio 端点

**位置**：`api/main.py` 全文

`/api/v1/stock/search`、`/api/v1/financial/score/{code}` 等都是给 financial-report 用的。**portfolio 模块的 TradingManager 从未被 API 暴露**。意味着即便前端想接后端，也没有接口可接。

**修复**：补 `/api/v1/portfolio/buy`、`/sell`、`/positions`、`/stats`、`/nav` 等。

---

### 🟠 6.2 时区未统一

- `database.py` 用 `datetime('now')` (UTC)
- `trading.py.save_snapshot` 用本地时间 `datetime.now()`
- 前端 `new Date().toISOString()` 是 UTC
- `signals_YYYYMMDD.csv` 用 `YYYYMMDD` 字符串（无时区）

可能导致：19:00 跑出 `signals_20260612.csv`（东八区 19:00 = UTC 11:00），但 Portfolio.vue 用 `Date().toISOString().split('T')[0]` 拿到 UTC 日期 2026-06-12。**巧合一致**——但跨时区或夏令时切换时会出现 `signals_20260612.csv` 实际是 6/11 的数据。

**修复**：统一 `Asia/Shanghai` 时区。

---

### 🟠 6.3 备份脚本改动未在仓库内

`HANDOVER.md` 第 64 行说 `/home/admin/scripts/r2_backup.py` 改了，但**该文件不在 AUTO-STOCK 仓库内**——服务器路径 `/home/admin/scripts/` 不在 git 里。意味着这次改动没有 commit、没有版本控制、没有 review。

**修复**：把 r2_backup.py 移到 `scripts/` 下、或建立独立小仓库。

---

### 🟡 6.4 没有端到端测试

CLAUDE.md 说 `python -m pytest` 可跑，但 portfolio/signals 的端到端测试**没有**。`HANDOVER.md` 提到的 TC-001~TC-010 只写了 ✅，没有对应 pytest 文件。

**修复**：补 `tests/test_portfolio.py`（买入→持仓→卖出→统计）、`tests/test_calc_signals.py`（窗口期、边界、缺失数据）。

---

## 7. 总结与优先级

| 类别 | 数量 | 必修（影响数据正确性或安全） |
|------|------|-------------------------------|
| 🔴 严重 | 7 | 1.1, 1.2, 3.1, 3.2, 3.3, 4.1, 6.1 |
| 🟠 中度 | 11 | 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 2.1, 3.4, 3.5, 3.6, 3.7, 3.8, 5.1, 5.2, 6.2 |
| 🟡 轻微 | 7 | 1.11, 1.12, 2.4, 2.5, 4.3, 5.3, 5.4, 6.4 |

**部署前必修**（按 ROI 排序）：
1. `4.1` — 30 秒加一个 `deny` 规则，挡掉 portfolio.db 泄露
2. `3.3` — Stats.vue 假数据误导决策
3. `1.2` — 印花税 0.1% 改成"仅盈利时"会少扣 0.1%，每天跑会累积错
4. `1.1` — `get_trade_stats` 笛卡尔积，任何接 Stats 的下游都会爆
5. `3.1/3.2` — Portfolio.vue 完全 mock，必须明确告诉用户"功能未完成"

**架构层必修**：
- 启用 SQLite WAL + 外键
- 抽 `account_id` 真正参数化
- API 暴露 portfolio endpoints

---

## 8. 审查未涉及但建议跟进

- `web/financial-report/` 未审查（CLAUDE.md 标记"已完成"）
- `src/backtest/` 未审查（CLAUDE.md 标记"已完成"）
- `api/main.py` 只扫了端点列表，未逐个审查
- 部署相关的 systemd unit、Cloudflare R2 备份脚本均未在仓库内

---

> 报告人：Claude (MiniMax-M3)
> 报告路径：`docs/stock-system/CODE_REVIEW.md`
