# 子报告：Web 前端

> 范围：
> - `web/financial-report/`（auto-claw.top 根，财报评分）— `src/views/Home.vue`、`src/views/Detail.vue`、`src/main.js`、`src/App.vue`
> - `web/stock-alert/`（auto-claw.top/yujing/，个股预警）— `src/views/StockKline.vue`、`src/data/loader.js`、`vite.config.js`
> - `web/stock-system/`（stock.auto-claw.top/，股票操作系统）— `src/views/Dashboard.vue`、`Signals.vue`、`Portfolio.vue`、`Stats.vue`、`Strategies.vue`、`src/data/loader.js`、`src/data/cache.js`、`src/data/strategy.js`、`src/main.js`
> - 三个项目的 `package.json` / `vite.config.js`，以及部署侧 `/etc/nginx/conf.d/auto-claw.top.conf`、`/etc/nginx/conf.d/stock-system.conf`、`deploy/stock-system.conf`、`web/stock-system/nginx.conf`
> - 关联后端：`api/main.py`（CORS 配置）、`result/` 与 `data/price/` 数据源
>
> 严重程度评级：P0=功能错误/P1=性能或安全/P2=可改进/P3=小问题
> 审查日期：2026-06-14

---

## 1. 概览

三个 Vue 3 + Vite 前端工程整体可用，业务流程能跑通：财报评分通过 FastAPI 实时计算；个股预警以静态 CSV 形式由 nginx 直读，零后端依赖；股票操作系统通过 `/api/v1/portfolio/*` 走真实持仓/交易/统计，配合本地缓存层做实时性优化。

**主要问题集中在 4 个方向**：

1. **数据规模与性能**：stock-alert 在 dist 目录硬塞 392 MB 的 5529 个 CSV，单 JS 包 2.7 MB（未 minify）；每次搜索/选股都全量加载 `score_price_history.csv` 在浏览器内 in-memory 过滤。
2. **缓存策略被破坏**：stock-system Dashboard 在 `onMounted` 调 `clearAllCache()`，使 smartFetch 的"日加载 1 次"语义失效；`/data/` 静态文件的绕过 fetch 又绕过了 smartFetch 体系。
3. **代码卫生**：.bak / .backup / 旧 web/ 根目录 整套遗留前端未清理；Home.vue 留 14 处 `console.log` 调试；K线 `buildKlineOption` 在 Home/Detail 间 80 行复制粘贴；axios 与 fetch 混用。
4. **CLAUDE.md 描述与实现不符**：CLAUDE.md 提到 stock-system 有"月度统计"和"信号策略（规划中）"，但 Stats.vue **完全没有月度聚合代码**，Strategies.vue 是 5 个路由的实页面但 CLAUDE.md 路由表只列了 4 个。

总体质量评分 3/5——能用、能跑、有亮点（K线 + 评分叠加 + 持仓计算都对），但细节、清理、性能余量、文档一致性都还有显著改进空间。

---

## 2. 关键发现（按严重程度降序）

### [P1] stock-alert dist 内置 392 MB CSV，nginx 每次全量服务

- 位置：`/home/admin/AUTO-STOCK/web/stock-alert/dist/data/price/`（5529 个文件，392 MB）+ `dist/data/score_price_history.csv`
- 现象：每次 `vite build` 后，**手动**把 `AUTO-STOCK/data/price/*.csv` 复制到 `dist/data/price/`（DEVELOPMENT_STATUS.md:65），把 `result/score_price_history.csv` 复制到 `dist/data/`。
- 后果：
  - 部署时 392 MB 通过 git 同步（虽然 git 没跟踪 dist，但实际部署机器之间需要 `rsync`），第一次部署很慢。
  - 搜索任何股票都会先 fetch 全量 `score_price_history.csv`（约 5500 行）——N 个用户并发 = N × 500KB 流量。
  - `AUTO-STOCK/data/price/000001.csv`（103 KB）等文件 nginx 直接 serve，没有 CDN / 没有 range 支持。
- 证据：
  - `web/stock-alert/dist/data/price/` 5529 个文件，`du -sh` = 392 MB。
  - `web/stock-alert/src/data/loader.js:47-49` `loadScoreHistory()` 拉全量 CSV 不分页。
