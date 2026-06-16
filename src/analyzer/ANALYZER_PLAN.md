# 股票分析系统 v2 - 分析层规划

> 建立时间: 2026-05-24
> 负责人: 1号

---

## 📋 功能说明

### 一、核心目标

在现有评分系统基础上，构建**分析层**，实现：
1. 评分有效性验证（高分股票是否真的涨？）
2. 历史规律挖掘（评分与未来收益的关系）
3. 信号系统（达到阈值自动推送）

### 二、系统定位

```
┌─────────────────────────────────────────────────────────┐
│                    AUTO-STOCK 系统架构                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   数据层 (data/)                                         │
│     ├── price/         历史价格（2016至今）              │
│     ├── finance/       财报数据（2001至今）             │
│     ├── dividend/       分红数据                         │
│     ├── industry/      行业数据                         │
│     └── fund/          资金流向                         │
│                                                         │
│   评分层 (result/daily_score/)                          │
│     └── batch_result_*.csv   每日多因子评分              │
│                                                         │
│   分析层 (src/analyzer/)  ← 本模块                      │
│     ├── score_validator.py   评分有效性验证              │
│     ├── kline_analyzer.py    K线图数据生成               │
│     ├── signal_detector.py   信号检测与推送              │
│     └── label_generator.py   标签生成                    │
│                                                         │
│   元数据 (meta/)                                         │
│     ├── factor_config_v*.json   因子配置版本            │
│     ├── pool_config_v*.json     股票池配置              │
│     └── snapshot_manifest.csv   清单记录               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
/home/admin/AUTO-STOCK/
│
├── data/                    # 数据层（已有）
│   ├── price/             · 历史价格
│   ├── finance/           · 财报数据
│   ├── dividend/          · 分红数据
│   ├── industry/          · 行业数据
│   └── fund/              · 资金流向
│
├── src/                     # 源代码
│   ├── factors/           · 9个因子实现
│   ├── datafactory/       · 数据获取
│   └── analyzer/          · 分析层（本模块）⭐
│       ├── score_validator.py    · 评分有效性验证
│       ├── kline_analyzer.py     · K线图分析
│       ├── signal_detector.py    · 信号检测
│       ├── label_generator.py    · 标签生成
│       └── __init__.py
│
├── result/                  # 评分结果
│   ├── daily_score/       · 每日评分 batch_result_*.csv
│   │   └── bak/
│   └── future_returns/    · 未来收益追踪
│       ├── 5d/future_5d_YYYYMMDD.csv
│       ├── 10d/future_10d_YYYYMMDD.csv
│       └── 20d/future_20d_YYYYMMDD.csv
│
├── meta/                     # 元数据
│   ├── factor_config_v1.json
│   ├── pool_config_v1.json
│   └── snapshot_manifest.csv
│
├── scripts/                 # 每日运行脚本
│   ├── daily_score_gen.py  · 生成每日评分
│   ├── daily_data_fetch.py · 获取数据
│   ├── daily_report.py     · 生成网页报告
│   └── daily_label_gen.py · 生成未来收益标签
│
├── reports/                  # 网页报告
│   └── daily_report_*.html
│
└── web/                      # 前端
    └── dist/
```

---

## 🏗️ 数据存储设计（便于扩展）

### 一、未来收益表结构

**文件路径**: `result/future_returns/{n}d/future_{n}d_{score_date}.csv`

**字段设计**（便于扩展到数据库）:

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| date | TEXT | 记录生成日期(YYYYMMDD) | `20260519` |
| code | TEXT | 股票代码(6位，存文本防前导0) | `600660` |
| name | TEXT | 股票名称 | `平安银行` |
| score_date | TEXT | 评分日期(YYYYMMDD) | `20260519` |
| score_price | REAL | 评分日收盘价(元) | `12.50` |
| nd_date | TEXT | N天后日期(YYYYMMDD) | `20260526` |
| nd_price | REAL | N天后收盘价(元) | `12.91` |
| next_nd_return | REAL | N天后收益率(%)，保留2位 | `3.28` |

**说明**:
- `n` = 5/10/20，分别代表不同追踪周期
- 所有日期格式统一为 YYYYMMDD
- code 存为 TEXT 类型，防止前导0丢失
- 涨幅为浮点数，保留2位小数
- 未来扩展到数据库时，字段名称基本不变

### 二、文件命名规范

```
result/future_returns/
├── 5d/future_5d_YYYYMMDD.csv      ← 5天后收益
├── 10d/future_10d_YYYYMMDD.csv    ← 10天后收益
└── 20d/future_20d_YYYYMMDD.csv    ← 20天后收益
```

- 文件名格式: `future_{n}d_{score_date}.csv`
- `n` = 追踪天数 (5/10/20)
- `score_date` = 评分日期 (YYYYMMDD)
- 例如: `future_5d_20260519.csv` 表示5月19日评分的股票，5天后收益

### 三、元数据表结构

**1. factor_config_v*.json** - 因子配置
```json
{
  "version": "v1",
  "created_date": "20260501",
  "description": "初始9因子评分系统",
  "factors": {
    "单日涨跌幅": {"weight": 10, "max_score": 10, "logic": "趋势感知矩阵"},
    "股息率": {"weight": 10, "max_score": 10, "logic": "分段线性(0-10%)"},
    "财报": {"weight": 20, "max_score": 20, "logic": "扣非净利润+趋势"},
    "5日涨跌幅": {"weight": 10, "max_score": 10, "logic": "分段(-10%~+10%)"},
    "今年相对大盘强弱": {"weight": 10, "max_score": 10, "logic": "相对大盘超额收益"},
    "行业相对强弱": {"weight": 10, "max_score": 10, "logic": "个股vs行业20日强弱"},
    "资金流向": {"weight": 10, "max_score": 10, "logic": "净流入+换手率+涨幅"},
    "新闻": {"weight": 10, "max_score": 10, "logic": "正面新闻数量+关键词"},
    "关注度": {"weight": 10, "max_score": 10, "logic": "用户关注指数+稳定性"}
  },
  "total_weight": 100
}
```

