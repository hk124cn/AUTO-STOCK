# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述
微信小程序版「财报评分」，功能与网页版 (web/financial-report) 对齐。原生微信小程序开发（非 uni-app/Taro）。

## 技术栈
- **框架**: 微信小程序原生 (WXML + WXSS + JS)
- **图表**: Canvas 手绘（K线蜡烛图、趋势折线图）
- **后端API**: `https://www.auto-claw.top/api/v1`（FastAPI，代码在 `api/main.py`）
- **CI/上传**: `miniprogram-ci`（见 package.json）
- **AppID**: `wxf1b550fac7e720d6`

## 页面结构
```
pages/
├── index/     → 首页：股票搜索 + 财报评分 + K线翻转卡片
├── detail/    → 详情页：季度切换 + 分项得分 + 财务数据 + 趋势图 + K线
├── reports/   → 多因子报告页：大盘概览 + TOP榜 + 因子冠军
└── webview/   → WebView（文件存在但未在 app.json 注册，暂未使用）
```

## API 端点
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/stock/search?q=&limit=` | GET | 搜索股票（代码/名称模糊匹配） |
| `/api/v1/financial/score/{code}` | GET | 3季度财报评分 + 趋势 + 洞察 |
| `/api/v1/financial/detail/{code}` | GET | 详情（含完整财务数据DataFrame） |
| `/api/v1/financial/kline/{code}&quarter=` | GET | 公告后7日K线数据 |
| `/api/v1/feedback` | POST | 提交建议反馈 |
| `/api/v1/reports/today` | GET | 今日多因子评分报告 |
| `/api/v1/reports/search?q=` | GET | 从报告中搜索股票 |

## 与网页版的差异（维护要点）

### 已对齐的功能
- 首页搜索 + 评分卡片 + 翻转K线
- 详情页季度切换 + 分项进度条 + 财务数据
- 反馈提交
- 多因子报告页

### 已补齐功能 (2026-05-31)
1. ~~**搜索高亮匹配**~~ — 用 `rich-text` + `highlightMatch()` 实现金色高亮
2. ~~**进度条点击浮动提示**~~ — 点击分项得分弹出基础分/趋势分拆分 tooltip
3. ~~**评分说明补全~~ — 补齐计算规则、趋势分计算、数据来源、注意事项4个section
4. ~~**反馈后继续按钮**~~ — 提交成功后显示"已提交，继续反馈"按钮
5. ~~**简要说明/趋势解读图标**~~ — 添加 💡📈 emoji + flex 布局

### 已修复BUG (2026-05-31)
1. ~~**K线Canvas白色背景**~~ — 已改为 `#1C1C1E` 深色背景，网格线改为 `#38383A`
2. ~~**趋势图Canvas白色背景**~~ — 同上
3. ~~**K线tooltip触控不灵敏**~~ — 缓存 canvas boundingClientRect，避免每次 touch 都查询 DOM

### 图表实现差异
- **网页版**: ECharts（平滑曲线、面积渐变、交互式tooltip、动画）
- **小程序版**: Canvas 手绘（折线+圆点、手动计算坐标、touch事件tooltip）
- 小程序无法直接用 ECharts，可考虑引入 `echarts-for-weixin` 组件

## 常用命令
```bash
# 本地预览（微信开发者工具中打开此目录）
# 上传代码（需要密钥 private.wxf1b550fac7e720d6.key）
node upload.js
```

## 数据流
```
用户输入代码 → /stock/search (搜索候选)
            → /financial/score/{code} (获取评分)
            → /financial/kline/{code} (获取K线)
            → /financial/detail/{code} (详情页)
```

## 样式规范
- 深色主题：背景 `#000000`，卡片 `linear-gradient(145deg, rgba(35,35,40,0.95), rgba(22,22,25,0.98))`
- 主色调：`#007AFF`（蓝）、`#FF3B30`（红/涨）、`#34C759`（绿/跌）
- 评分颜色：≥15 红色(excellent)、≥5 橙色(good)、<5 绿色(poor)
- 涨跌色：A股习惯 红涨(`#ef232a`)绿跌(`#14b143`)