- 建议：考虑用 nginx alias 直接指向 `AUTO-STOCK/data/price/`（参考 stock-system.conf 已经这样做了 `/data/price/`），stock-alert/dist 内不放数据；前端只通过 nginx alias 读共享数据。这与 stock-system 的部署模式一致。

### [P1] vite `minify: false` 让 3 个项目 JS 包都 ≥ 2.7 MB

- 位置：
  - `web/financial-report/vite.config.js:16` `minify: false`
  - `web/stock-alert/vite.config.js:16` `minify: false`
  - `web/stock-system/vite.config.js:16` `minify: false`
- 现象：stock-alert `dist/assets/index-*.js` 2.7 MB（gzipped 前），gzip 后 ~700 KB；financial-report dist 2.8 MB。
- 后果：移动端首屏白屏时间明显；CSP `'unsafe-inline'` 也是 minify: false 后的回退方案（stock-system.conf:27）。
- 建议：生产构建开 `minify: 'esbuild'`（vite 默认）或 `terser`。Vite 5 默认 'esbuild'，性能与 terser 相当但构建快。

### [P1] Dashboard.vue onMounted 强制清缓存，破坏 T1_DATA 设计

- 位置：`web/stock-system/src/views/Dashboard.vue:155` `clearAllCache()`
- 现象：进入首页每次都清所有缓存（内存 + localStorage），然后再通过 smartFetch 重拉。
- 后果：T1_DATA 设计本意是"日加载 1 次"（cache.js:62），Dashboard 显式清掉后变成"每次都拉"，背离了 evening_pipeline 19:00 算一次信号的频率假设。对后端 QPS 是 N 用户 × 全量 signals 列表的压力。
- 证据：
  - `web/stock-system/src/data/cache.js:60-63` T1_DATA TTL = 24h
  - `Dashboard.vue:154-157` `onMounted(async () => { clearAllCache(); try { const signalsResp = await loadSignals() ...`
- 建议：Dashboard 应当复用 smartFetch 的缓存，仅在用户主动点击刷新时调 `clearAllCache()`；或者改用 `forceRefresh: false`（默认）走正常缓存路径。

### [P1] Portfolio.vue refreshPrices 绕过 smartFetch 直拉静态文件

- 位置：`web/stock-system/src/views/Portfolio.vue:600-654`
- 现象：`refreshPrices` 内部直接 `fetch('/data/score_price_history.csv?_t=' + Date.now())` 解析 CSV（Portfolio.vue:604-627），完全绕过 smartFetch 缓存层。
- 后果：与 cache.js 的"统一缓存管理"理念冲突；该文件 500 KB 量级且没走任何 TTL 策略；并且 Portfolio.vue 自己实现的 CSV 解析没有引号转义支持（line 606-619 用 `line.split(',')`），遇到行业名带逗号就错位。
- 证据：`Portfolio.vue:604-608`
  ```js
  const resp = await fetch('/data/score_price_history.csv?_t=' + Date.now())
  const text = await resp.text()
  const lines = text.trim().split('\n')
  if (lines.length < 2) return
  const headers = lines[0].split(',')
  ```
- 建议：要么走 `loader.js` 里加一个 `loadScorePriceLatest()` 智能缓存接口（复用 `parseCSV` 支持 RFC4180）；要么在 `updatePrices` API 里直接读后端 SQLite/CSV 让后端给出最新 close_price。

### [P1] stock-alert 重复拉全量 score_price_history.csv 做大盘K线

- 位置：`web/stock-alert/src/data/loader.js:47-49, 57-59, 63-87`
- 现象：
  - `loadScoreHistory()` 拉全量 CSV（不分页、不按 code 预过滤）。
  - `getStockData(code, ...)` 内部 `Promise.all([loadScoreHistory(), loadPrice(code)])`——选一只股票就重拉整个评分历史。
  - `searchStocks(keyword)` 也是全量过一遍 `loadScoreHistory()` 然后去重再筛。
- 后果：换一只股票耗时 = fetch 大文件 + 解析 + 过滤 5500 行；切换时间范围不重拉数据（renderChart 内 filterByDate），但切换股票就全量重读。
- 证据：`loader.js:66-87`
- 建议：使用后端 API 提供 `/api/v1/stock/search` 风格的查询接口；或者把 `score_price_history.csv` 按 code 拆分为 `/yujing/data/scores/{code}.json` 减小单次请求大小。最低成本可接受方案：首次 `loadScoreHistory()` 之后**缓存到 sessionStorage**，后续切换股票直接读缓存。

