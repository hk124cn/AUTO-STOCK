# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目状态
**已完成** — 9因子评分系统 + 信号监控系统 + 持仓管理系统

## 常用命令

### 数据更新（日常流程）
```bash
# 从服务器同步代码
bash scripts/sync_repo.sh

# 更新市场数据（仅限交易日）
python scripts/update_data.py
```

### 运行评分
```bash
# 单股评分
echo -e "1\n600519" | python main.py

# 批量评分
echo -e "2\nstock_pool.csv\nresult" | python main.py
```

### 每日晚间流水线（评分→分析→报告）
```bash
bash scripts/evening_pipeline.sh           # 默认今天
bash scripts/evening_pipeline.sh 20260528  # 指定日期
```

### 重建行业数据（申万二级）
```bash
python -m src.datafactory.build_industry_data --full
```

### 运行测试
```bash
python -m pytest
```

## 架构

### 因子系统（已完成）
- **基类**: `src/core/base_factor.py` — 所有因子继承 `BaseFactor`，实现 `calculate()`
- **因子发现**: `src/core/factor_manager.py` 动态加载 `src/factors/` 下的所有因子类
- **分数聚合**: `src/core/scoring_engine.py` 使用加权平均汇总多因子得分

已实现的因子（共9个，总分100分）：
- `src/factors/attention_factor.py` — 关注度因子 (10分)
- `src/factors/daily_change_factor.py` — 单日涨跌幅因子 (10分)
- `src/factors/dividend_factor.py` — 股息率因子 (10分)
- `src/factors/financial_factor.py` — 财务因子 (20分)
- `src/factors/fiveday_factor.py` — 5日涨跌幅因子 (10分)
- `src/factors/hy_diff_factor.py` — 行业相对强弱因子 (10分，申万二级)
- `src/factors/news_factor.py` — 新闻因子 (10分)
- `src/factors/zj_flow_factor.py` — 资金流向因子 (10分)
- `src/factors/dp_diff_factor.py` — DP差异因子

添加新因子：在 `src/factors/` 下创建模块，定义继承 `BaseFactor` 的类，实现 `calculate()` 返回 `{"name": str, "score": float, "weight": float}`。

### 数据流水线（已完成）
```
AKShare API → data/daily_market/ → data/price/*.csv (个股)
```

- **数据下载**: `src/datafactory/market_down.py` — 获取日线市场数据
- **数据清洗**: `src/datafactory/price_builder.py` — 将日线CSV转换为个股价格文件
- **数据读取**: `src/datafactory/data_manager.py` — 提供 `get_price()`, `get_finance()`, `get_dividend()`, `get_attention()`, `get_news()`，本地优先缓存
- **公告日期**: `get_disclosure_dates()` — 获取财报披露日期（智能缓存）
- **公告后K线**: `get_kline_after_disclosure()` — 获取财报发布后N日股价数据
- **行业数据**: `build_industry_data.py` — 申万二级行业映射和涨跌幅（131个行业）

### 行业系统（申万二级）
- **131个二级行业**：如"白酒Ⅱ"、"股份制银行Ⅱ"、"汽车零部件"等，相比一级行业更精准
- **数据文件**: `data/industry/stock_industry_mapping.csv` (5199只股票)
- **涨跌幅数据**: `data/industry/change_xxx_20d.csv` (131个行业)

### Web 界面

```
web/
├── financial-report/    # → /  财报评分（Vue 3 + Vite + ECharts）
├── stock-alert/         # → /yujing/  个股评分预警图（Vue 3 + Vite + ECharts）
└── stock-system/        # → stock.auto-claw.top  股票操作系统（信号监控+持仓管理）
```

**股票操作系统** (`stock.auto-claw.top`):
- **信号监控**: v1(每日触发) / v2(首次突破) 两种策略，按财报分数/7日均分排序
- **持仓管理**: 模拟/实盘账户，买入/卖出记录，止盈止损
- **收益统计**: 收益曲线、月度统计、夏普比率
- **策略管理**: v1/v2 策略切换，参数配置

**财报评分** (`/`):
- **页面路由**:
  - `/` — 首页，搜索股票查询财报评分
  - `/detail/:code` — 详情页，分季度查看评分和股价走势
- **翻转卡片**: 点击按钮卡片3D翻转，显示财报发布后7日股价走势图

**个股预警** (`/yujing/`):
- 搜索股票（代码或名称），回车直接选中
- 价格K线图（ECharts candlestick，左Y轴，scale:true 动态起点）
- 评分曲线叠加（右Y轴，默认关闭）
- Tooltip：中文标签 + 涨跌幅（前日收盘价计算）
- 时间范围：1M / 3M / 6M / 1Y / All
- **数据自动更新**：Nginx 直接读取 `data/price/` 和 `result/score_price_history.csv`，无需 rebuild

