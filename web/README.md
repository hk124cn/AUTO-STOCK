# AUTO-STOCK Web 系统说明

> 本文件描述 `/home/admin/AUTO-STOCK/web/` 下的各个子项目的功能、现状和部署。

---

## 概览

| URL | 目录 | 类型 | 状态 | 说明 |
|-----|------|------|------|------|
| `/` | `web/financial-report/dist/` | Vue App | ✅ 正常 | 财报评分系统 |
| `/reports/` | `reports/` | 静态HTML | ✅ 正常 | 每日多因子评分 |
| `/yujing/` | `web/stock-alert/dist/` | Vue App | ✅ 正常 | 个股评分预警图 |
| `/api/` | 后端8000端口 | FastAPI | ✅ 正常 | 数据API |
| `/api/generate_report` | 后端8766端口 | Python HTTP | ✅ 正常 | 报告生成 |

---

## 目录结构（已重组）

```
/home/admin/AUTO-STOCK/
├── web/
│   ├── financial-report/        # → /              财报评分（Vue App）
│   │   ├── dist/                # npm run build 输出
│   │   ├── src/views/
│   │   │   ├── Home.vue
│   │   │   └── Detail.vue
│   │   ├── vite.config.js
│   │   └── package.json
│   │
│   ├── stock-alert/             # → /yujing/       个股评分预警图
│   │   ├── dist/                # npm run build 输出
│   │   ├── src/
│   │   │   ├── views/StockKline.vue
│   │   │   └── data/loader.js
│   │   ├── vite.config.js
│   │   └── package.json
│   │
│   └── maintenance.html         # 维护页面
│
├── reports/                     # → /reports/       每日多因子评分
│   ├── index.html
│   └── daily_report_*.html
│
├── result/                      # 评分结果（Nginx 直接读取）
│   ├── score_price_history.csv  # → /yujing/data/score_price_history.csv
│   └── daily_score/
│       └── batch_result_*.csv
│
├── data/                        # 市场数据（Nginx 直接读取）
│   └── price/                   # → /yujing/data/price/
│       ├── 000001.csv
│       ├── 000300.csv           # 沪深300指数
│       └── ...
│
├── api/main.py                  # FastAPI 后端（端口8000）
└── scripts/
    ├── evening_pipeline.sh      # 每日晚间流水线（评分→分析→报告）
    ├── daily_report.py          # 每日报告生成
    ├── start_financial_score.sh # 启动服务脚本
    └── report_api.py            # 报告生成API（端口8766）
```

---

## 1. `/` — 财报评分（Vue App）

**目录**：`web/financial-report/`

**URL**：`https://auto-claw.top/`

**现状**：✅ 正常运行

**Nginx 配置**：
```nginx
location / {
    root /home/admin/AUTO-STOCK/web/financial-report/dist;
    try_files $uri $uri/ /index.html;
}
```

---

## 2. `/reports/` — 每日多因子评分

**目录**：`/home/admin/AUTO-STOCK/reports/`

**URL**：`https://auto-claw.top/reports/`

**现状**：✅ 正常运行，由 `evening_pipeline.sh` 每日自动生成

**Nginx 配置**：
```nginx
location = /reports { return 301 /reports/; }
location /reports/ {
    alias /home/admin/AUTO-STOCK/reports/;
    try_files $uri $uri/ /reports/index.html;
}
```

---

## 3. `/yujing/` — 个股评分预警图

**目录**：`web/stock-alert/`

**URL**：`https://auto-claw.top/yujing/`

**现状**：✅ 正常运行

**功能**：
- 搜索股票（代码或名称），回车直接选中第一条
- 价格K线图（左Y轴，scale:true 动态起点）
- 评分曲线叠加（右Y轴，默认关闭，勾选后叠加显示）
- Tooltip：中文标签（开盘/收盘/最低/最高）+ 涨跌幅（前日收盘价计算）
- 时间范围切换：1M / 3M / 6M / 1Y / All

**数据自动更新**：
- 价格数据：Nginx 直接读取 `data/price/`，每日数据下载后自动生效
- 评分数据：Nginx 直接读取 `result/score_price_history.csv`，晚间流水线自动生成
- 无需 rebuild，无需手动同步，刷新页面即可看到最新数据

**Nginx 配置**：
```nginx
# 评分数据（从 result/ 直接读取，实时更新）
location = /yujing/data/score_price_history.csv {
    alias /home/admin/AUTO-STOCK/result/score_price_history.csv;
}

# 价格数据（从主数据目录直接读取，实时更新）
location /yujing/data/price/ {
    alias /home/admin/AUTO-STOCK/data/price/;
}

# 静态文件
location /yujing/ {
    alias /home/admin/AUTO-STOCK/web/stock-alert/dist/;
    try_files $uri $uri/ /yujing/index.html;
}
```

**技术要点**：
- ECharts candlestick 使用 category 轴时，`p.data` 格式为 `[categoryIndex, open, close, low, high]`（5个值），需从 index 1 开始取 OHLC
- 单 grid 叠加布局：价格K线左Y轴 + 评分曲线右Y轴，避免多 grid 的渲染问题

---

## 4. `/api/` — FastAPI 数据服务

**后端**：`api/main.py`，端口 8000

**URL**：`https://auto-claw.top/api/v1/...`

**现状**：✅ 正常

---

## 5. `/api/generate_report` — 报告生成服务

**后端**：`scripts/report_api.py`，端口 8766

**URL**：`https://auto-claw.top/api/generate_report`

**现状**：✅ 正常

---

## 构建与部署

### 构建前准备
```bash
# 停止服务释放内存（服务器 1.8GB）
ps aux | grep gunicorn | grep -v grep | awk '{print $2}' | xargs -r kill
```

### 构建财报评分
```bash
cd /home/admin/AUTO-STOCK/web/financial-report && npm run build
```

### 构建个股预警
```bash
cd /home/admin/AUTO-STOCK/web/stock-alert && npm run build
```

### 启动服务
```bash
bash /home/admin/AUTO-STOCK/scripts/start_financial_score.sh
```

### Nginx 配置
```bash
sudo nginx -t && sudo nginx -s reload
```
