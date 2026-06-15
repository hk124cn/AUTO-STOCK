# 04 Web 前端 — 原始审查笔记

> 审查范围：`web/financial-report/`、`web/stock-alert/`、`web/stock-system/` 三个 Vue 3 + Vite 前端
> 审查日期：2026-06-14
> 仅审查前端源码与部署配置，**未运行** build

---

## 1. 项目结构与构建

| 项目 | 路径 | 部署域 | 基础路径 | 状态 |
|------|------|--------|---------|------|
| financial-report | web/financial-report | auto-claw.top (根) | `/` | 完成 |
| stock-alert | web/stock-alert | auto-claw.top/yujing/ | `/yujing/` | 部分完成 |
| stock-system | web/stock-system | stock.auto-claw.top | `/` | 完成 |

- 三者均为 Vue 3 + Vue Router + Vite + ECharts。
- `package.json` 完全一致（axios 依赖仅 financial-report / stock-alert 显式声明，stock-system 隐式依赖）。
- `vite.config.js` 三者均设 `minify: false`，stock-alert 和 stock-system 还显式配了 dev proxy `/api -> :8000`。

---

## 2. 静态资源 / 部署数据

### stock-alert/dist
- 总大小 **395 MB**，其中 `dist/data/price/*.csv` 占 **392 MB**（5529 个文件）。
- 资源目录是 `web/stock-alert/dist/data/`，从 `AUTO-STOCK/data/price/` + `result/score_price_history.csv` 同步而来。
- 同步机制：**手动复制**（DEVELOPMENT_STATUS.md 第65行："每次 vite build 后需要手动同步到 dist/ 目录"）。
- 没有 `.gitignore` 排除 dist/ 或 data/，但 git 实际未跟踪它们（`git ls-files` 仅含源码）。
- `dist/index.html` 内嵌 `/yujing/assets/...` 路径（base 正确）。
- `loader.js:8` 硬编码 `BASE_URL = '/yujing/data'`。

### stock-system/dist
- 2.9 MB（仅 assets，无 data）。
- `loader.js:266-276` `gotoYujing` 硬编码 `window.open('https://auto-claw.top/yujing/...')`（跨域硬编码）。
- vite dev server proxy 配置了 `/api` 和 `/data`，但部署到 nginx 之前开发环境才有意义（nginx 自己 reverse proxy）。

### financial-report/dist
- 2.8 MB，所有数据走 `/api/v1/financial/*`（后端）。
- 无静态数据文件。

---

## 3. 数据加载路径

### financial-report
- 全部走 **API**：`/api/v1/financial/score/{code}`、`/api/v1/financial/kline/{code}`、`/api/v1/stock/search`、`/api/v1/feedback`。
- 通过 `auto-claw.top.conf` 的 `location /api/` 反代到 127.0.0.1:8000。
- CORS：API 端 `allow_origins=["*"]`（api/main.py:49）。

### stock-alert
- 数据走 **静态文件**：`/yujing/data/score_price_history.csv` + `/yujing/data/price/{code}.csv`。
- nginx `auto-claw.top.conf:95-101` 用 `alias` 指向 `AUTO-STOCK/result/` 和 `AUTO-STOCK/data/price/`，**与 stock-alert/dist/ 同源**（但路径独立于 dist）。
- 评论过的"大盘K线不显示"问题根因：评分数据 `20260512+` vs 大盘指数 `20160104+`，日期不重叠（DEVELOPMENT_STATUS.md）。
- 搜索功能：从前端 `score_price_history.csv` 全量读取、按 code 唯一后筛选，**5500+ 条记录全量加载到浏览器**。

### stock-system
- 持仓/账户/信号走 **API**：`/api/v1/portfolio/*`、`/api/v1/signals/latest`。
- 静态价格数据走 `/data/score_price_history.csv`（用 `?mode=REAL/SIM` 区分账户）。
- nginx `stock-system.conf:71-81` 用 alias 暴露 `AUTO-STOCK/data/price/` 和 `result/`。
- 缓存策略 `cache.js`：内存 Map + localStorage 双层，T1 数据（评分/信号）TTL 24h，REALTIME（持仓/股价）按市场时段 30s/5min/1h。
- 缓存 key 用 `CACHE_VERSION = 'v1'` 区分，但**`/data/` 静态文件的 cache 机制与 API 缓存完全独立**——Portfolio.vue `refreshPrices` 直接 `fetch('/data/score_price_history.csv?_t='+Date.now())` 绕过 smartFetch 缓存（Portfolio.vue:604）。
- Vue Router `createWebHistory()` 配 stock-system nginx 的 `try_files $uri $uri/ /index.html;`（已配）。

