# /yujing/ 个股评分预警图 - 开发记录

## 状态：开发中，未完成

---

## 已完成 ✅

### 1. 项目搭建
- 路径：`/home/admin/AUTO-STOCK/web/stock-alert/`
- Vue 3 + Vite + ECharts
- 静态部署在 `/home/admin/AUTO-STOCK/web/stock-alert/dist/`
- 访问地址：`https://auto-claw.top/yujing/`

### 2. 搜索框前0被删问题 ✅
- **根因**：`loader.js` 的 `normalizeCode()` 去掉前导零用于比较，但搜索结果也用了处理后的值
- **修复**：保留原始 `code` 用于显示，`codeNum`（处理后）用于比较
- **文件**：`src/data/loader.js`
- **验证**：搜索"600660"显示"600660 - 福耀玻璃" ✅

---

## 待处理问题

### 2. Y轴起点从0开始
- **问题**：K线图Y轴从0开始，导致股价波动看起来很平
- **期望**：动态起点，接近最低价
- **修改**：已加 `scale: true` 到 yAxis 配置
- **状态**：修改已部署，但无法在 headless 浏览器中验证 scale:true 是否生效
- **验证方法**：需要在有显卡/正常浏览器的环境中手动打开页面看Y轴刻度范围

### 3. 大盘K线不显示
- **问题**：开启大盘K线 toggle 后，图表无内容
- **根因**：评分历史数据从 2026-05-12 开始，大盘指数数据从 2016-01-04 开始，日期不重叠
- **数据文件**：
  - 评分历史：`/home/admin/AUTO-STOCK/web/stock-alert/dist/data/score_price_history.csv`（20260512起）
  - 大盘指数：`/home/admin/AUTO-STOCK/web/stock-alert/dist/data/price/000300.csv`（20160104起）
- **修复方案**：大盘K线需要使用和价格K线相同的日期范围过滤（而不是评分日期范围）

### 4. checkbox选中/未选中样式无区分
- **问题**：价格K线☑选中和大盘K线☐未选，视觉上几乎一样
- **根因**：两个按钮背景都是深色 `#2a2a4a`，只有轻微差异（125 vs 110亮度）
- **期望**：选中状态为金黄色 `#ffd700`，未选中为灰色
- **修复**：CSS `button.active` 已定义金黄色背景，可能是 Vue class 绑定问题
- **文件**：`src/views/StockKline.vue`

### 5. 坐标轴太暗看不清
- **问题**：Y轴和X轴刻度文字在深色背景上对比度不足
- **修改**：已将刻度颜色从 `#444` 改为 `#999`，坐标轴线从 `#444` 改为 `#666`
- **文件**：`src/views/StockKline.vue`
- **状态**：修改已部署，需手动验证

---

## 技术记录

### 验证工具
- Playwright headless 测试脚本：`/tmp/test_verify.py` 系列
- 截图输出：`/tmp/yujing_vf.png` 等
- **限制**：headless 模式下无法访问 `echarts.getInstanceByDom()`（沙箱限制）

### 数据文件
- 评分历史：`/home/admin/AUTO-STOCK/web/stock-alert/public/data/score_price_history.csv`
- 价格数据：`/home/admin/AUTO-STOCK/web/stock-alert/public/data/price/{code}.csv`
- 每次 `vite build` 后需要手动同步到 `dist/` 目录

### 内存问题
- 服务器 1.8GB，build 时容易 OOM
- 停止 gunicorn 和 monitor 脚本后有 ~500MB 可用，build 成功
- 当前状态：gunicorn API 已停，monitor 脚本已从 crontab 移除

---

## 下次开发建议

1. **重启 gunicorn API**：执行 `bash /home/admin/AUTO-STOCK/scripts/start_financial_score.sh`
2. **恢复 monitor 脚本**：添加到 crontab
3. **验证 Y轴起点**：在有显卡的环境中打开页面，看Y轴刻度是否从 ~60 开始而非 0
4. **修复大盘K线**：将 `loadData()` 中的 `marketData` 改为按价格日期过滤，而非评分日期
5. **修复 checkbox 样式**：检查 `v-bind:class` 绑定是否正确，确认 CSS 优先级