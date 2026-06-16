# 子报告：Web 前端

> 范围：
> - `web/financial-report/`（auto-claw.top 根，财报评分）— `src/views/Home.vue`、`src/views/Detail.vue`、`vite.config.js`
> - `web/stock-alert/`（auto-claw.top/yujing/，个股预警）— `src/views/StockKline.vue`、`src/data/loader.js`、`dist/data/` 体积
> - `web/stock-system/`（stock.auto-claw.top/，股票操作系统，本轮重点）— `src/views/Dashboard.vue`、`Signals.vue`、`Portfolio.vue`、`Stats.vue`、`Strategies.vue`、新 `src/data/loader.js`（version 维度）、`src/data/cache.js`、新 `dist/assets/`
> - 部署侧：`deploy/stock-system.conf`、`web/stock-system/nginx.conf`、`.gitignore`、`docs/stock-system/`（新文档站）
> - 关联后端：`api/main.py`（CORS）、`/api/v1/signals/latest?version=`、`/api/v1/strategies/versions`
>
> 严重程度评级：P0=功能错误/P1=性能或安全/P2=可改进/P3=小问题
> 审查日期：2026-06-15

---

## 1. 概览

本轮 Web 前端新增核心改动集中在 `web/stock-system/`：v1/v2 策略版本切换（用户可在前端选择"什么算 BUY 信号"）、`Strategies.vue` 新增信号版本卡片、`Dashboard.vue` / `Signals.vue` 全部接入版本维度。新增 `docs/stock-system/` 文档站（1846 行 7 份 .md）。新增 `deploy/stock-system.conf` 部署配置（替代或并存 `web/stock-system/nginx.conf`）。

**主要问题**：

1. **上次 8 项 P1 仅修复 1 项**：stock-alert 死代码 (P1-6) 已清；其余 7 项（dist 392 MB、未 minify、Dashboard clearAllCache、Portfolio refreshPrices 绕过缓存、stock-alert 全量 CSV 重拉、Home.vue console.log、跨域硬编码）原样存在。
2. **新 Stats.js 2.5 MB**：单文件因 `minify: false` + `import * as echarts` 巨大，比上次 2.5 MB 持平——是 stock-system 整个 dist 的 86%。
3. **stock-system/dist 被 git 跟踪**而另两个 dist 都 gitignored——是新增的不一致。
4. **新 activateVersion 过度清缓存**：`setStrategyVersion` 调 `clearAllCache()`，但实际只该清 signals + scores 两个 key。

总体评分维持 **3/5**——新功能（策略版本）质量好，但历史 P1 几乎全未清理 + 新增部署/git 治理不一致。

---

## 2. 关键发现（按严重程度降序）

### [P0] Stats.js dist 2.5 MB 单文件阻塞首屏

- 位置：`web/stock-system/dist/assets/Stats-DKBAotRe.js` = 2,505,261 bytes
- 现象：vite.config.js `minify: false`（line 16）+ `Stats.vue:184 import * as echarts from 'echarts'` 拉整个 echarts 库。
- 后果：访问 `/stats` 路由 = 单 chunk 2.5 MB JS parse；移动端/弱网首屏明显延迟；其它路由（Dashboard/Signals/Portfolio/Strategies）通过懒加载也都被 lazy import 链拉入（vue-router dynamic import + 共享 chunk）。
- 证据：
  - `web/stock-system/vite.config.js:16` `minify: false`
  - `Stats.vue:184` `import * as echarts from 'echarts'`
- 建议：
  1. `minify: 'esbuild'`（Vite 默认），约 800 KB。
  2. echarts 按需引入（line 184 改为 tree-shakeable core 入口）：
     ```js
     import * as echarts from 'echarts/core'
     import { LineChart } from 'echarts/charts'
     import { GridComponent, TooltipComponent, ... } from 'echarts/components'
     import { CanvasRenderer } from 'echarts/renderers'
     echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer, ...])
     ```
     约 350 KB（gzip 前 100 KB）。

