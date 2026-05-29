# AUTO-STOCK 系统维护文档

## 1. 系统架构

```
用户访问: https://auto-claw.top/
         ├─→ /              财报评分（Vue App 静态文件）
         ├─→ /reports/      每日多因子评分（静态HTML）
         ├─→ /yujing/       个股评分预警图（Vue App 静态文件）
         ├─→ /api/          FastAPI 后端（8000端口）
         └─→ /api/generate_report  报告生成（8766端口）
```

**目录结构:**
```
AUTO-STOCK/
├── main.py              # 命令行批量评分入口
├── api/main.py          # FastAPI HTTP服务 (端口8000)
├── web/
│   ├── financial-report/   # → /  财报评分 Vue App
│   ├── stock-alert/        # → /yujing/  个股预警 Vue App
│   └── maintenance.html    # 维护页面
├── reports/             # → /reports/  每日报告
├── result/              # 评分结果
│   ├── daily_score/     # batch_result_*.csv
│   └── score_price_history.csv  # 评分-价格历史大表
├── data/                # 本地数据缓存
│   ├── price/           # 个股价格数据（Nginx 直接读取）
│   ├── finance/         # 财务数据缓存
│   ├── dividend/        # 分红数据缓存
│   ├── daily_market/    # 每日市场快照
│   ├── attention/       # 关注度数据
│   ├── fund/            # 资金流向数据
│   └── industry/        # 行业映射+涨跌幅
├── src/                 # 评分系统源码
│   ├── core/            # 核心模块
│   ├── factors/         # 因子实现（9个因子）
│   ├── datafactory/     # 数据层
│   └── analyzer/        # 分析器（kline_analyzer）
└── scripts/
    ├── evening_pipeline.sh      # 每日晚间流水线
    ├── daily_report.py          # 每日报告生成
    ├── start_financial_score.sh # 启动服务脚本
    └── report_api.py            # 报告生成API
```

---

## 2. Nginx 配置

配置文件：`/etc/nginx/conf.d/auto-claw.top.conf`

```nginx
# 财报评分
location / {
    root /home/admin/AUTO-STOCK/web/financial-report/dist;
    try_files $uri $uri/ /index.html;
}

# 每日报告
location = /reports { return 301 /reports/; }
location /reports/ {
    alias /home/admin/AUTO-STOCK/reports/;
    try_files $uri $uri/ /reports/index.html;
}

# 个股预警 - 评分数据（自动更新）
location = /yujing/data/score_price_history.csv {
    alias /home/admin/AUTO-STOCK/result/score_price_history.csv;
}

# 个股预警 - 价格数据（自动更新）
location /yujing/data/price/ {
    alias /home/admin/AUTO-STOCK/data/price/;
}

# 个股预警 - 静态文件
location /yujing/ {
    alias /home/admin/AUTO-STOCK/web/stock-alert/dist/;
    try_files $uri $uri/ /yujing/index.html;
}

# API 代理
location /api/generate_report {
    proxy_pass http://127.0.0.1:8766;
}
location /api/ {
    proxy_pass http://127.0.0.1:8000;
}
```

---

## 3. 每日定时任务

| 时间 | 任务 | 脚本 |
|------|------|------|
| 17:00 | 拉取市场数据 | `scripts/daily_download.sh` |
| 18:00 | 未来收益标签 | `scripts/daily_future_return.sh` |
| 19:00 | 晚间流水线 | `scripts/evening_pipeline.sh`（评分→分析→报告）|

详见 `CRON.md`。

---

## 4. 常用命令

### 启动服务
```bash
bash /home/admin/AUTO-STOCK/scripts/start_financial_score.sh
```

### 构建前端（需先停 gunicorn 释放内存）
```bash
ps aux | grep gunicorn | grep -v grep | awk '{print $2}' | xargs -r kill
cd /home/admin/AUTO-STOCK/web/financial-report && npm run build
cd /home/admin/AUTO-STOCK/web/stock-alert && npm run build
```

### 数据更新
```bash
python3 scripts/update_data.py
```

### 批量评分
```bash
echo -e "2\nstock_pool.csv\n\n" | python3 main.py
```

### 重建评分历史
```bash
python3 src/analyzer/kline_analyzer.py --force
```

### Nginx
```bash
sudo nginx -t && sudo nginx -s reload
```

---

## 5. 数据自动更新机制

个股预警页面 (`/yujing/`) 的数据通过 Nginx 直接读取源目录：

| 数据 | 源目录 | 更新时机 |
|------|--------|---------|
| 个股价格 | `data/price/` | 17:00 daily_download |
| 评分历史 | `result/score_price_history.csv` | 19:00 evening_pipeline 步骤2 |

更新后刷新网页即可看到最新数据，无需 rebuild 或手动同步。