---

## 4. 路由与视图

### financial-report
- `main.js:8-11` 路由：`/` → Home，`/detail/:code` → Detail（`props: true`）。
- Detail.vue 通过 `route.params.code` 获取股票代码（Detail.vue:677）。
- 错误处理：API 失败显示 `error` ref，无 404/兜底页（找不到股票停留在 loading=false + 错误提示）。
- 移动端：`index.html` 设了 `maximum-scale=1.0, user-scalable=no`，但样式上用 flex/grid，居中布局，移动端可用但未做针对性优化。

### stock-alert
- `main.js` **无路由**，单页应用，仅 StockKline 组件。
- URL 参数：`?code=`, `?cost=`, `?tp=`, `?sl=`, `?strategy=`（StockKline.vue:562-583）。
- 加载时 `searchKeyword.value = padded`，然后 `selectStock` 自动选中第一条。
- 错误处理：`error` ref 显示在底部，**未区分"股票代码无数据"vs"网络失败"**。

### stock-system
- `main.js:7-12` 路由：`/`、`/signals`、`/portfolio`、`/stats`、`/strategies`。
- 5 个页面，无懒加载（除用 `() => import(...)` 实际上做了代码分割）。
- App.vue 顶部导航在移动端收起文字仅留图标（App.vue:259 `display: none`）。
- 错误处理：每个页面 `loading` / `error` ref 简单处理，无 404 兜底路由（无 `path: '*'` 通配）。

---

## 5. 图表（ECharts）

### financial-report/Home.vue
- 翻转卡片（CSS 3D `rotateY` + `perspective: 1000px`），K线图固定 7 个位置（Home.vue:220 `min: 0, max: 6`）。
- 涨跌幅 tooltip 自定义：第 1 天用 prevClose，后续用前日收盘（正确）。
- ECharts tooltip `appendTo: document.body` + `z: 9999`（避免被卡片遮挡）。

### financial-report/Detail.vue
- 同样 3D 翻转 + 蜡烛图。
- **多线图**（Detail.vue:748-854）：总分/营收/归母/扣非 4 条线，分数 yAxis `-10 ~ 20` 硬编码（Detail.vue:801-802），**yAxis 范围不随数据动态调整**。
- `initChart` 用 `setTimeout(initChart, 500)` 重试机制（Detail.vue:695-704），隐式假设 500ms 后 DOM 渲染好。

### stock-alert/StockKline.vue
- K线 + 评分曲线 + 止盈止损线 + 触达点散点。
- 评分曲线 yAxis `min: 0, max: 100` 硬编码（StockKline.vue:351）。
- 价格 K线 yAxis `scale: true`（动态起点）。
- **多个 series 共享 xAxis，但 zIndex 不一致**：买入信号 `z: 10`，止盈止损 `z: 11`（正确）。
- **错误序列**：止盈触达 series 在 markLines 之前就 `series.push` 了（StockKline.vue:374-393），但实际止盈触达点数据填充是在 markLines 之后（StockKline.vue:421-445）——先 push 再计算！意味着第一次进入时 `tpPoints = []` 然后 `chart.setOption()` 才会拿到值，但因为 setOption 在 `nextTick` 内，所以会执行填充。**但是 markLines 内的 targetTp 引用了 `costPrice.value * (1 + takeProfitRate.value / 100)`（StockKline.vue:249）**——这行已被赋空（line 252: `markLines = []`），所以实际计算是下方 421 行的，但 targetTp 在那里又重新声明。
- 实际上 line 248-254 全部是"空跑"代码（tpPoints/slPoints/markLines 立即重置），但变量 targetTp 没有在那一段声明也没在 252 段删除。所以是死代码+作用域混乱。

### stock-system/Stats.vue
- 双 Y 轴（净值 + 总资产），正确使用 `yAxisIndex`。
- 净值用面积渐变，总资产用虚线。
- 移动端不报错但 stats-row 在窄屏变为 column（Stats.vue:502）。

---

## 6. 业务逻辑

### Portfolio.vue
- 买入校验：价格 > 0、股数 ≥ 100、整百（Portfolio.vue:391-407）。
- 卖出校验：股数 ≤ 持仓（Portfolio.vue:434）。
- 费用计算：`Math.max(amount * 0.00015, 5)`（最低 5 元）。
- **没有显示实时盈亏公式**：`sellFormEstimate` 显示"预计盈亏"，但实际扣了 commission + stamp_tax（卖出），买入只在 `buyFormTotal` 加了 commission。
- 持仓列只显示成本价/现价/盈亏金额/收益率（从 API 来，前端不算）。
- "修改总资产" 弹窗（capitalModal）确认后调 `/api/v1/portfolio/update-capital`——后端会**清空所有数据**（Portfolio.vue:337 "重置整个账户"），仅传 `initial_capital` 字段（Portfolio.vue:549-553）。