### [P0] Dashboard.vue onMounted 强制 clearAllCache（仍未修复 + 放大）

- 位置：`web/stock-system/src/views/Dashboard.vue:163-189`
- 现象：进入首页首行 `clearAllCache()` 之后串行调 `loadStrategyVersions()` 和 `loadSignals(false, currentVersion.value)`。
- 后果：上次 P1-3 已记录但未修。**新一轮**新引入 `loadSignals` 缓存键加 version 维度（loader.js:99-117）后，每次 `clearAllCache` → `loadSignals(v1)` + `loadSignals(v2)` 都需要重新打 `/api/v1/signals/latest?version=v1` 与 `/api/v1/strategies/versions`。一个 Dashboard 加载 = 2 次后端请求。
- 证据：`Dashboard.vue:164` `clearAllCache()` + `loader.js:99-117` version-aware smartFetch
- 建议：删除 line 164 的 `clearAllCache()`，让 smartFetch 自己的 24h TTL 起作用。如果用户需要强制刷新，UI 显式提供"刷新"按钮。

### [P0] setStrategyVersion 过度清所有缓存

- 位置：`web/stock-system/src/data/loader.js:92-96`
- 现象：切换策略版本时调 `clearAllCache()`，但实际只有 signals 和 scores 两个 key 与 version 维度相关（账户/持仓/统计/交易/净值都是 REALTIME 且与版本无关）。
- 后果：用户在 Strategies 页面点"切换到 v2" → 清空账户缓存 → 进入 Dashboard 重新打 `/api/v1/portfolio/account?mode=SIM|REAL` → QPS 上升 + 用户短暂看到空账户。
- 证据：`loader.js:92-96` `setStrategyVersion` → `clearAllCache()`
- 建议：改为精确失效：
  ```js
  invalidateCache('signals')
  invalidateCache('scores')
  ```
  与 `buyStock`/`sellStock` 的 `invalidateCache('positions:')` 模式一致。

### [P1] stock-alert dist 内置 393 MB CSV（仍未修复）