### [P1] stock-alert 死代码 + 变量作用域混乱（不影响功能但极易引发回归）

- 位置：`web/stock-alert/src/views/StockKline.vue:244-254`
- 现象：
  - line 245-247 声明 `tpPoints = []; slPoints = []; markLines = []` 立即重置。
  - line 248 `if (costPrice.value && costPrice.value > 0 && costPrice.value < 1e10)` 进入后只算 `targetTp = costPrice.value * (1 + takeProfitRate.value / 100)` 和 `targetSl`，**但既不 push 到 tpPoints/slPoints，也不 push 到 markLines**。
  - 实际真正的 push 在 line 421-445（`if` 块外）重新进入相同 `if (costPrice.value...)` 条件。
- 后果：当前运行 OK（功能没坏），但 line 244-254 是**死代码**——任何后续维护者会误以为这里就是止盈止损填充点。如果之后有人在 line 248 后面加 `markLines.push(...)`，会因为 markLines 已被清空造成诡异 bug。
- 证据：见上述 line range
- 建议：删除 line 244-254 整段死代码；保留 line 421-445 单一填充点。

### [P1] financial-report Home.vue 留 14 处 console.log 调试日志

- 位置：`web/financial-report/src/views/Home.vue:381, 383, 384, 387, 388, 391, 401, 402, 403, 406, 408, 412, 415, 431, 433, 438`
- 现象：开发期调试用的 `console.log` 没清理。
- 后果：用户打开浏览器控制台可见股票代码、API URL、API 返回全文，**可能泄露 PII/内部结构**。
- 建议：删除或改为 `if (import.meta.env.DEV) console.log(...)`。

### [P1] 跨域硬编码 stock-system → stock-alert

- 位置：`web/stock-system/src/data/loader.js:266-276` `gotoYujing`
- 现象：`window.open('https://auto-claw.top/yujing/?${params.toString()}', '_blank')` 硬编码域名。
- 后果：本地开发（`localhost:3002`）想跳转到本地 stock-alert（`localhost:3001`）必须改源码；不同部署环境（staging/prod）需要再改。
- 建议：抽到环境变量 / `import.meta.env.VITE_YUJING_URL` 缺省值为生产 URL；或通过 query 参数 / 父页面传 base URL。

### [P2] 多处 .bak / .backup 死文件未清理

- 位置：
  - `web/financial-report/src/views/Home.vue.bak`、`Home.vue.backup`
  - `web/financial-report/src/views/Detail.vue.bak`、`Detail.vue.backup`
  - `web/financial-report/src/assets/styles.css.backup`
- 现象：未在 git 跟踪但留在工作树。
- 后果：编辑器文件树噪音；新人 onboarding 困惑。
- 建议：删除。

### [P2] 旧 web/ 根目录整套前端未清理

- 位置：
  - `web/index.html`、`web/index_simple.html`、`web/maintenance.html`
  - `web/src/`、`web/app.py`、`web/package.json`、`web/vite.config.js`
  - `web/components/backtest_page.py`、`web/components/score_dashboard.py`
- 现象：项目根 `web/` 目录下还有一整套 Flask + 旧 Vue 前端的"老"代码，与 `web/financial-report/`, `web/stock-alert/`, `web/stock-system/` 并存。
- 后果：CLAUDE.md 中 描述的 web/ 结构是新三件套（`financial-report/`, `stock-alert/`, `stock-system/`），但根 `web/index.html` 等老文件路径在浏览器中仍可访问，Nginx 配置未屏蔽。
- 证据：
  - `web/index.html`、`web/src/App.vue`、`web/components/backtest_page.py` 均存在。
  - `/etc/nginx/conf.d/auto-claw.top.conf` 根 location 服务的是 `web/financial-report/dist`（line 35-37），老的 `web/index.html` 实际无法被访问（被 `try_files` 拦截到 `financial-report/dist/index.html`）——但代码本身留作垃圾。
