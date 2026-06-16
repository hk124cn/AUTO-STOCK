# 股票操作系统

实盘操作管理系统，用于信号监控、持仓管理和收益统计。

## 功能

- **首页仪表盘** - 概览今日信号、评分排名
- **信号监控** - 实时查看买入信号，支持搜索和排序
- **持仓管理** - 记录买卖交易，管理持仓状态
- **收益统计** - 收益曲线、月度统计、交易分析

## 技术栈

- Vue 3
- Vite
- ECharts
- Vue Router

## 开发

```bash
# 安装依赖
npm install

# 开发服务器
npm run dev

# 构建
npm run build
```

## 数据来源

- `/data/signals/signals_latest.csv` - 最新信号
- `/data/daily_score/batch_result_*.csv` - 每日评分
- `/data/price/{code}.csv` - 个股价格
- `/data/score_price_history.csv` - 评分历史

## 部署

1. 构建项目：`npm run build`
2. 复制 `dist/` 到服务器
3. 配置 Nginx（见 `nginx.conf`）
4. 配置域名 `stock.auto-claw.top`

## 访问地址

- 生产环境：https://stock.auto-claw.top/
- 开发环境：http://localhost:3002/
