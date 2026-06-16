# 草稿：Web 前端复查 (2026-06-15)

## 上次 P1 修复状态（8 项）

| # | 上次 P1 | 状态 | 证据 |
|---|---------|------|------|
| P1-1 | stock-alert dist 内置 392 MB CSV | **未修复** | `du -sh dist/data` = 393M |
| P1-2 | vite `minify: false` → 包 ≥ 2.7 MB | **未修复** | 三个 vite.config.js 第 16 行依然 `minify: false`；stock-system dist/assets/Stats-DKBAotRe.js = **2.5 MB** |
| P1-3 | Dashboard.vue onMounted 强制 clearAllCache | **未修复** | Dashboard.vue:164 `clearAllCache()` 依然在 onMounted 首行 |
| P1-4 | Portfolio.vue refreshPrices 绕过 smartFetch | **未修复** | Portfolio.vue:605 仍 `fetch('/data/score_price_history.csv?_t=' + Date.now())` + line 620 `vals = lines[i].split(',')`（无 RFC4180） |
| P1-5 | stock-alert 全量重拉 score_price_history.csv | **未修复** | loader.js:67 `Promise.all([loadScoreHistory(), loadPrice(code)])`；内存缓存但刷新页面丢 |
| P1-6 | StockKline.vue 死代码作用域混乱 | **已修复** | StockKline.vue 现 387 行（原 460+），`tpPoints/slPoints/markLines/targetTp/targetSl` 全部已删 |
| P1-7 | Home.vue 14 处 console.log | **未修复** | 仍 14 处 console.log（line 381/382/383/384/388/391/401/402/403/406/412/415/431/433） |
| P1-8 | 跨域硬编码 stock-system → stock-alert | **未修复** | loader.js:310 `window.open('https://auto-claw.top/yujing/?...')` 仍硬编码 |

**修复率：1/8 = 12.5%**

## 本轮新发现

### [P0] Dashboard.vue 进入即清缓存 + 同一 tick 内多源信号请求（放大 P1-3 影响）

- 位置：`web/stock-system/src/views/Dashboard.vue:163-189`
- 现象：`onMounted` 首行 `clearAllCache()` 之后，紧跟着**串行**调用 `loadStrategyVersions()` 和 `loadSignals(false, currentVersion.value)`。
- `loadSignals` 第 2 个参数 `version` 让缓存键变 `${CACHE_KEYS.SIGNALS}:${version}`，但 `clearAllCache()` 之后无缓存可命中 → 强制打 `/api/v1/signals/latest?version=v1` + `/api/v1/strategies/versions` 两个后端接口。
- 后果：每次 Dashboard 打开 = 2 次后端请求 + 旧 P1-3 同样问题。
- 建议：删除 line 164 的 `clearAllCache()`；让 smartFetch 自己的 24h TTL 起作用。

### [P0] Stats.js dist 2.5 MB，单一 chunk 加载阻塞首屏

- 位置：`web/stock-system/dist/assets/Stats-DKBAotRe.js` 2,505,261 bytes
- 现象：vite.config.js `minify: false` + Stats.vue `import * as echarts from 'echarts'` 拉整个 echarts 库。
- 后果：访问 /stats 单页加载 = 2.5 MB JS parse；移动端/弱网 3G 下首屏可见延迟。
- 证据：`Stats.vue:184 import * as echarts from 'echarts'` + `vite.config.js:16 minify: false`
- 建议：
  1. `minify: 'esbuild'`（Vite 默认），同样代码可压缩到约 800 KB。
  2. 进一步按需引入：`import { LineChart } from 'echarts/charts'` + `import { CanvasRenderer } from 'echarts/renderers'` + `import * as echarts from 'echarts/core'`（约 350 KB）。

### [P1] stock-system dist 被 git 跟踪，其他两个 dist 都已 gitignore

- 位置：`web/stock-system/dist/` (git ls-files 显示被跟踪)
- 现象：`.gitignore` 中有 `web/financial-report/dist/` 和 `web/stock-alert/dist/`，但 **没有** `web/stock-system/dist/`。
- 后果：dist 资产（2.9 MB 已 minified 前）每次 build 都会污染 git diff；当前就有 9 个 D（删除）+ 9 个 ??（新增）= 18 条 dist 变更。
- 建议：在 .gitignore 添加 `web/stock-system/dist/`；执行 `git rm -r --cached web/stock-system/dist/`。

### [P1] 新增 Strategies.vue 信号版本切换 + activateVersion 用 alert()

- 位置：`web/stock-system/src/views/Strategies.vue:253-257`
- 现象：`activateVersion` 用 `alert()` 提示切换成功；用户体验差且阻塞 UI 线程。
- 后果：用户每次切换都要点 alert 确认；alert 在某些浏览器/移动 WebView 中样式难看。
- 建议：换成站内 toast 组件或 inline 状态提示；与 Portfolio.vue:664 `alert('✅ 快照已保存...')` 同样问题。