- 建议：删除整个 `web/src/`、`web/index.html`、`web/index_simple.html`、`web/maintenance.html`、`web/app.py`、`web/components/`、`web/package.json`、`web/vite.config.js`，并从 `git status` 验证。

### [P2] K线 buildKlineOption 在 Home.vue 和 Detail.vue 复制 80 行

- 位置：
  - `web/financial-report/src/views/Home.vue:212-304`（`buildKlineOption`）
  - `web/financial-report/src/views/Detail.vue:469-561`（相同实现）
- 现象：除了 `grid` 参数，几乎逐字相同。
- 后果：未来改 tooltip 或 K线样式需要两处同步；已经观察到 4 次小差异（grid 参数、axisLabel.fontSize）。
- 建议：抽到 `web/financial-report/src/components/KlineCard.vue` 或 `src/lib/klineOption.js`，Home/Detail 共用。

### [P2] axios vs fetch 风格不统一

- 位置：
  - financial-report 用 `axios`（Home.vue:139 `import axios from 'axios'`、Detail.vue:376）
  - stock-alert 完全不用 axios（虽然 package.json:13 声明了）
  - stock-system 完全不用 axios（虽然 package.json.json 都没列 axios）
  - financial-report `Detail.vue:876` 提交反馈用 `fetch`（不混用）
- 现象：同项目内 fetch / axios 混用，跨项目更不一致。
- 建议：统一为 fetch（无依赖、tree-shakeable）；从 stock-alert 和 stock-system 移除 axios 依赖。

### [P2] stock-system main.js 路由表与 CLAUDE.md 不一致

- 位置：
  - `web/stock-system/src/main.js:7-12` 实际有 5 个路由：`/`, `/signals`, `/portfolio`, `/stats`, `/strategies`
  - `CLAUDE.md` 第 247-258 行描述的页面路由只有 4 个（缺 `/strategies`）
  - App.vue 导航栏 5 个 link 都有
- 现象：Strategies 页面存在并工作（已读 src/views/Strategies.vue 前 50 行确认），但 CLAUDE.md 漏列。
- 建议：补全 CLAUDE.md。

### [P2] CLAUDE.md 提到"信号策略"和"月度统计"未实际实现

- 位置：`CLAUDE.md:247-258` "Stats 收益曲线、月度统计、交易分析"
- 现象：Stats.vue 已读全文，**无任何"按月聚合"代码**——只显示净值曲线 + 总资产曲线 + 胜率/盈亏比/最大回撤等。navHistory 是后端给的全量日数据，**没有 groupBy(month)**。
- 建议：要么补月度聚合表，要么改 CLAUDE.md 删掉这个描述。

### [P2] nginx stock-system.conf CORS 头多余

- 位置：`/etc/nginx/conf.d/stock-system.conf:59, 67, 74, 80`
  ```
  add_header Access-Control-Allow-Origin "https://stock.auto-claw.top" always;
  ```
- 现象：同源部署（前后端都在 stock.auto-claw.top 域下），浏览器不发 CORS 请求。
- 后果：无害但增加响应体积、与 CSP（line 27 `connect-src 'self'`）有微妙矛盾——CSP 不允许跨域，nginx 又设了 CORS。
- 建议：删除 CORS 头；与 CSP 保持一致。

### [P2] Detail.vue initChart 用 setTimeout 轮询 DOM 渲染

- 位置：`web/financial-report/src/views/Detail.vue:693-704`
- 现象：
  ```js
  const initChart = () => {
    if (!chartRef.value) { setTimeout(initChart, 500); return }
    if (!result.value || !result.value.scores) { setTimeout(initChart, 500); return }
    ...
  }
  ```
- 现象：用 setTimeout 500ms 轮询 2 次（最多 1 秒），如果数据还没好就一直等。
- 后果：极端情况下图表可能延迟 1-2 秒才显示；CPU 空转。
- 建议：改用 `await nextTick()` 一次性（Detail.vue:681 `await nextTick(); setTimeout(initChart, 100)` 已经有这一行了——再套 setTimeout 轮询就重复）。

### [P2] Portfolio.vue 与 Stats.vue 缺 404 兜底路由

- 位置：`web/stock-system/src/main.js:6-12`
- 现象：路由表无 `path: '/:pathMatch(.*)*'` 兜底。
- 后果：访问 `/foo` 仍然渲染 Dashboard（vue-router 默认行为），用户无感知。
- 建议：加 NotFound 组件。

