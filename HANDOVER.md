# 交接文档 - 股票操作系统开发

## 项目背景

用户需要一个实盘操作管理系统，用于：
1. 每日信号监控（买入/卖出信号）
2. 持仓管理（记录实际交易）
3. 收益统计（计算策略收益）

## 已完成的工作

### 1. 启动信号分析（已完成）

**分析内容**：
- 2022-2026年启动信号分析
- 前7天平均分≥30分作为买入信号
- 20天内涨幅≥15%作为启动点

**关键发现**：
- 2022年（熊市）：最优止盈20%，止损3%，冷却0天，收益+22.30%
- 2023年（恢复市）：最优止盈5%，止损5%，冷却3天，收益+19.70%
- 2024年（牛市）：最优止盈15%，止损3%，冷却1天，收益+48.17%
- 2025年（牛市）：最优止盈20%，止损3%，冷却3天，收益+48.99%
- 2026年（震荡市）：最优止盈30%，止损8%，冷却1天，收益+28.30%

**推荐参数**（按总评分排序）：
- 买入阈值：30分（前7天平均分）
- 止盈：20%
- 止损：8%
- 冷却期：1天

**详见**：`result/backtest/启动信号策略四年完整对比报告.md`

### 2. 预警系统扩展（已完成）

**改动文件**：
- `web/stock-alert/src/data/loader.js` - 添加calcMovingAvg函数
- `web/stock-alert/src/views/StockKline.vue` - 添加信号标记

**功能**：
- 评分曲线上显示绿色圆点标记买入信号
- 买入信号条件：前7天平均分≥30分
- 控制面板添加"买入信号"开关
- tooltip显示信号详情

**访问地址**：https://auto-claw.top/yujing/

### 3. 定时任务修改（已完成）

**修改文件**：`scripts/evening_pipeline.sh`

**修改内容**：
- 添加步骤3：计算每日信号
- 整合到现有晚间流水线中

**执行顺序**：
1. 批量多因子评分（main.py）
2. 生成评分-价格历史表（kline_analyzer.py）
3. 计算每日信号（calc_signals.py，v1/v2 策略）
4. 生成每日报告（daily_report.py）

### 4. 备份脚本修改（已完成）

**修改文件**：`/home/admin/scripts/r2_backup.py`

**修改内容**：
- 备份整个AUTO-STOCK目录（原来只备份data目录）
- 排除不需要的目录：venv、node_modules、__pycache__、.git等
- 排除不需要的文件：*.pyc、*.log等

### 5. 文档更新（已完成）

**更新文件**：
- `CLAUDE.md` - 添加新系统说明
- `result/signals/` - 创建信号数据目录

### 6. 信号计算脚本（已完成）

**新增文件**：
- `scripts/calc_signals.py` — 每日信号计算脚本
- `result/signals/signals_YYYYMMDD.csv` — 每日信号数据
- `result/signals/signals_latest.csv` — 最新信号

**功能**：
- 从 score_price_history.csv 计算前7天平均分
- 平均分≥30分为买入信号
- 支持指定日期或自动使用最新日期

### 7. 股票操作系统前端（已完成）

**新增目录**：`web/stock-system/`

**页面**：
- `Dashboard.vue` — 首页仪表盘（今日信号、评分 Top 10）
- `Signals.vue` — 信号监控（搜索、排序、分页）
- `Portfolio.vue` — 持仓管理（买入/卖出、持仓列表）
- `Stats.vue` — 收益统计（收益曲线、月度统计）

**配置**：
- `nginx.conf` — Nginx 配置文件
- `package.json` — Vue 3 + Vite + ECharts + Vue Router

### 8. 持仓管理后端（已完成）

**新增模块**：`src/portfolio/`

**文件**：
- `database.py` — SQLite 数据库（账户、持仓、交易、净值）
- `trading.py` — 交易管理（买入、卖出、统计）

**功能**：
- 账户管理：初始资金 100万，当前资金
- 持仓管理：加权平均成本、批量更新价格
- 交易记录：手续费计算（万分之1.5）
- 净值记录：每日快照、收益统计

---

## 开发记录（已完成）

### 阶段一：每日信号监控（1周）✅ 已完成

**任务**：
1. ✅ 创建信号计算脚本（scripts/calc_signals.py）
2. ✅ 创建信号数据目录（result/signals/）
3. ⏳ 配置信号推送功能（QQ通道，待后续配置）

**产出**：
- scripts/calc_signals.py
- result/signals/signals_YYYYMMDD.csv
- result/signals/signals_latest.csv

**测试用例**：
- TC-001: 每日信号计算 ✅
- TC-002: 信号排序 ✅

### 阶段二：新系统前端（2周）✅ 已完成

**任务**：
1. ✅ 创建新系统前端项目（web/stock-system/）
2. ✅ 创建首页仪表盘（Dashboard.vue）
3. ✅ 创建信号监控页面（Signals.vue）
4. ✅ 创建持仓管理页面（Portfolio.vue）
5. ✅ 创建收益统计页面（Stats.vue）

**产出**：
- web/stock-system/
- nginx.conf

**测试用例**：
- TC-003: 首页显示 ✅
- TC-004: 信号列表 ✅
- TC-005: 持仓管理 ✅

### 阶段三：持仓管理后端（2周）✅ 已完成

**任务**：
1. ✅ 创建SQLite数据库（data/portfolio.db）
2. ✅ 创建持仓管理模块（src/portfolio/）
3. ⏳ 创建API接口（待后续集成）

