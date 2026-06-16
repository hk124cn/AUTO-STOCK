# 股票操作系统 (Stock System)

## 概述

实盘操作管理系统，用于信号监控、持仓管理、收益统计。

## 访问地址

- 主站：stock.auto-claw.top
- 预警图：auto-claw.top/yujing/

## 功能模块

### 1. 信号监控
- 每日信号汇总（v1 每日触发 / v2 首次突破）
- 按财报分数 / 7日均分排序
- 买入/卖出信号显示
- 策略版本切换

### 2. 持仓管理
- 模拟/实盘双账户
- 买入/卖出记录
- 浮动盈亏计算
- 止盈止损管理

### 3. 收益统计
- 收益曲线图
- 月度/年度统计
- 夏普比率、最大回撤

### 4. 策略管理
- v1/v2 策略切换
- 参数配置（阈值、冷却期等）

## 技术栈

- 前端：Vue 3 + ECharts + Vue Router
- 后端：FastAPI + SQLite
- 部署：Nginx + Cloudflare

## 策略参数

### v1 — 每日触发
- 买入条件：7日均分 ≥ 30
- 止盈：20% / 止损：8%
- 冷却期：1天

### v2 — 首次突破
- 买入条件：7日均分首次跨30（昨<30≤今）
- 止盈：20% / 止损：8%
- 冷却期：1天
- 默认按财报分数排序

## 相关文档

- [功能说明](FEATURES.md)
- [API文档](API.md)
- [测试用例](TESTING.md)
- [部署说明](DEPLOYMENT.md)
- [更新日志](CHANGELOG.md)

## 文件结构

```
web/stock-system/
├── src/
│   ├── views/
│   │   ├── Dashboard.vue      # 首页仪表盘
│   │   ├── Signals.vue        # 信号监控（含财报分数排序）
│   │   ├── Portfolio.vue      # 持仓管理
│   │   ├── Strategies.vue     # 策略管理
│   │   └── Stats.vue          # 收益统计
│   ├── data/
│   │   ├── loader.js          # 数据加载（API + CSV）
│   │   └── cache.js           # 智能缓存
│   ├── auth.js                # 认证模块
│   └── authModal.js           # 密码弹窗
├── dist/                      # 构建输出
└── package.json
```

## 数据库设计

数据库文件：`data/portfolio.db`（SQLite，由 `src/portfolio/database.py` PortfolioDB 管理）

### accounts（账户）
```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,              -- 账户名称
    mode TEXT NOT NULL DEFAULT 'SIM', -- SIM=模拟仓, REAL=实盘
    initial_capital REAL NOT NULL DEFAULT 1000000,
    current_capital REAL NOT NULL DEFAULT 1000000,
    strategy_id INTEGER,             -- 绑定的策略ID
    created_at TEXT, updated_at TEXT,
    UNIQUE(name, mode)
);
```

### strategies（策略配置）
```sql
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    buy_threshold REAL NOT NULL DEFAULT 30.0,  -- 买入阈值
    take_profit REAL NOT NULL DEFAULT 0.20,    -- 止盈比例
    stop_loss REAL NOT NULL DEFAULT 0.08,      -- 止损比例
    cooldown_days INTEGER NOT NULL DEFAULT 1,  -- 冷却天数
    max_position_pct REAL NOT NULL DEFAULT 0.20, -- 单只上限比例
    max_positions INTEGER NOT NULL DEFAULT 5,  -- 最大持仓数
    description TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT, updated_at TEXT
);
```

### positions（持仓）
```sql
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    code TEXT NOT NULL, name TEXT NOT NULL,
    shares INTEGER NOT NULL,         -- 持仓股数
    cost_price REAL NOT NULL,        -- 成本价
    current_price REAL,              -- 当前价
    buy_date TEXT NOT NULL,
    buy_score REAL,                  -- 买入时评分
    closed_at TEXT,                  -- 平仓时间
    updated_at TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### trades（交易记录）
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    code TEXT NOT NULL, name TEXT NOT NULL,
    type TEXT NOT NULL,              -- BUY / SELL
    price REAL NOT NULL,
    shares INTEGER NOT NULL,
    amount REAL NOT NULL,            -- 交易金额
    fee REAL NOT NULL DEFAULT 0,     -- 佣金
    stamp_tax REAL NOT NULL DEFAULT 0, -- 印花税
    trade_date TEXT NOT NULL,
    score REAL,                      -- 交易时评分
    reason TEXT,                     -- 交易原因
    created_at TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### daily_nav（每日净值）
```sql
CREATE TABLE daily_nav (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    nav REAL NOT NULL,               -- 净值
    total_assets REAL NOT NULL,      -- 总资产
    position_value REAL NOT NULL,    -- 持仓市值
    cash REAL NOT NULL,              -- 现金
    UNIQUE(account_id, date),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### trade_lots（交易批次，FIFO 成本计算）
```sql
CREATE TABLE trade_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    code TEXT NOT NULL, name TEXT NOT NULL,
    buy_date TEXT NOT NULL,
    buy_price REAL NOT NULL,
    buy_shares INTEGER NOT NULL,
    sell_date TEXT, sell_price REAL,
    sell_shares INTEGER DEFAULT 0,
    remaining_shares INTEGER NOT NULL,
    buy_score REAL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### dividends（分红记录）
```sql
CREATE TABLE dividends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    code TEXT NOT NULL, name TEXT NOT NULL,
    ex_date TEXT NOT NULL,           -- 除权日
    dividend_per_share REAL NOT NULL,
    shares INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```