### Signals.vue
- 加载信号后按 `signal === 'BUY'` 过滤（Signals.vue:165）。
- 分页：每页 50 条，代码逻辑无 bug。
- `fromCache` 标志存在但**永远为 false**（Signals.vue:240 注释 "smartFetch 内部不暴露 fromCache"）——UI 永远显示非缓存。

### Stats.vue
- 加载 stats + trades(20) + navHistory（全量）。
- 最大回撤本地算：`(peak - n) / peak` 然后取 max。
- 没有月度聚合（CLAUDE.md 第 247 行提到"按月聚合"，但代码中**没有实现月度统计**——CLAUDE.md 描述与实际不符）。

### Dashboard.vue
- 进首页就 `clearAllCache()`（Dashboard.vue:155）——每次打开都强制重新拉 signals，避免显示陈旧数据。但**与 smartFetch 的设计意图相悖**（T1_DATA 设计就是 24h 内只拉 1 次）。
- `topScores` 是按 `avg7_score` 排序（Dashboard.vue:176），不是按当前评分。

---

## 7. 部署

### nginx 配置对比

| 项目 | 配置位置 | root | 关键设置 |
|------|---------|------|---------|
| financial-report | `/etc/nginx/conf.d/auto-claw.top.conf` | `web/financial-report/dist` | try_files SPA + `/api/` 反代 + `/yujing/` 反代 |
| stock-alert | 同上（location /yujing/） | `web/stock-alert/dist` | `/yujing/data/price/` alias → AUTO-STOCK/data/price/ |
| stock-system | `/etc/nginx/conf.d/stock-system.conf` | `web/stock-system/dist` | SPA + `/api/` + 多个 `/data/*` alias |

### 反代与 CORS
- `/api/` 都用 `proxy_pass http://127.0.0.1:8000`。
- nginx 没设 `proxy_set_header Host $host` for stock-system (line 47-50 of stock-system.conf) 但有——OK。
- CORS：API 端 `allow_origins=["*"]`，但浏览器同源策略下，nginx 反代后**不存在 CORS**——是 same-origin。但**CORS 头仍配置了（`Access-Control-Allow-Origin: https://stock.auto-claw.top`）**（stock-system.conf:59, 67, 74, 80）——多此一举但无害。

### 安全
- stock-system.conf 显式 deny 了对 `.db`、`.env`、`.git`、`.py`、`.log`、`.bak` 的访问（line 84-105）。
- **auto-claw.top.conf 没有类似 deny 规则**——理论上通过 `/yujing/data/price/000001.csv` 配合路径遍历可能访问 `data/price/../portfolio.db`？但 `alias` 配置对路径有 `try_files` 拦截，安全性尚可。

### dist 是否入 git
- `git ls-files web/stock-alert/dist/` → 空目录，但 dist 在文件系统里。
- `git ls-files web/stock-system/dist/` → 空。
- `git ls-files web/financial-report/dist/` → 空。
- **均未跟踪**（用 `git status` 看不到未跟踪 dist，可能在 .gitignore 里或者被隐式忽略——但项目根没看到 .gitignore）。

### 构建产物
- stock-alert `dist/index-*.js` 2.7 MB（**未 minify** + 含 ECharts + Vue 全部打进去），请求大小 2.7 MB gzip 前。
- financial-report / stock-system 也未 minify，资源体积大。

---

## 8. 重复代码与死代码

### 重复
- Home.vue 和 Detail.vue 的 K线图 `buildKlineOption`（Home.vue:212-304 / Detail.vue:469-561）几乎完全相同——80 行复制粘贴，仅 `grid` 参数不同。
- 3 个项目 `package.json` 几乎一样。

### 死代码 / 后门
- financial-report `Home.vue.bak`、`Detail.vue.bak`、`Home.vue.backup`、`Detail.vue.backup`（在 `src/views/` 目录）——**未在 git 跟踪**但仍在工作树。
- financial-report `src/assets/styles.css.backup`。
- financial-report `src/components/` 目录**空**。
- stock-alert `src/components/` 目录**空**。
- stock-system `src/components/` 目录**空**。
- stock-alert `app.py`（web/app.py）——**老的 Flask 旧版前端**还在，没删除。
- `web/src/`、`web/index.html`、`web/index_simple.html`——**整套旧前端未清理**。