### 每日报告系统
- **生成**: `scripts/daily_report.py` — 读取 batch_result，生成 HTML 报告
- **展示**: `/reports/` — 每日多因子评分网页
- **功能**: 特别关注股票高亮、收盘价+涨跌幅显示、行业分析
- **自动更新**: 由 `evening_pipeline.sh` 每日 19:00 后自动生成

### 每日晚间流水线
```bash
scripts/evening_pipeline.sh
```
串联执行：批量评分 → kline_analyzer → 每日报告，任一步失败会停在该步。
Cron: `0 19 * * 1-5`

### 回测系统
- **策略注册**: `src/backtest/strategies.py` — v1(每日触发) / v2(首次突破)
- **历史评分**: `src/backtest/scorer.py` — 5因子 point-in-time 评分
- **回测引擎**: `src/backtest/engine.py` — scored/live 两种模式
- **信号计算**: `scripts/calc_signals.py` — 每日信号生成（支持策略版本切换）

## 数据存储
- `data/price/*.csv` — 历史日线价格（日期、收盘价、成交额、开盘、最高、最低）
- `data/daily_market/*.csv` — 原始日线市场快照
- `data/finance/` — 财务数据缓存
- `data/dividend/` — 分红数据缓存
- `data/attention/` — 关注度数据
- `data/news/` — 新闻数据
- `data/fund/` — 5日资金流向数据
- `data/industry/` — 行业映射+涨跌幅（申万二级）
- `data/disclosure/*.csv` — 财报披露日期缓存（智能过期）
- `result/score_price_history.csv` — 评分-价格历史大表（含 finance_score 列）
- `result/daily_score/batch_result_*.csv` — 每日批量评分结果（唯一权威数据源）
- `result/signals/v1/` — v1 策略信号（每日触发）
- `result/signals/v2/` — v2 策略信号（首次突破）
- `data/portfolio.db` — 持仓管理数据库

## 关键文件
- `main.py` — 评分入口（单股/批量），输出到 `result/daily_score/`
- `src/core/factor_manager.py` — 因子动态加载入口
- `src/datafactory/data_manager.py` — 数据统一访问接口
- `src/datafactory/build_industry_data.py` — 行业数据构建（申万二级）
- `src/factors/financial_factor.py` — 财报评分因子（满分20）
- `src/factors/daily_change_factor.py` — 单日涨跌幅因子（满分10）
- `src/analyzer/kline_analyzer.py` — 评分-价格历史表生成器（含 finance_score）
- `src/backtest/strategies.py` — 策略注册表（v1/v2）
- `api/main.py` — FastAPI 后端服务
- `scripts/calc_signals.py` — 每日信号计算（支持 v1/v2 策略）
- `scripts/evening_pipeline.sh` — 每日晚间流水线
- `scripts/daily_report.py` — 每日报告生成
- `scripts/stock_analysis.py` — 个股深度分析报告
- `scripts/start_financial_score.sh` — 服务启动脚本
- `web/financial-report/src/views/Home.vue` — 财报评分首页
- `web/financial-report/src/views/Detail.vue` — 财报评分详情页
- `web/stock-alert/src/views/StockKline.vue` — 个股预警K线图
- `web/stock-alert/src/data/loader.js` — 预警数据加载
- `web/stock-system/src/views/Signals.vue` — 信号监控页面（含财报分数排序）

## 评分指标与权重
| 指标 | 权重 | 正增长满分 | 负增长封顶 |
|------|------|-----------|-----------|
| 扣非净利润 | 50% | 10分 (40%增长=满分) | -50分 |
| 归母净利润 | 25% | 5分 (40%增长=满分) | -25分 |
| 营业收入 | 25% | 5分 (40%增长=满分) | -25分 |

### 计算公式
**正增长**：基础分 = 满分 × (同比增长率 / 40)，不/10

**负增长**：基础分 = 封顶分 × (同比增长率 / 100) / 10

**趋势分**：
- 连续增长/下降：±7.5% × 满分
- V型/倒V反转：±5% × 满分
- 整体变化：±5% × 满分
- 趋势分范围：±10% × 满分

**最终评分** = 转换后基础分总和 + 趋势分总和

### 示例
茅台(600519) 2025Q4：扣非-30.83%、归母-30.34%、营收-19.35% → **-4.29分**
福耀玻璃(600660) 2026Q1：扣非-17.32%、归母-15.68%、营收+5.08% → **-1.88分**

## 依赖
- akshare >= 1.13.99
- pandas >= 2.0.0
- numpy >= 1.24.0