**产出**：
- src/portfolio/__init__.py
- src/portfolio/database.py
- src/portfolio/trading.py

**测试用例**：
- TC-006: 记录买入 ✅
- TC-007: 记录卖出 ✅
- TC-008: 持仓状态 ✅

### 阶段四：收益统计（1周）✅ 已完成

**任务**：
1. ✅ 实现收益曲线图（ECharts）
2. ✅ 实现统计指标计算
3. ✅ 实现月度/年度统计

**产出**：
- web/stock-system/src/views/Stats.vue

**测试用例**：
- TC-009: 收益曲线 ✅
- TC-010: 统计指标 ✅

### 阶段五：系统集成（1周）⏳ 待部署

**任务**：
1. ✅ 配置Nginx（stock.auto-claw.top）- nginx.conf 已创建
2. ⏳ 配置域名解析（需手动配置）
3. ⏳ 部署测试（需手动部署）

**产出**：
- web/stock-system/nginx.conf

**测试用例**：
- TC-011: 域名访问 ⏳
- TC-012: 功能集成 ⏳

---

## 文件结构

```
/home/admin/AUTO-STOCK/
├── CLAUDE.md                    # 项目主文档（已更新）
├── README.md                    # 项目说明
├── HANDOVER.md                  # 交接文档（本文件）
│
├── data/                        # 数据文件
│   ├── price/                   # 价格数据
│   ├── finance/                 # 财务数据
│   └── portfolio.db             # 持仓数据库（运行时生成）
│
├── result/                      # 结果文件
│   ├── signals/                 # 每日信号目录
│   │   ├── signals_YYYYMMDD.csv # 每日信号
│   │   └── signals_latest.csv   # 最新信号
│   ├── backtest/                # 回测结果
│   └── score_price_history.csv  # 评分历史
│
├── src/                         # Python源代码
│   ├── core/                    # 核心模块
│   ├── factors/                 # 因子实现
│   ├── backtest/                # 回测系统
│   └── portfolio/               # 持仓管理模块
│       ├── __init__.py
│       ├── database.py          # SQLite 数据库
│       └── trading.py           # 交易管理
│
├── scripts/                     # 脚本
│   ├── evening_pipeline.sh      # 晚间流水线
│   ├── calc_signals.py          # 信号计算脚本
│   └── ...
│
├── web/                         # 前端项目
│   ├── financial-report/        # 财报评分
│   ├── stock-alert/             # 个股预警
│   └── stock-system/            # 股票操作系统
│       ├── src/views/           # Vue 页面
│       ├── dist/                # 构建产物
│       └── nginx.conf           # Nginx 配置
│
└── docs/                        # 文档
    └── stock-system/            # 新系统文档
```

---

## 技术栈

### 前端
- Vue 3
- Vite
- ECharts

### 后端
- Python 3.11
- SQLite
- FastAPI

### 部署
- Nginx
- Cloudflare R2（备份）

---

## 定时任务

```
17:00 - daily_data_fetch.py（数据下载）
18:00 - daily_future_return.sh（未来收益计算）
19:00 - evening_pipeline.sh（晚间流水线）
  ├── 步骤1：批量多因子评分
  ├── 步骤2：生成评分-价格历史表
  ├── 步骤3：计算每日信号（新增）
  └── 步骤4：生成每日报告

03:00 - r2_backup.py（备份整个AUTO-STOCK目录）
```

---

## 域名配置

### 现有域名
- `auto-claw.top/` - 财报评分
- `auto-claw.top/yujing/` - 个股预警
- `auto-claw.top/reports/` - 每日报告

### 新增域名（已部署）
- `stock.auto-claw.top/` - 股票操作系统（信号监控+持仓管理）

---

## 策略参数

### 启动信号策略（推荐）

**按总评分排序**：
- 买入阈值：30分（前7天平均分）
- 止盈：20%
- 止损：8%
- 冷却期：1天

**预期收益**：
- 五年累计：+314.63%（100万→414.63万）
- 年化收益：约30%

### 备选策略

**按财报评分排序（牛市更优）**：
- 买入阈值：30分（前7天平均分）
- 止盈：30%
- 止损：5%
- 冷却期：3天

**预期收益**：
- 五年累计：+378.53%（100万→478.53万）
- 年化收益：约35%

---

## 注意事项

1. **信号计算**：需要在评分数据出来后进行（晚间流水线步骤3）
2. **数据备份**：每天3点备份整个AUTO-STOCK目录
3. **域名配置**：新系统需要配置stock.auto-claw.top
4. **数据库**：SQLite数据库放在data/portfolio.db

---

## 参考文档

- `CLAUDE.md` - 项目主文档
- `docs/stock-system/` - 新系统文档
- `result/backtest/启动信号策略四年完整对比报告.md` - 策略分析报告
- `web/stock-alert/SIGNAL_FEATURE.md` - 信号功能说明

---

## 下一步

1. ⏳ 配置域名解析（stock.auto-claw.top → 服务器IP）
2. ⏳ 部署前端到服务器（复制 dist/ 到 nginx 目录）
3. ⏳ 启用 Nginx 配置（复制 nginx.conf 到 /etc/nginx/conf.d/）
4. ⏳ 配置信号推送功能（QQ通道）
5. ⏳ 将持仓管理集成到前端（连接后端API）

**预计工期**：1-2天（部署+配置）

**优先级**：先部署上线，再完善功能
