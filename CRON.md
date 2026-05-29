# AUTO-STOCK 每日定时任务

> 本文档记录系统的每日定时运行流程

---

## 每日定时任务表

| 时间 | 任务 | 脚本 | 说明 |
|------|------|------|------|
| 17:00 | 拉取当天市场数据 | `scripts/daily_download.sh` | 下载价格、资金流向、行业等 |
| 18:00 | 生成未来收益标签 | `scripts/daily_future_return.sh` | 计算5d/10d/20d收益 |
| 19:00 | 晚间流水线 | `scripts/evening_pipeline.sh` | 评分→分析→报告（串联执行） |

---

## 晚间流水线 (evening_pipeline.sh)

19:00 启动，依次执行以下步骤，任一步失败会停在该步并记录日志：

```
步骤1: 批量多因子评分 (main.py)
    ↓ 成功后
步骤2: 生成评分-价格历史表 (kline_analyzer.py)
    ↓ 成功后
步骤3: 生成每日报告 (daily_report.py) + 更新 reports/index.html
```

**日志**：`logs/evening_pipeline_YYYYMMDD.log`

**Cron 配置**：
```
0 19 * * 1-5 bash /home/admin/AUTO-STOCK/scripts/evening_pipeline.sh >> /home/admin/AUTO-STOCK/logs/evening_pipeline.log 2>&1
```

---

## 完整流程图

```
17:00 ──────────────────────────────────────────────
    │
    ▼
┌─────────────────┐
│ daily_download   │  拉取当日市场数据
│ (scripts/)      │  - 价格数据 → data/price/
└────────┬────────┘  - 资金流向 → data/fund/
         │          - 行业涨幅 → data/industry/
         ▼
18:00 ──────────────────────────────────────────────
    │
    ▼
┌─────────────────┐
│ future_return    │  生成未来收益标签
│ (scripts/)      │  - 计算5d/10d/20d收益率
└────────┬────────┘  - 输出到 result/future_returns/
         │
         ▼
19:00 ──────────────────────────────────────────────
    │
    ▼
┌──────────────────────────────────────────────────┐
│ evening_pipeline.sh                              │
│                                                  │
│  步骤1: main.py 批量多因子评分                    │
│    → result/daily_score/batch_result_YYYYMMDD.csv│
│                                                  │
│  步骤2: kline_analyzer.py 评分-价格历史表         │
│    → result/score_price_history.csv              │
│    → 自动更新 /yujing/ 网页数据                   │
│                                                  │
│  步骤3: daily_report.py 每日报告                  │
│    → reports/daily_report_YYYYMMDD.html          │
│    → reports/index.html                          │
│    → 自动更新 /reports/ 网页                      │
└──────────────────────────────────────────────────┘
```

---

## 数据依赖关系

```
数据层 (data/)
├── price/          ← daily_download 下载
├── finance/        ← 定期更新
├── dividend/       ← 定期更新
├── industry/       ← daily_download 下载
└── fund/           ← daily_download 下载
         │
         ▼
评分层 (result/)
├── daily_score/
│   └── batch_result_YYYYMMDD.csv  ← main.py 生成
├── score_price_history.csv        ← kline_analyzer.py 生成
└── future_returns/                ← future_return_generator 生成
```

---

## 数据自动更新

以下数据通过 Nginx 直接读取源目录，更新后刷新网页即可看到最新数据：

| 数据 | Nginx 路径 | 源目录 | 更新时机 |
|------|-----------|--------|---------|
| 个股价格 | `/yujing/data/price/` | `data/price/` | 17:00 daily_download |
| 评分历史 | `/yujing/data/score_price_history.csv` | `result/score_price_history.csv` | 19:00 evening_pipeline 步骤2 |
| 每日报告 | `/reports/` | `reports/` | 19:00 evening_pipeline 步骤3 |

---

## 手动触发

```bash
# 手动跑晚间流水线（默认今天）
bash scripts/evening_pipeline.sh

# 指定日期
bash scripts/evening_pipeline.sh 20260528

# 单独跑评分
echo -e "2\nstock_pool.csv\n\n" | python3 main.py

# 单独跑 kline_analyzer（增量）
python3 src/analyzer/kline_analyzer.py --date 20260528

# 重建全部评分历史（修复数据用）
python3 src/analyzer/kline_analyzer.py --force
```

---

## 日志位置

| 日志 | 路径 |
|------|------|
| 晚间流水线 | `logs/evening_pipeline_YYYYMMDD.log` |
| 数据下载 | `logs/daily_download_YYYYMMDD.log` |
| 未来收益 | `logs/future_return_YYYYMMDD.log` |
| Gunicorn | `/tmp/gunicorn.log` |
| Nginx | `/var/log/nginx/` |