### [P1] loadSignals 缓存键拼接 + `setStrategyVersion` 清所有缓存

- 位置：`web/stock-system/src/data/loader.js:99-117, 92-96`
- 现象：
  - line 99 缓存键 = `${CACHE_KEYS.SIGNALS}:${version}`，策略版本一变缓存键全变 → 老缓存会随版本数线性增长，24h 内不主动清可能堆积。
  - `setStrategyVersion` 调 `clearAllCache()` 清所有缓存，但用户切 v1→v2 实际只需要清 signals 和 scores 两个 key，账户/持仓/统计等 REALTIME 数据应保留。
- 后果：切换策略版本后 REALTIME 缓存也被清 → Dashboard 切到任意页面都会触发后端 QPS 上升。
- 建议：`setStrategyVersion` 改为 `invalidateCache('signals') + invalidateCache('scores')`，不要 `clearAllCache()`。

### [P1] api 后端 CORS allow_origins=["*"] + stock-system.conf nginx 又加 ACAO

- 位置：`api/main.py:50 allow_origins=["*"]` + `web/stock-system/nginx.conf:59, 67, 74, 80`
- 现象：双层 CORS 配置，行为取决于请求路径：API 走 nginx 反代时是 same-origin（不触发 CORS），静态资源直发更不会触发。
- 后果：增加响应体积 + 调试迷惑（开发者抓包会看到 ACAO 头以为是跨域问题）。
- 建议：删除 nginx.conf 4 处 ACAO；API 端 allow_origins 收紧到已知域名（`["https://stock.auto-claw.top", "https://auto-claw.top"]`）。

### [P1] newStrategies.vue 模板硬编码回测收益数字

- 位置：`web/stock-system/src/views/Strategies.vue:38-39`
- 现象：版本卡片里写死 `三年回测: 2024 +18% · 2025 +32% · 2026 +15%` 和 `年均 +21.6%`。
- 后果：实际回测数据更新后 UI 不会变；策略参数变了，UI 仍显示旧数字；新增加 v3 时忘了改。
- 建议：从 `/api/v1/backtest/top?n=10`（已经在 fetchBacktestTop 拉）取真实结果渲染。

### [P1] Portfolio.vue:620 `vals = lines[i].split(',')` 行业名带逗号错位

- 位置：`web/stock-system/src/views/Portfolio.vue:620`
- 现象：CSV 用 `split(',')`，但行业名（申万二级）如"白酒Ⅱ"不含逗号看起来 OK，**但如果有公司名带逗号**（罕见但合规 CSV 需要引号转义）会错位。
- loader.js 已经有 `parseCSV` (RFC4180) 在 line 17-49，但 Portfolio.vue 自己实现了一遍 CSV 解析，**没有引号转义**。
- 后果：当前行业名 / 公司名都是单 token，可能表面无 bug；但 score_price_history.csv 一旦加入带引号的字符串就错位。
- 建议：导出一份 `parseCSV` 或在 loader.js 新增 `loadScorePriceLatest()` 走 smartFetch。

### [P2] StockKline.vue 仍在每次切换股票全量拉 CSV

- 位置：`web/stock-alert/src/data/loader.js:13-33`
- 现象：in-memory cache `cache[path]` 跨页面刷新就丢；fetchCSV 没有 setTimeout 也没有 LRU 限制。
- 后果：浏览器开 10 分钟点 20 只股票 = 20 次全量 CSV 拉取。
- 建议：缓存到 `sessionStorage`（同会话持久）或 IndexedDB。

### [P2] financial-report Detail.vue setTimeout(initChart, 500) 轮询 2 次

- 位置：`web/financial-report/src/views/Detail.vue:681-704`
- 现象：line 681 `await nextTick(); setTimeout(initChart, 100)` + line 693-704 setTimeout 500ms 自递归。
- 后果：网络慢时图表最多延迟 1-1.5s；CPU 空转。
- 建议：删除 setTimeout 轮询，仅保留 line 681 的 nextTick+setTimeout(100)。

### [P2] 跨项目 Dashboard.vue 切到 Signals.vue 时重复调 loadStrategyVersions

- 位置：`Dashboard.vue:167-169` + `Signals.vue:276-278`
- 现象：两个页面 onMounted 都调 `loadStrategyVersions()`，都用 `forceRefresh=false` 走缓存。
- 后果：smartFetch 缓存命中时确实不会双发请求，但 `Dashboard → Signals` 切换时**两次都走缓存读 + 一次内存查找**；如果用户清缓存就会双发。
- 建议：把 `loadStrategyVersions` 提到全局 Pinia / provide 共享。

### [P2] stock-system 无 404 兜底路由 + financial-report 同

- 位置：`web/stock-system/src/main.js:10-15` + `web/financial-report/src/main.js:8-11`
- 现象：路由表无 `path: '/:pathMatch(.*)*'`。
- 后果：访问 `/foo` 仍渲染 Dashboard（vue-router 默认行为）。
- 建议：加 NotFound 组件 + 兜底路由。

