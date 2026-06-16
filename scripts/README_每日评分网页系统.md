# 每日评分网页系统 — 说明文档

> 最后更新：2026-05-18  
> 作者：1号

---

## 一、系统概述

**每日评分网页系统**是一个自动化的多因子股票评分报告生成系统，每天根据评分引擎输出的 CSV 数据，生成带日期的 HTML 报告，并自动更新 `latest` 副本供用户访问。

**访问地址**：`https://auto-claw.top/reports`

**⚠️ 重要区分**：本系统与 `https://auto-claw.top`（根路径）的**财报评分系统**完全独立，后者是 Vue 3 前端应用，位于 `web/` 目录。两者共用域名但互不关联。

---

## 二、目录结构

```
/home/admin/AUTO-STOCK/
├── scripts/
│   ├── daily_report.py              # 核心报告生成脚本（~964行）
│   ├── daily_report_cron.sh         # 定时执行脚本
│   ├── report_api.py                # 个股报告生成API（端口8766）
│   ├── stock_analysis.py            # 个股深度分析报告生成
│   └── README_每日评分网页系统.md     # 本文档
├── src/
│   └── result/
│       ├── batch_result_YYYYMMDD.csv  # 每日评分引擎输出
│       └── bak/                         # 历史备份
└── reports/
    ├── daily_report_YYYYMMDD.html     # 带日期的HTML报告
    ├── daily_report_YYYYMMDD.md       # 带日期的Markdown报告
    ├── daily_report_latest.html       # 最新报告副本（不带日期）
    ├── daily_report_latest.md         # 最新报告Markdown副本
    └── individual/                    # 个股报告
        ├── stock_analysis_XXXXXX.html
        └── stock_analysis_XXXXXX.md
```

---

## 三、核心文件说明

### 3.1 `scripts/daily_report.py` — 核心生成脚本

**功能**：读取评分结果 CSV + 历史数据，生成 Markdown 和 HTML 两份报告。

**输入**：
- `src/result/batch_result_YYYYMMDD.csv` — 当日评分结果（评分引擎输出）
- 历史所有 `batch_result_*.csv` — 用于走势分析和对比

**输出**：
- `reports/daily_report_YYYYMMDD.html` — 完整 HTML 报告
- `reports/daily_report_YYYYMMDD.md` — Markdown 报告

**报告包含8个板块**：
| 板块 | 内容 |
|------|------|
| 一、大盘概览 | 最高分、最低分、平均分、评分分布柱状图 |
| 二、评分分布 | 各分数段（10分以下~90+）股票数量统计 |
| 三、自选股专区 | 200只自选股按总分排名 |
| 四、特别关注股票分析 | 自选股中的重点股票，9因子拆解 + 历史走势 + 全市场排名 |
| 五、今日 vs 昨日对比 | 评分涨幅/跌幅 TOP 5 |
| 六、5日评分走势分析 | 持续上升/下降（>3分）TOP 5 |
| 七、风险提示 | 多因子全面走弱（≥3个因子≤2分）的股票 |
| 八、投资建议 | 加分股/减分股 + 当日涨跌幅 |

**9个评分因子**：
| 因子名 | 变量名 |
|--------|--------|
| 关注度 | `关注度` |
| 单日涨跌幅 | `单日涨跌幅` |
| 股息率 | `股息率` |
| 今年相对大盘强弱 | `今年相对大盘强弱` |
| 财报 | `财报` |
| 5日涨跌幅 | `5日涨跌幅` |
| 行业相对强弱 | `行业相对强弱` |
| 新闻 | `新闻` |
| 资金流向 | `资金流向` |

**因子评分规则**：
- ≥7分 → 🟢 强
- 4~7分 → 🟡 中
- <4分 → 🔴 弱

**妙想API集成**：通过 `get_stock_changepct()` 函数调用妙想API获取当日涨跌幅数据，用于投资建议板块。

---

### 3.2 `scripts/daily_report_cron.sh` — 定时执行脚本

```bash
#!/bin/bash
cd /home/admin/AUTO-STOCK

TODAY=$(date +%Y%m%d)
python3 scripts/daily_report.py $TODAY

if [ -f reports/daily_report_${TODAY}.html ]; then
    cp reports/daily_report_${TODAY}.html reports/daily_report_latest.html
    echo "✅ 已更新 latest 报告"
fi
```

**工作流程**：
1. 获取当天日期 `YYYYMMDD`
2. 调用 `daily_report.py` 生成报告
3. 将最新报告复制为 `daily_report_latest.html`（不带日期版本）

