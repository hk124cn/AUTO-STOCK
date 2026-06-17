# Fix Handoff — 2026-06-17

> 用途：把第三次审查（`audit/2026-06-15-full-review/REPORT.md`）发现的 25 个问题**逐项列出**，
> 让另一个模型/会话按此文档**逐项修复 + 写回状态**。

## 目录

```
audit/2026-06-17-fix-handoff/
├── 00-index/
│   ├── README.md        ← 你正在看（本文件）
│   ├── ISSUES.md        ← 25 个问题的详细清单（按修复顺序）
│   ├── STATUS.md        ← 修复状态表（每修一项更新一行）
│   └── HOWTO.md         ← 给另一模型的"怎么读+怎么改+怎么写回"
└── (之后修代码时可能产生的草稿)
```

## 工作流

```
另模型：
  1. 读 README.md（这页）
  2. 读 ISSUES.md（25 项详细）
  3. 读 audit/2026-06-15-full-review/00-index/REPORT.md（理解背景）
  4. 读 audit/2026-06-15-full-review/00-index/RESPONSE.md（看其他模型怎么回答）
  5. 按 ISSUES.md 顺序**逐项修复**
  6. 每修完一项，**改 STATUS.md 对应行**
  7. 全部修完（或部分放弃），写 SUMMARY.md 总结

我自己（原始审查）：
  1. 收到 SUMMARY.md 后做验收
  2. 跑端到端测试（evening_pipeline + sim_trader + curl）
  3. 决定是否合并到 main
```

## 25 项概览（详见 ISSUES.md）

| 波次 | 项数 | 关键项 | 总工作量 |
|------|------|--------|----------|
| **🔴 第一波（必须先）** | 4 | #1-#4（4 个 P0 阻塞） | 10min |
| **🟠 第二波（P0 完整）** | 7 | #6-#13 | 45min |
| **🟡 第三波（小 P1/P2）** | 5 | #9 #16-#19 | 30min |
| **🟢 第四波（按需）** | 9 | #14 #15 #20-#25 | 数小时 |

**第一波不修，后面都没法验证**（API 端点 500、脚本启动崩、信号不生成）。

## 关键警告（给另一模型）

1. **改任何 P0 前先重启 API**（`sudo systemctl restart stock-api`）—— 让代码生效
2. **改 main.py / api/main.py 后必须 `npm run build` 才会让前端看到新行为**？不，**main.py 是后端脚本，web 是 stock-system 独立项目**。检查是否影响。
3. **sim_trader dry-run 改硬失败前要确保 P0-D 已修**（不然每天 cron 报红）
4. **改数据库 schema（accounts.strategy_id）必须先做 ALTER 兼容迁移**（不要 DROP+CREATE，否则数据丢）
5. **改 requirements.txt 不要动现有 3 行，只追加**
6. **git filter-repo 前必须备份 .git**（上次备份在 `.git.backup-before-filter-repo/`，这次复用）

## 验证流程（修复后必跑）

```bash
# 后端
sudo systemctl restart stock-api
curl -i http://127.0.0.1:8000/api/v1/strategies/active   # 应 200 而非 500

# SELL 端到端
python3 scripts/calc_signals.py --date 20260615 --strategy-version v1
# 期望：跑通 + result/signals/v1/signals_*.csv 含 SELL 行

# 模拟交易
python3 scripts/sim_trader.py --date 20260615 --dry-run
# 期望：跑通 + 打印今日应执行的买卖（不真写）

# 流水线全链路
bash scripts/evening_pipeline.sh 20260615
# 期望：5 步全成功 + exit 0
```

修完且全跑通后，**别忘记**在 STATUS.md 把"全部 ✅ 修完"记下来，并写 SUMMARY.md。
