# AUTO-STOCK 系统维护文档

## 1. 系统架构

```
用户访问: http://auto-claw.top:3000 (Vite开发服务器)
         └─► api/main.py (FastAPI 8000端口)
              └─► AUTO-STOCK 系统 (src/)
```

**目录结构:**
```
AUTO-STOCK/
├── main.py              # 命令行批量评分入口
├── api/main.py          # FastAPI HTTP服务 (端口8000)
├── web/                 # Vue前端 (3000端口)
├── src/
│   ├── core/            # 核心模块
│   │   ├── base_factor.py       # 因子基类
│   │   ├── factor_manager.py   # 因子动态加载
│   │   └── scoring_engine.py   # 评分引擎
│   ├── factors/         # 因子实现
│   │   ├── financial_factor.py # 财报因子 (满分20分)
│   │   ├── dividend_factor.py  # 股息率因子 (满分10分)
│   │   ├── attention_factor.py # 关注度因子
│   │   ├── zj_flow_factor.py   # 资金流因子
│   │   └── ...
│   ├── datafactory/     # 数据层
│   │   ├── data_manager.py     # 数据统一访问
│   │   ├── market_down.py      # 市场行情下载
│   │   ├── price_builder.py    # 价格数据清洗
│   │   ├── finance_manager.py  # 财务管理
│   │   └── trade_calendar.py   # 交易日历
│   └── result/          # 评分结果输出
└── data/                # 本地数据缓存
    ├── price/           # 个股价格数据
    ├── finance/         # 财务数据缓存
    ├── dividend/        # 分红数据缓存
    ├── daily_market/    # 每日市场快照
    └── attention/       # 关注度数据
```

---

## 2. 因子评分逻辑

### 2.1 财报因子 (Financial Factor) - 满分20分

**数据来源:** AKShare `ak.stock_financial_abstract_ths()`

**评分维度:**
| 指标 | 满分 | 评分逻辑 |
|------|------|----------|
| 扣非净利润同比增长率 | 10分 | 基础分: 40%增长=满分; 趋势分: 连续增长/下降/V型反转 |
| 归母净利润同比增长率 | 5分 | 同上 |
| 营业总收入同比增长率 | 5分 | 同上 |

**趋势评分规则:**
- 连续增长: +15%
- 连续下降: -15%  
- V型反转 (负→正): +10%
- 倒V反转 (正→负): -10%
- 平均变化>5%: +10%
- 平均变化<-5%: -10%

---

### 2.2 股息率因子 (Dividend Factor) - 满分10分

**数据来源:** AKShare `ak.stock_history_dividend_detail()`

**评分规则 (分段线性):**
| 股息率 | 得分 |
|--------|------|
| 0% | 0分 |
| 2% | 4分 |
| 5% | 8分 |
| 8%-10% | 10分 |
| >10% | 6分 (过高可能不稳定) |

---

### 2.3 其他因子
| 因子 | 满分 | 说明 |
|------|------|------|
| attention_factor.py | - | 关注度因子 |
| zj_flow_factor.py | - | 资金流因子 |
| news_factor.py | - | 新闻因子 |
| fiveday_factor.py | - | 五日走势因子 |
| dp_diff_factor.py | - | 大盘差值因子 |
| hy_diff_factor.py | - | 行业差值因子 |

---

## 3. 数据来源与更新

### 3.1 数据源 (AKShare)

| 数据类型 | API | 本地路径 |
|----------|-----|----------|
| 个股价格 | `ak.stock_zh_a_hist()` | `data/price/{code}.csv` |
| 市场行情 | `ak.stock_zh_a_spot()` / `ak.stock_zh_a_spot_em()` | `data/daily_market/{date}.csv` |
| 财务数据 | `ak.stock_financial_abstract_ths()` | `data/finance/{code}.csv` |
| 分红数据 | `ak.stock_history_dividend_detail()` | `data/dividend/{code}.csv` |

### 3.2 更新频率

**定时任务** (crontab):
```
0 16 * * 1-5  cd /home/admin/AUTO-STOCK && python3 scripts/daily_download.py
```
- 每日16:00（A股收盘后）执行
- 仅限交易日（通过 `trade_calendar.is_trade_day()` 判断）

**执行流程:**
```
is_trade_day() → download_market() → build_price()
```

### 3.3 数据缓存策略
- 优先使用本地缓存 (`data/` 目录)
- 如本地无数据或过期，自动从AKShare下载
- 分红数据超过120天自动刷新

---

## 4. 常用命令

### 4.1 启动服务
```bash
# 启动前端 (3000端口)
cd /home/admin/AUTO-STOCK/web && npm run dev

# 启动API (8000端口)
cd /home/admin/AUTO-STOCK && uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4.2 数据更新
```bash
cd /home/admin/AUTO-STOCK && python3 scripts/daily_download.py
```

### 4.3 批量评分
```bash
cd /home/admin/AUTO-STOCK && python main.py
# 选择模式: 1=单股, 2=批量
```

---

## 5. 待实现功能

- [ ] 回测引擎 (`src/core/backtest.py`)
- [ ] 买入/卖出信号提示
- [ ] 每日评分报告自动生成