---

### 3.3 `scripts/report_api.py` — 个股报告生成API

**端口**：8766

**功能**：接收 POST 请求生成个股深度分析报告，支持 SSE 实时推送和轮询降级。

**接口**：
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/generate` | 触发个股报告生成，返回 `generating` / `exists` / `pending` |
| GET | `/api/sse/{code}` | SSE 实时推送生成进度 |
| HEAD | `/reports/individual/stock_analysis_{code}.html` | 检查报告是否存在 |

**报告生成流程**：
1. 前端点击个股 → 检查报告是否存在（HEAD请求）
2. 不存在 → 调用 `/api/generate` 触发后台生成
3. 通过 SSE 接收进度更新 → 完成后自动跳转
4. SSE 失败 → 降级为 2秒轮询

---

### 3.4 `scripts/stock_analysis.py` — 个股深度分析

**功能**：根据股票代码生成个股深度分析报告（HTML + Markdown）。

**输入**：命令行参数 `python3 stock_analysis.py <代码>`

**输出**：`reports/individual/stock_analysis_XXXXXX.html/md`

---

## 四、数据流

```
评分引擎 (main.py)
    │
    ▼ 输出
src/result/batch_result_YYYYMMDD.csv
    │
    ▼ 读取
scripts/daily_report.py
    │
    ├──► reports/daily_report_YYYYMMDD.html  ← nginx serve /reports
    │
    └──► reports/daily_report_YYYYMMDD.md
         │
         ▼ 复制
    reports/daily_report_latest.html  ← 用户访问入口
```

---

## 五、部署方式

**静态部署**：报告是纯静态 HTML 文件，通过 nginx 直接 serve。

**nginx 配置**（推测）：
```nginx
location /reports {
    alias /home/admin/AUTO-STOCK/reports/;
    index daily_report_latest.html;
}
```

**无需前端构建**：与 `web/` 目录的 Vue 项目无关，不需要 `npm run build`。

---

## 六、定时任务

当前通过 `daily_report_cron.sh` 执行，需配置 crontab：

```bash
# 示例：每天交易日 19:00 运行（评分引擎跑完后）
0 19 * * 1-5 cd /home/admin/AUTO-STOCK && bash scripts/daily_report_cron.sh
```

---

## 七、常见问题

### Q1: 网页数据不更新？
- 检查评分引擎是否正常运行，`src/result/` 下是否有最新的 `batch_result_*.csv`
- 手动执行：`python3 scripts/daily_report.py YYYYMMDD`
- 检查 `reports/daily_report_latest.html` 是否已更新

### Q2: 妙想API获取涨跌幅失败？
- 检查 `MX_APIKEY` 环境变量是否配置
- 妙想API有速率限制，大批量查询可能触发限流

### Q3: 历史数据不足？
- 5日走势分析需要至少5天数据
- 昨日对比需要前一天数据存在

### Q4: 个股报告生成慢？
- 个股报告调用外部API获取数据，依赖网络
- 可通过 SSE 或轮询获取进度

---

## 八、文件清单速查

| 文件 | 行数 | 作用 |
|------|------|------|
| `daily_report.py` | ~964 | 核心报告生成 |
| `daily_report_cron.sh` | ~10 | 定时执行 |
| `report_api.py` | ~100 | 个股报告API |
| `stock_analysis.py` | ~270 | 个股深度分析 |
| `stock_web.py` | ~67 | 股票查询Web接口 |

---

## 九、与财报评分系统的区别

| 项目 | 每日评分网页系统 | 财报评分系统 |
|------|-----------------|-------------|
| 地址 | `/reports` | `/`（根路径） |
| 技术 | 静态 HTML（Python生成） | Vue 3 + Vite |
| 目录 | `scripts/` + `reports/` | `web/` |
| 内容 | 全市场多因子评分报告 | 个股财报评分查询 |
| 更新方式 | 定时脚本生成 | 实时API查询 |
| 前端框架 | 无（纯HTML） | Vue 3 + ECharts |

---

## 📋 待办事项

### 手机端样式优化
- **状态**: 待处理
- **问题**: 
  1. 响应式CSS对生成报告不起作用（脚本语法问题）
  2. 即使添加了CSS，效果也不理想（表格边框溢出、布局不协调）
- **后续**: 需要重新设计手机端样式，考虑：
  - 简化表格展示
  - 使用更紧凑的布局
  - 测试后再更新生成脚本

