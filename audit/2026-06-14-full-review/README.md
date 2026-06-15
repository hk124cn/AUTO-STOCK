# 全量代码审查 — 2026-06-14

> 启动时间：2026-06-14  
> 目标：全面审查 AUTO-STOCK 系统（9因子评分 + 数据流水线 + Web + 报告 + 回测 + 持仓 + 流水线 + 部署），找潜在坑、不合理可改进点；重点核查已完成回测数据/方法的可靠性。  
> 方式：8 个子任务并行 + 2 轮独立核实 + 1 轮汇总，文档可断档继续。

## 目录结构

```
audit/2026-06-14-full-review/
├── 00-index/                    主报告、汇总、改进路线图
│   ├── REPORT.md                最终主报告（汇总）
│   ├── ROADMAP.md               按优先级排序的改进清单
│   └── _archive/                中间过时快照
├── 01-factor-system/            因子系统
│   ├── raw-notes/               草稿
│   └── final/                   子报告
├── 02-data-pipeline/            数据流水线
├── 03-backtest-system/          回测系统【深度】
│   ├── raw-notes/
│   └── final/
├── 04-web-frontend/             Web 前端
├── 05-report-system/            报告 + 流水线
├── 06-portfolio-and-signals/    持仓 + 信号
├── 07-cron-and-deploy/          Cron / 部署 / 监控
├── 09-cross-cutting/            横向（CLI、配置、错误处理、日志）
└── _shared/                     跨子任务的共用工具
    ├── CONVENTIONS.md           写作约定（如何写子报告）
    └── CHECKLIST.md             审查清单
```

## 断档继续（Resume）

每个子任务写两份文件：
- `raw-notes/notes.md` — 草稿，随写随保存（断档不会丢）
- `final/SUBREPORT-<name>.md` — 收敛版结论

当会话中断后再启动时：
1. 先读 `00-index/REPORT.md` 了解整体进度
2. 对未完成的子任务，读取 `raw-notes/notes.md` 继续追加
3. 所有子报告齐了，再补 `00-index/REPORT.md`

## 子任务清单

| 编号 | 子任务 | 负责维度 | 优先级 |
|------|--------|----------|--------|
| 1 | 因子系统 | 9因子 + 评分引擎 | 高 |
| 2 | 数据流水线 | datafactory | 高 |
| 3 | 回测系统（设计层） | engine/scorer/data | **极高** |
| 3b | 已完成回测（结果层） | 2022-2026 5份回测 | **极高** |
| 4 | Web 前端 | 3 个 Vue 项目 | 中 |
| 5 | 报告 + 流水线 | daily_report + evening_pipeline | 中 |
| 6 | 持仓 + 信号 | portfolio + calc_signals | 高 |
| 7 | Cron / 部署 | cron/api/nginx | 中 |
| 8 | 横向 | CLI/配置/日志 | 中 |

## 总体结论占位

（汇总后写入 00-index/REPORT.md）

## 严重问题 Top-N

（汇总后写入 00-index/REPORT.md）