### [P2] financial-report 缺 404 兜底

- 位置：`web/financial-report/src/main.js:8-11` 同样无 `*` 路由
- 后果：访问 `/xyz` 停留在 Home 视图。
- 建议：同上。

### [P2] stock-alert 搜索重复逻辑——loader.js 内的 searchStocks 独立，StockKline.vue 内联实现

- 位置：
  - `loader.js:123-141` `searchStocks(keyword)` 返回去重后的列表
  - `StockKline.vue:168-172` `onSearch` 直接调 `searchStocks(searchKeyword.value)`，无额外筛选
  - `StockKline.vue:175-183` `onEnterSearch` 又调 `onSearch` 再取第一条
- 现象：onSearch 没用防抖（loader.js 内 100% 全量遍历），用户每输入一个字就 fetch + 解析 + 全量过滤一遍。
- 后果：输入"600519"会触发 6 次 fetch（"6"、"60"、"600"、"6000"、"60001"、"600019"——其实 query.length < 2 时 loader.js 不返回）。
- 证据：`loader.js:124-141` 没有长度判断，`StockKline.vue:168-172` 没 debounce
- 建议：和 Home.vue 一致加 300ms debounce（Home.vue:356）。

### [P3] stock-system `web/stock-system/src/components/` 空目录

- 位置：`web/stock-system/src/components/`（空）
- 建议：删目录或加 README 占位。

### [P3] stock-alert 同上，financial-report `src/components/` 也空

- 建议：清理或加 placeholder。

### [P3] Dashboard.vue "进首页清缓存"行为可能导致用户每次都看到 flash of old data

- 位置：`Dashboard.vue:155` `clearAllCache()` 在 onMounted 中
- 现象：每次进入 Dashboard 都清缓存+重拉。在信号量大时（5000+ 只）会显示 200ms+ 的 loading。
- 建议：把"清缓存"按钮放到 UI 显式位置（参考 user 主动刷新场景），默认走缓存。

### [P3] Stats.vue 净值曲线 yAxis formatter 截断精度

- 位置：`web/stock-system/src/views/Stats.vue:261-262` `formatter: function (val) { return val.toFixed(2) }`
- 现象：净值 0.987654 显示 "0.99"——两位小数对单位净值（接近 1）可能显示不出微小波动。
- 建议：保留 4 位小数（`toFixed(4)`）。

---

## 3. 改进建议（非问题，但有更好做法）

1. **数据归一**：考虑把 stock-alert 与 stock-system 共用的 `score_price_history.csv` 通过 nginx alias 共享读取（stock-system 已经这么做），stock-alert/dist 内不再包含 data/ 目录。源代码 + 构建产物分离。

2. **类型化**：三个 .vue 文件大量 `ref(null)`、`.value.xxx`，零 TypeScript。引入 `vue-tsc` / `defineProps<...>()` / `<script setup lang="ts">` 可以消灭一类低级错误（Pos/Neg/String 混用、null deref）。

3. **错误边界**：每个路由加 `errorCaptured` / global error handler，把 API 失败更友好地展示。

4. **CSP 进一步收紧**：`stock-system.conf:27` `script-src 'self' 'unsafe-inline'` 因 vite 生成的 inline `<script>` 引入；改用 nonce 或 SHA-256 hash 可以删 `'unsafe-inline'`。

5. **历史快照**：股票操作系统每天 19:00 才落一条 nav 记录（依赖 evening_pipeline），但前端无任何"数据未刷新"提示。如果用户上午打开页面看到的是昨天下午的数据，没有任何 hint。

6. **删除老的 `web/` 根目录**：见 [P2]。

7. **统一错误处理**：Home.vue / Detail.vue / StockKline.vue / Portfolio.vue / Stats.vue 各自有 `loading` / `error` 模式，重复代码多。提取为 composable（如 `useApiList`）。

8. **Portfolio.vue 修改总资产 modal** 是 destructive 操作（清空账户），目前用 `confirm()` 浏览器原生气泡——考虑二次确认或输入 "RESET" 关键字确认。

---

## 4. 需要核实的不确定项