**2. pool_config_v*.json** - 股票池配置
```json
{
  "version": "v1",
  "created_date": "20260501",
  "description": "沪深300 + 中证1000 + 自选股",
  "pools": ["hs300", "zz1000", "watchlist"],
  "stock_count": 1384
}
```

**3. snapshot_manifest.csv** - 清单记录
```csv
date,factor_version,pool_version,stock_count,note
20260519,v1,pool_v1,1384,初始版本
20260525,v2,pool_v2,1420,修改xx因子权重
```

---

## 📊 目标分解列表

### 第一阶段：元数据与数据基础

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 1.1 创建 meta/ 目录结构 | ✅ 完成 | 🔴 高 | ✅ 完成 |
| 1.2 设计 factor_config_v1.json | ✅ 完成 | 🔴 高 | ✅ 完成 |
| 1.3 设计 pool_config_v1.json | ✅ 完成 | 🔴 高 | ✅ 完成 |
| 1.4 设计 snapshot_manifest.csv | ✅ 完成 | 🔴 高 | ✅ 完成 |
| 1.5 回溯标记历史 batch_result | ⚠️ 待确认 | 🟡 中 | **定义待确认**：是生成历史future_returns还是更新manifest？当前历史数据均为v1版本，暂无需标记 |

### 第二阶段：未来收益追踪

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 2.1 future_return_generator.py 脚本 | ✅ 完成 | 🔴 高 | ✅ 完成并测试 |
| 2.2 设置每日定时任务 | ✅ 完成 | 🟡 中 | 18:00运行，cron已配置 |
| 2.3 回溯生成历史标签 | ✅ 完成 | 🟡 中 | 已生成5d历史数据(5.12-5.15) |

### 第三阶段：评分有效性验证

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 3.1 score_validator.py 脚本 | 待做 | 🔴 高 | 验证评分有效性 |
| 3.2 生成验证报告 | 待做 | 🟡 中 | 表格+可视化 |
| 3.3 各因子有效性分析 | 待做 | 🟢 低 | 后续研究 |

### 第四阶段：K线图模块

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 4.1 kline_analyzer.py | 待做 | 🟡 中 | 生成K线+评分数据 |
| 4.2 前端页面开发 | 待做 | 🟢 低 | ECharts展示 |

### 第五阶段：信号系统

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 5.1 signal_detector.py | 待做 | 🟡 中 | 信号检测逻辑 |
| 5.2 推送渠道配置 | 待做 | 🟢 低 | QQ/微信 |
| 5.3 阈值配置界面 | 待做 | 🟢 低 | 方便调整 |

---

## 📈 进度跟踪

| 日期 | 更新内容 |
|------|---------|
| 2026-05-24 | 完成目录结构调整，result/移至根目录，新建future_returns/ |
| 2026-05-24 | 完成meta/目录及文件：factor_config_v1.json, pool_config_v1.json, snapshot_manifest.csv |
| 2026-05-24 | 修复review反馈：添加.gitkeep空目录、清理空文件、明确任务1.5定义 |
| 2026-05-24 | 完成future_return_generator.py：生成5d收益标签5533条 |
| 2026-05-24 | 创建CRON.md：记录每日定时任务流程 |
| - | - |

---

## 📝 课题/待解决问题

### 高优先级

1. **因子配置v1版本**
   - 9个因子的权重、评分逻辑需要完整记录
   - 建议BOSS确认各因子的具体计算方式

2. **label_generator.py 核心逻辑**
   - 如何判断"5天后"是哪一天（考虑周末、节假日）
   - 停牌股如何处理（不复牌无法计算收益）

3. **历史数据补全**
   - 现有的 batch_result 从哪天开始？
   - 需要补多久的历史标签？

### 中优先级

4. **扩展到数据库**
   - 当前用CSV存储，未来可能迁移到SQLite
   - 字段设计已考虑兼容性，但仍需预留 id、created_at 等字段

5. **信号阈值设计**
   - 高分预警：多少分算高？（80？85？）
   - 低分抄底：多少分算低？（20？15？）
   - 是否需要动态阈值（根据市场情况调整）

6. **K线图数据格式**
   - ECharts 需要什么数据格式？
   - 评分曲线如何叠加？

### 低优先级（后续研究）

7. **多因子归因分析**
   - 每个因子对收益的贡献度
   - 哪些因子是"核心因子"？

8. **行业轮动研究**
   - 行业强弱与评分的联动

9. **择时信号**
   - 大盘点位与个股评分的关系
   - 何时仓位应该降低？

---

## 🔗 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| SOUL.md | /workspace/SOUL.md | 核心价值观 |
| MEMORY.md | /workspace/MEMORY.md | 长期记忆 |
| CLAUDE.md | AUTO-STOCK/CLAUDE.md | 项目说明 |

---

## 📌 备注

- 本文档随项目进展持续更新
- 数据库选型待定（SQLite / MySQL / PostgreSQL）
- 量化指标（夏普比率、最大回撤等）后续扩展