### 死代码
- Detail.vue 顶部 `chartInitialized` 声明但未使用（Detail.vue:397）。
- StockKline.vue 变量 `flipTransitioning` (financial-report) 保留 setTimeout 中的死路径。
- Stock-alert `vite.config.js` 的 `server.proxy` 仅在 dev 模式有效，部署后无意义。

### Stock-alert bug 1：变量作用域错误
- StockKline.vue:244-254 声明的 `targetTp`/`targetSl` 在 line 421-445 重新使用，**且 line 247 立刻 `markLines = []`**，line 248-254 是死代码——保留仅因为后面 line 421 重新计算时也用了 `costPrice.value`。

### Stock-system 的 cron 调起
- CLAUDE.md 提到 `0 19 * * 1-5` 跑 evening_pipeline.sh，但 stock-system 实际数据（信号/持仓）依赖 API 实时计算。`scripts/evening_pipeline.sh` 没有直接写到 `stock-system/dist/` 的部署步骤——部署是手工的（无 npm build + cp 自动化）。

---

## 9. 时序与状态

### Portfolio.vue 自动刷新
- `setupAutoRefresh()` 用 setInterval 拉数据（Portfolio.vue:491-497），TTL 由市场状态决定。
- `watchMarketState()` 每分钟检查市场状态变化（Portfolio.vue:500-510），变化时**重新设置 timer + 强制拉一次**。
- 卸载时 clearInterval（Portfolio.vue:758-760）——OK。
- **问题**：Tab 切换时也调 `fetchData(false)`（Portfolio.vue:483-487），但 cache 已经会判断是否过期——多余。

### Dashboard.vue 缓存破坏
- `clearAllCache()` 在 onMounted 调用（Dashboard.vue:155）——每次进入都强制重拉。**这与 T1_DATA 设计冲突**。

### SmartFetch 的语义
- `getFromLocal` 在 `dataType === 'T1_DATA'` 时才查 localStorage（cache.js:147）。
- REALTIME 只在内存缓存，**不持久化**——意味着刷新页面就要重拉。
- TTL 24h 意味着如果用户在 19:00 拉了一次数据后，跨午夜前 18:59 进来又拉一次——不会真的重新拉。

---

## 10. 工具与代码质量

- `App.vue` 的脚本块为空（`script setup` 后立即 `<style>`）——可以。
- Home.vue / Detail.vue / StockKline.vue 大量 `console.log` 调试信息（`Home.vue:381-415`、Detail.vue 多处）——**调试日志未删除**。
- `axios` 在 financial-report 和 stock-alert 中使用，stock-system **完全不用 axios**（都用 fetch）——不一致。
- `stocks` 搜索：`searchStocks` 对 `score_price_history.csv` 全量 in-memory 处理（loader.js:124-141），5500 条记录每次切换股票都全量过一遍。

---

## 11. 移动端 / 响应式

- financial-report：固定 `max-width: 1200px` 居中，移动端通过 `meta viewport` + 居中布局。
- stock-alert：同 financial-report，max-width 1200px。
- stock-system：max-width 1400px + media query（App.vue:253-265），导航栏窄屏收起文字。
- 三者均**未做完整移动端适配**——表格在窄屏上会挤压。

---

## 12. P0 / P1 / P2 初步分类

### P0（功能错误）
- (待定) Stock-alert 的 `targetTp` 作用域混乱 + 死代码——但实际有第二次计算覆盖，所以功能没坏。
- (待定) Portfolio.vue `clearAllCache` 在 onMounted 调用——破坏缓存设计但不算功能错误。

### P1（性能 / 安全）
- stock-alert 每次 fetchCSV 拉全量 `score_price_history.csv`（约 5500 行）+ 单只股票 600+ 行——对单用户单次还好，但**N 个用户**就是大流量。
- stock-alert dist 392 MB，nginx 静态服务每次冷启动慢。
- vite `minify: false` 全部 3 个项目——2.7MB JS 文件 gzip 前下发。
- financial-report 没有 rate-limit / debounce on search——已实现 300ms debounce (Home.vue:356)。

### P2（可改进）
- 死代码（.bak/.backup 备份文件）。
- 调试日志未清除。
- 组件目录为空——历史遗留。
- CLAUDE.md 提到"按月聚合"——代码中无实现。
- axios vs fetch 风格不统一。
- K线 buildKlineOption 在 Home/Detail 重复 80 行。