### [P2] Strategies.vue 多个 fetch 端点没用 authedFetch（应该是 GET 不需要 auth，但仍需统一）

- 位置：`web/stock-system/src/views/Strategies.vue:286, 297, 311, 326`
- 现象：`fetchStrategies`、`fetchAccountBindings`、`fetchBacktestTop`、`bindStrategy` 内的 `/api/v1/portfolio/account` 走 `fetch()` 而非 `authedFetch()`。
- 后果：API 已经 `Depends(verify_token)`，这些 GET 不带 token 调会 401 → 静默失败 → 数据为空。
- 建议：与 `authedFetch` 统一；或确认这几个端点没加 auth 装饰器。

### [P2] Strategies.vue 切换版本弹 alert 阻塞 + 缓存清全表

- 位置：`Strategies.vue:253-257` + `loader.js:92-96`
- 现象：`activateVersion` → `setStrategyVersion` → `clearAllCache()`。清全部缓存过重。
- 后果：见 P1-5。
- 建议：仅清 signals + scores。

### [P2] financial-report 仍有 14 处 console.log

- 位置：`web/financial-report/src/views/Home.vue:381-438`
- 现象：14 处 console.log 全部未删。
- 建议：删 / `if (import.meta.env.DEV)` 包裹。

### [P2] 构建产物源代码分离：financial-report / stock-alert / stock-system 都内嵌 dist

- 现象：三个 dist 都在 git（stock-system 显式 tracking，financial-report/stock-alert 是 dev server 用）。nginx 部署时也指向 dist。
- 后果：dist 实际污染 git 仓库（stock-system 18 个 D/?? 条目）；构建产物没走 CI。
- 建议：统一 gitignore 三个 dist；加 CI build step。

### [P3] StockKline.vue 已无 dead code（P1-6 修复确认）

- 位置：`web/stock-alert/src/views/StockKline.vue` 全文 387 行
- 现象：上次 P1-6 的 `tpPoints/slPoints/markLines/targetTp/targetSl` 已全部删除，止盈止损线由 `costPrice` 透传 query 给 stock-system 处理（loader.js:301-310）。
- 评价：本次确认 P1-6 修复完整。

### [P3] Stats.vue yAxis formatter 仍是 toFixed(2)

- 位置：`web/stock-system/src/views/Stats.vue:264`
- 现象：净值曲线 yAxis `formatter: val => val.toFixed(2)`。
- 评价：上次 P3-2 仍存在（line 264），但与"toFixed(4)"对比的视觉差异小，可不修。

### [P3] 跨项目硬编码 localhost:8000

- 位置：`web/stock-alert/vite.config.js:31` + `web/stock-system/vite.config.js:30`
- 现象：dev server 代理到 `http://localhost:8000`，**硬编码**。
- 后果：dev 时 API 必须在 8000 端口；如果 API 端口变了，proxy 失效但无报错（fallback 404）。
- 建议：抽到 `process.env.API_TARGET` 或 `import.meta.env.VITE_API_TARGET`。

### [P3] docs/stock-system/ 新文档站

- 位置：`docs/stock-system/{README,FEATURES,API,TESTING,CHANGELOG,DEPLOYMENT,CODE_REVIEW}.md` 共 1846 行
- 现象：完整文档体系已建立，CHANGELOG 1.1.0 / 1.0.0 / 0.1.0 三个版本号。
- 评价：**正资产**。但 `docs/README.md` 没有反向链接到 `audit/` 目录。

## 关键文件

- `/home/admin/AUTO-STOCK/web/stock-system/src/views/Dashboard.vue`（line 164 clearAllCache）
- `/home/admin/AUTO-STOCK/web/stock-system/src/views/Strategies.vue`（line 253-257 新增信号版本切换）
- `/home/admin/AUTO-STOCK/web/stock-system/src/data/loader.js`（line 99-117 新增 version 维度）
- `/home/admin/AUTO-STOCK/web/stock-system/src/data/cache.js`（CACHE_VERSION v2）
- `/home/admin/AUTO-STOCK/web/stock-system/dist/assets/Stats-DKBAotRe.js`（2.5 MB 巨型）
- `/home/admin/AUTO-STOCK/web/financial-report/src/views/Home.vue`（14 console.log）
- `/home/admin/AUTO-STOCK/web/stock-alert/dist/data/`（393 MB 数据）
- `/home/admin/AUTO-STOCK/web/stock-alert/src/data/loader.js`（仍全量重拉）
- `/home/admin/AUTO-STOCK/web/stock-alert/src/views/StockKline.vue`（已修复死代码）
- `/home/admin/AUTO-STOCK/web/stock-system/nginx.conf`（CORS 多余 + dist tracking）
- `/home/admin/AUTO-STOCK/api/main.py:50`（CORS allow_origins=["*"]）
- `/home/admin/AUTO-STOCK/.gitignore`（缺 stock-system/dist）
- `/home/admin/AUTO-STOCK/docs/stock-system/`（新文档站，1846 行）
