# HOWTO — 给另一模型/会话的工作指南

## 你是谁

你是另一个 AI 模型（可能是 Claude 也可能是别的），被用户委托**按 `ISSUES.md` 修复 25 个问题**。

## 你该做的

### 1. 读这些（必读）

| 路径 | 为什么读 |
|------|----------|
| `audit/2026-06-17-fix-handoff/00-index/README.md` | 整体流程 |
| `audit/2026-06-17-fix-handoff/00-index/ISSUES.md` | 25 项详细修法 |
| `audit/2026-06-17-fix-handoff/00-index/STATUS.md` | 当前进度 |
| `audit/2026-06-15-full-review/00-index/REPORT.md` | 上下文（为什么有这些问题） |
| `audit/2026-06-15-full-review/00-index/RESPONSE.md` | 其他模型怎么回答的 |

### 2. 修复时

**先修第一波**（#1-#4，10min）—— 不修后面都跑不起来。

**修改文件后必做的事**：
- 后端改动 → `sudo systemctl restart stock-api` → curl 验证
- 数据库 schema 改动 → 修 `_init_db` 加兼容 ALTER（不要 DROP+CREATE）
- requirements.txt 改动 → `pip install -r requirements.txt --dry-run` 验证无冲突
- git filter-repo → 备份 .git → 强推后**用户**确认

### 3. 每修一项，**更新 STATUS.md**

```markdown
| 1 | P0-A `__init__.py` 导入 | ✅ | abc1234 |  |
| 2 | P0-B positions 字段名 | 🔧 |  | 修复中 |
| 3 | P0-C buy_date 格式 | ⏳ |  |  |
```

- 改状态符号
- 写 commit hash（如有 commit）或留空
- 写备注（"已测"、"跳过原因"等）

### 4. 跳过的项怎么标

```markdown
| 14 | live 模式未修 | ⏭️ |  | 用户不用 --live 参数，方案 B（加 docstring）足够 |
```

### 5. 修失败怎么标

```markdown
| 21 | TOCTOU | ❌ |  | 改了但单元测试发现条件 UPDATE 在 WAL 模式下有 race（已留 issue） |
```

### 6. 全部/部分修完后写 SUMMARY.md

`audit/2026-06-17-fix-handoff/00-index/SUMMARY.md` 写：
- 总共修了多少
- 跳过了多少 + 理由
- 新发现的问题（如果修复过程中发现）
- 已知仍存在的风险
- 端到端验证结果（贴 curl/calc_signals/sim_trader/evening_pipeline 输出）

## 你不该做的

- ❌ 不要 commit 任何东西到 main 分支（除非用户明确同意）
- ❌ 不要 force push（git filter-repo 修 #24 之前先备份 .git + 让用户确认）
- ❌ 不要 DROP 数据库表
- ❌ 不要改 CLAUDE.md / HANDOVER.md（这些是项目文档，不属于修复范围）
- ❌ 不要"顺手"做超出 ISSUES.md 范围的修改（如发现新问题就先记录在 SUMMARY，不在本次修复）
- ❌ 不要重命名文件或重构（只做最小修改）

## 修复成功的标志

- STATUS.md 中 16 项必做标记 ✅
- `sudo systemctl restart stock-api && curl -i http://127.0.0.1:8000/api/v1/strategies/active` 返回 200
- `python3 scripts/calc_signals.py --date 20260615` 跑通且生成 SELL 行
- `python3 scripts/sim_trader.py --date 20260615 --dry-run` 跑通
- `bash scripts/evening_pipeline.sh 20260615` 5 步全成功

## 修复失败时

- 任何一步报错
- 在 STATUS.md 该项标 ❌ + 写具体报错
- **不要继续** 后续步骤（避免雪上加霜）
- 在 SUMMARY.md 写"哪一步卡住、为什么"
- 让用户决定下一步

## 完成后

最后一步：在 SUMMARY.md 写"已交付"，让原始审查者（我）做验收。