- 位置：`/home/admin/AUTO-STOCK/web/stock-alert/dist/data/` = 393 MB
- 现象：每次 build 手动复制 5529 个 CSV 到 dist。
- 后果：搜索任何股票都先 fetch 全量 `score_price_history.csv`（约 500 KB），N 用户并发流量大；git 同步慢。
- 建议：参考 stock-system 已用 nginx alias（`web/stock-system/nginx.conf:67-70` 共享 `AUTO-STOCK/data/price/`），stock-alert 也用 alias 读，**dist 内不放 data/**。

### [P1] vite `minify: false` 让 3 个项目首屏仍 ≥ 2.7 MB

- 位置：
  - `web/financial-report/vite.config.js:16`
  - `web/stock-alert/vite.config.js:16`
  - `web/stock-system/vite.config.js:16`
- 现象：financial-report dist 2.8 MB、stock-alert dist 2.6 MB、stock-system dist 2.9 MB；gzip 前均 > 2.5 MB。
- 后果：移动端首屏白屏；CSP `'unsafe-inline'`（nginx.conf:43）也是 minify 关闭后的回退。
- 建议：开 `minify: 'esbuild'`（Vite 默认），构建时间 1-2s 增加，换 60%+ 体积下降。

### [P1] Portfolio.vue refreshPrices 仍绕过 smartFetch

- 位置：`web/stock-system/src/views/Portfolio.vue:601-655`
- 现象：`refreshPrices` 内部仍 `fetch('/data/score_price_history.csv?_t=' + Date.now())` + `lines[i].split(',')`（无引号转义）。
- 后果：与 cache.js 的"统一缓存管理"理念冲突；500 KB 量级 + 无 TTL；CSV 解析无 RFC4180 兼容。
- 建议：要么新增 `loadScorePriceLatest()` 走 smartFetch + 用 `loader.js:17-49` 的 parseCSV；要么后端加 `/api/v1/portfolio/price-latest` 端点。

### [P1] stock-alert loader.js 全量重拉 score_price_history（仍未修复）

- 位置：`web/stock-alert/src/data/loader.js:13-33, 47-49, 63-87, 90-108`
- 现象：`getStockData` + `searchStocks` 每次都调 `loadScoreHistory()`；in-memory cache `cache[path]` 跨页面刷新就丢。
- 后果：换一只股票 = fetch 大文件 + 解析 + 过滤 5500 行；切时间范围不重拉但切股票就全量重读。
- 建议：缓存到 sessionStorage（同会话持久）或首次加载后写入内存 + sessionStorage 双层。

### [P1] Home.vue 仍 14 处 console.log（仍未修复）

- 位置：`web/financial-report/src/views/Home.vue:381, 382, 383, 384, 388, 391, 401, 402, 403, 406, 412, 415, 431, 433` + 2 处 console.error = 共 16 处（其中 14 是 console.log）
- 现象：开发期调试用的 `console.log` 没清理。
- 后果：用户控制台可见股票代码、API URL、API 返回全文。
- 建议：删除或 `if (import.meta.env.DEV) console.log(...)`。

### [P1] 跨域硬编码 stock-system → stock-alert（仍未修复）

- 位置：`web/stock-system/src/data/loader.js:310`
- 现象：`window.open('https://auto-claw.top/yujing/?${params.toString()}', '_blank')` 仍硬编码域名。
- 建议：抽到 `import.meta.env.VITE_YUJING_URL` 缺省生产 URL。

### [P1] stock-system/dist 被 git 跟踪（不一致）

- 位置：`web/stock-system/dist/`（git ls-files 显示被跟踪）
- 现象：`.gitignore` 排除 `web/financial-report/dist/` 和 `web/stock-alert/dist/`，**但没有** `web/stock-system/dist/`。
- 后果：当前 git status 有 9 个 D（删除旧 chunk）+ 9 个 ??（新 chunk）= 18 条 dist 污染 diff；其他两个项目已正确 gitignore。
- 建议：
  ```
  # .gitignore
  web/stock-system/dist/
  ```
  + `git rm -r --cached web/stock-system/dist/`。

### [P1] Strategies.vue 信号版本回测数字硬编码

- 位置：`web/stock-system/src/views/Strategies.vue:37-40`
- 现象：版本卡片写死 `三年回测: 2024 +18% · 2025 +32% · 2026 +15%` 和 `年均 +21.6%`。
- 后果：实际回测更新后 UI 不变；新增 v3 时忘了改。
- 建议：从 `fetchBacktestTop` 的结果按 version.id 过滤取对应行。

### [P1] 双层 CORS 配置（nginx + API）

- 位置：
  - `web/stock-system/nginx.conf:59, 67, 74, 80` `add_header Access-Control-Allow-Origin "https://stock.auto-claw.top"`
  - `api/main.py:50` `allow_origins=["*"]`
- 现象：API 走 nginx 反代是 same-origin（不触发 CORS），静态资源更不会触发。两层配置同时存在，行为难预期。
- 建议：删除 nginx 4 处 ACAO；API allow_origins 收紧到 `["https://stock.auto-claw.top", "https://auto-claw.top", "https://www.auto-claw.top"]`。

### [P1] activateVersion 用 alert 阻塞 UI

- 位置：`web/stock-system/src/views/Strategies.vue:253-257`
- 现象：版本切换成功提示用 `alert('✅ 已切换到 v1 信号版本')`。
- 后果：阻塞 UI 线程；移动 WebView 样式不一致。
- 建议：与项目内 `authModal` 模式一致的 toast 组件；或在版本卡片内联切换状态。

### [P2] 跨项目重复调 loadStrategyVersions

- 位置：`Dashboard.vue:167-169` + `Signals.vue:276-278`
- 现象：两个页面 onMounted 都调 `loadStrategyVersions()`，smartFetch 缓存命中时无重复请求，但清缓存后会双发。
- 建议：把 versions 提升为全局 Pinia store 或 provide/inject 共享。

### [P2] Strategies.vue 部分 fetch 未用 authedFetch

- 位置：`web/stock-system/src/views/Strategies.vue:286, 297, 311, 326`
- 现象：`fetchStrategies` / `fetchAccountBindings` / `fetchBacktestTop` / `bindStrategy` 内 `/api/v1/portfolio/account` 用 `fetch()` 而非 `authedFetch()`。
- 后果：如果这些 GET 端点加了 `Depends(verify_token)` 装饰器会 401 静默失败。需核实 API 端点是否需要 token。
- 建议：统一为 `authedFetch`（GET 也走统一 token 注入），与 `buyStock`/`sellStock` 一致。

### [P2] Portfolio.vue CSV 解析无引号转义（带逗号字段会错位）

- 位置：`web/stock-system/src/views/Portfolio.vue:620` `const vals = lines[i].split(',')`
- 现象：CSV 行业名"白酒Ⅱ" / 公司名"贵州茅台,股份有限公司"（罕见但合规 CSV）会错位。
- 建议：复用 `loader.js:17-49` 的 `parseCSVLine`。

### [P2] financial-report Detail.vue setTimeout(initChart, 500) 轮询 2 次

- 位置：`web/financial-report/src/views/Detail.vue:693-704`
- 现象：line 681 `await nextTick(); setTimeout(initChart, 100)` 之后，line 693-704 `setTimeout(initChart, 500)` 自递归（最多 2 次 ≈ 1 秒）。
- 建议：删除 setTimeout 轮询，仅保留 line 681 的 nextTick+setTimeout(100)。

### [P2] 无 404 兜底路由（stock-system + financial-report）

- 位置：`web/stock-system/src/main.js:10-15` + `web/financial-report/src/main.js:8-11`
- 建议：增加 `path: '/:pathMatch(.*)*'` 兜底 + NotFound 组件。

### [P2] buildKlineOption 在 Home.vue 和 Detail.vue 复制 80 行（仍未抽取）

- 位置：`web/financial-report/src/views/Home.vue:212` + `Detail.vue:469`
- 现象：除了 grid 参数，几乎逐字相同（Home.vue 677 行，Detail.vue 1451 行）。
- 建议：抽到 `src/lib/klineOption.js`。

### [P2] axios / fetch 风格不统一

- 位置：financial-report 用 axios（Home.vue:139 / Detail.vue:376），stock-alert 与 stock-system 完全不用 axios。
- 建议：统一为 fetch。

### [P2] Strategies.vue 3 处 alert（activateVersion / bindStrategy / deleteStrategyConfirm / Portfolio snapshot）

- 位置：Strategies.vue:256, 335, 405 + Portfolio.vue:664
- 建议：站内 toast。

### [P2] Stats.vue yAxis formatter 仍是 toFixed(2)

- 位置：`web/stock-system/src/views/Stats.vue:264`
- 现象：净值曲线 yAxis 仍 `val => val.toFixed(2)`，单位净值接近 1 时显示不出微小波动。
- 建议：`toFixed(4)`。

### [P3] dev proxy 硬编码 localhost:8000

- 位置：`web/stock-alert/vite.config.js:31` + `web/stock-system/vite.config.js:30`
- 现象：dev server 代理 `target: 'http://localhost:8000'`，硬编码。
- 建议：抽到 `process.env.API_TARGET` 或 `import.meta.env.VITE_API_TARGET`。

### [P3] stock-alert 搜索无 debounce

- 位置：`web/stock-alert/src/views/StockKline.vue:9, 102-111`
- 现象：onSearch 直接调 `searchStocks` 全量过 5500 行；用户每输入一个字都 fetch+parse+filter。
- 建议：300ms debounce（参考 Home.vue:356）。

### [P3] docs/ 反向链接缺失

- 位置：`/home/admin/AUTO-STOCK/docs/README.md`
- 现象：新文档站 README 没链接到 `audit/` 子报告。
- 建议：补交叉引用。

### [P3] Signals.vue sortField 重置逻辑分散

- 位置：`web/stock-system/src/views/Signals.vue:178`
- 现象：`sortField` 默认值依赖 `currentVersion.value` 但用户切版本（激活后调 setStrategyVersion 会清缓存）后 sortField 不会自动跟随。
- 建议：监听 currentVersion 变化重置 sortField。

---

## 3. 改进建议（非问题，但有更好做法）

1. **stock-system dist 引入 manualChunks**：vite 配置 `build.rollupOptions.output.manualChunks` 把 echarts 单独切到 vendor chunk，长期缓存。
2. **类型化**：3 个项目都 `<script setup>` 零 TypeScript；Stats.vue 这种 500 行大文件加 `<script setup lang="ts">` 可以减少 score / null 等低级错误。
3. **统一部署配置**：当前 `deploy/stock-system.conf` 与 `web/stock-system/nginx.conf` 内容接近（前者少了 CORS）；建议单一来源 + 占位符。
4. **CHANGELOG 与 git commit 联动**：`docs/stock-system/CHANGELOG.md` v1.1.0 写于 2026-06-16，但对应 commit 8b938f2 是 docs 类；新 Strategies.vue + loader.js 改动是工作树未提交。建议 commit 前更新 CHANGELOG。
5. **错误边界**：Strategies.vue 4 个 fetch 端点用 `try/catch` 包裹 + console.error 但 UI 不反馈错误，用户看到空表不知道为什么。可加 `<div v-if="loadError">...</div>`。
6. **数据归一**：把 stock-alert 的 `score_price_history.csv` 切到按 code 拆分的 JSON，前端按 code 拉单文件（参考 stock-system.conf:67-70 已有 alias 共享 data/price/ 的模式）。

---

## 4. 需要核实的不确定项

1. **`/api/v1/strategies/versions` 端点是否真存在**：loader.js:124 fetch 该端点，api/main.py:1166 确实定义了；但要确认返回结构（`{versions: [...]}`）与前端 `verResp.versions || []` 一致。
2. **`/api/v1/signals/latest?version=v2` 后端实现是否分版本返回**：v1/v2 应该是不同 JSON 文件；需确认后端按 query string 区分。
3. **Portfolio.vue refreshPrices CSV 的"最新日期"逻辑**：line 629 `[...dateSet].sort().pop()`——按字典序排序 "20260615" > "20260531" 是对的，但要确认 date 列原始格式是 YYYYMMDD 字符串。
4. **`docs/stock-system/CODE_REVIEW.md` (587 行) 是否被实际使用**：本轮没读全文，但作为 audit 文档应能引用。
5. **stock-system dist 被 git 跟踪是历史遗留还是有意为之**：stock-system 是最新项目，部署脚本可能直接 `git pull` + 用 dist；如果 gitignore 了就需要 CI build step。
6. **Stats.js 2.5 MB 是否有 CDN 或 service worker 缓存**：nginx.conf 静态资源 `expires 7d; Cache-Control "public, immutable"`（line 43-45）已正确，重复访问成本低，但**首次访问** 2.5 MB 仍是问题。

---

## 5. 评分（1-5，5 = 优）

| 维度 | 分数 | 评价 |
|------|------|------|
| 正确性 | 4 | 新策略版本切换功能完整；老 P1-3 / P1-4 等未修但不直接破坏功能 |
| 可维护性 | 2 | 8 个老 P1 仅修 1 个；activateVersion 过度清缓存；axios/fetch 混用；80 行 buildKlineOption 复制 |
| 性能 | 2 | Stats.js 2.5 MB 阻塞；stock-alert 393 MB dist；minify: false 三项目都未开；score_price_history.csv 全量重拉未修 |
| 文档 | 4 | 新 docs/stock-system/ 1846 行；CHANGELOG 三版本号；但 docs/README.md 缺交叉引用 |
| 部署 | 3 | deploy/stock-system.conf 新增（少 CORS）；双层 nginx.conf + deploy 共存；gitignore 不一致；dist 跟踪混乱 |
| **总评** | **3 / 5** | 新功能质量高（v1/v2 切换、finance_score 列），但历史 P1 几乎全未清理 + 新增 stock-system/dist git 治理不一致 |

---

## 6. P0/P1/P2 统计

- **P0**（功能错误 / 严重性能 / 设计缺陷）：**3**（P0-1 Stats.js 2.5 MB 阻塞首屏、P0-2 Dashboard clearAllCache 未修 + 放大、P0-3 setStrategyVersion 过度清所有缓存）
- **P1**（性能 / 安全 / 一致性）：**9**
  - P1-1 stock-alert dist 393 MB（仍未修）
  - P1-2 vite minify: false 三项目都未开（仍未修）
  - P1-3 Portfolio refreshPrices 绕过 smartFetch（仍未修）
  - P1-4 stock-alert 全量 CSV 重拉（仍未修）
  - P1-5 Home.vue 14 console.log（仍未修）
  - P1-6 跨域硬编码（仍未修）
  - P1-7 stock-system/dist 被 git 跟踪（新增）
  - P1-8 Strategies.vue 回测数字硬编码（新增）
  - P1-9 双层 CORS 配置（仍未修）
  - P1-10 activateVersion 用 alert 阻塞（新增）
- **P2**（可改进）：**9**
- **P3**（小问题）：**4**

### Top-3 严重问题

1. **P0-1 Stats.js dist 2.5 MB 单文件阻塞首屏**（连带 P1-2 minify: false）：上次 2.5 MB，本次持平。`minify: 'esbuild'` + echarts 按需引入可降到 350 KB（gzip 前），是性价比最高的一项。
2. **P0-2 Dashboard.vue 主动 clearAllCache**（连带 P0-3 setStrategyVersion 过度清缓存）：T1_DATA "日加载一次"语义被前后端多处破坏；本次新增的 version 维度让 `loadSignals(v1) + loadSignals(v2)` 双发，更需要修。
3. **P1-1 stock-alert dist 内置 393 MB CSV**（连带 P1-4 全量重拉）：半年未修，每次构建都手动复制 5529 个文件 + nginx 直服务 5529 个静态文件。stock-system 已经有 alias 共享 data/price/ 的成功模式，stock-alert 抄一份即可。

### 上次 8 项 P1 修复状态

- **P1-1** stock-alert dist 392 MB：❌ 未修（393 MB）
- **P1-2** vite minify: false：❌ 未修（minify: false 仍在 vite.config.js:16）
- **P1-3** Dashboard clearAllCache：❌ 未修（Dashboard.vue:164）
- **P1-4** Portfolio refreshPrices 绕过缓存：❌ 未修（Portfolio.vue:605）
- **P1-5** stock-alert 全量 CSV：❌ 未修（loader.js:13-33）
- **P1-6** StockKline.vue 死代码：✅ 已修（387 行，无 tpPoints/slPoints/markLines 残留）
- **P1-7** Home.vue 14 console.log：❌ 未修（仍 14 处）
- **P1-8** 跨域硬编码：❌ 未修（loader.js:310）

**修复率：1/8 = 12.5%**——半年内未对 7 项老 P1 做任何修复。

### 本轮新增关键交付

- v1/v2 策略版本切换（用户级，`localStorage` 持久化）
- `Strategies.vue` 新增信号版本卡片 + 三年回测数字展示
- `loader.js` `loadSignals(version)` + `loadStrategyVersions()` 接入 smartFetch
- `cache.js` CACHE_VERSION v2 让旧缓存失效（合理）
- `deploy/stock-system.conf` 新增（少 CORS，更精炼）
- `docs/stock-system/` 文档站 1846 行（README / FEATURES / API / TESTING / CHANGELOG / DEPLOYMENT / CODE_REVIEW）