1. **stock-alert "大盘K线不显示" 修复状态**：DEVELOPMENT_STATUS.md 第 35 行说"待处理"，但 git log 较新；当前 StockKline.vue 没有 `market: []` 之后的处理代码（已确认是空 `market: []`），推测尚未修复。
2. **stock-alert `loader.js` 全量 CSV 加载是否构成实际问题**：单文件 500KB 量级，浏览器解析 < 100ms，N 用户并发才有意义。建议在 server 上用 `nginx $binary_remote_addr` 限速。
3. **stock-alert dist 392 MB 是否对实际部署机器有压力**：未实际运行 `rsync` 测速，理论 1Gbps 内网下约 4 秒——可以接受。
4. **Portfolio.vue `refreshPrices` 直拉 `/data/` 是否对应 nginx alias 存在**：已确认 `/data/score_price_history.csv` 在 stock-system.conf:78-81 有 alias。
5. **CORS 配置多重**：API 端 `allow_origins=["*"]` + stock-system.conf 又设了 `Access-Control-Allow-Origin https://stock.auto-claw.top`——哪一个生效？前者只在跨域场景生效（反代后是 same-origin），后者是多余但不影响。
6. **stock-system 部署是否真的依赖 gunicorn**：`/etc/nginx/conf.d/auto-claw.top.conf` 第 76-82 行 `/api/` 反代到 8000 端口，**同一份 API 给两个域**（auto-claw.top + stock.auto-claw.top）。stock-api.service 在 deploy/ 下，**未启动/未确认**。
7. **CLAUDE.md 提到的"持仓数据库"位置**：`data/portfolio.db` 是 SQLite，但 stock-system.conf line 85 deny 了对 `*.db` 的访问——所以 API 端读写没问题，但前端任何 `/data/portfolio.db` 直读会 404。**正确**。

---

## 5. 评分（1-5，5 = 优）

| 维度 | 分数 | 评价 |
|------|------|------|
| 正确性 | 4 | 主要功能流程正确；止盈止损死代码、initChart 轮询、refreshPrices 绕过缓存等不直接破坏功能但隐藏风险 |
| 可维护性 | 2 | .bak/.backup/老 web/根 大量遗留；K线选项卡 80 行重复；axios/fetch 混用；Home.vue 14 处 console.log；CORS/缓存策略多套混用 |
| 性能 | 3 | 全量 CSV 加载、未 minify、stock-alert dist 392 MB、T1_DATA 缓存被 Dashboard 主动破坏——多个 P1 性能项 |
| 文档 | 3 | CLAUDE.md 描述与实现有多处不符（缺 strategies 路由、月度统计未实现） |
| 部署 | 3 | nginx 配置基本正确，安全 deny 规则充分；CORS 多余、dist 内置 392 MB 数据反模式、源码/产物分离未做 |
| **总评** | **3 / 5** | 功能可用、流程跑通，但有 4 类共 11 项 P1 级别的工程债务需要清理 |

---

## 6. P0/P1/P2 统计

- **P0**（功能错误）：**0**
- **P1**（性能 / 安全 / 正确性隐患）：**8**（P1-1 stock-alert dist 392MB、P1-2 未 minify、P1-3 Dashboard clearAllCache、P1-4 Portfolio refreshPrices 绕过缓存、P1-5 stock-alert 全量 CSV、P1-6 死代码作用域混乱、P1-7 console.log 泄露、P1-8 跨域硬编码）
- **P2**（可改进 / 死代码 / 一致性）：**8**
- **P3**（小问题）：**3**

### Top-3 严重问题

1. **P1-1 stock-alert dist 内置 392 MB CSV**（连带 P1-5 全量加载）：每次构建手动复制数据，构建产物与数据未分离，nginx 直服务 5529 个文件，无 CDN / range 支持。建议改用 nginx alias 共享 `AUTO-STOCK/data/price/`。
2. **P1-3 Dashboard.vue 主动 clearAllCache()**（连带 P1-4 refreshPrices 绕过缓存）：T1_DATA "日加载一次"的缓存语义被前后端多处破坏，造成不必要的后端 QPS。属于设计-实现不一致。
3. **P1-7 financial-report Home.vue 14 处 console.log 调试日志**（连带 [P2] 死代码 / 旧 web/ 根）：开发期脏数据未清理，留给生产环境是 PII/内部结构泄露隐患。
