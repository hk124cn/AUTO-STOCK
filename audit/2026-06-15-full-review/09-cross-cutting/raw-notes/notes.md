# 09-cross-cutting 草稿笔记

## 上次 P0 修复状态追踪

### P0-S2: TUSHARE_TOKEN 泄漏
- 当前 `config/config.py:48-51` → 从 `os.environ["TUSHARE_TOKEN"]` 读（无默认值，缺失即 raise）
- 真实值落在 `.env`（mode 600，git 未跟踪 ✓）
- 之前 commit `6cfc287:config/config.py` 含明文 token → filter-repo 已重写历史（commit 8b938f2）
- **但** `.git.backup-before-filter-repo/` 目录未跟踪但**在 working tree**，是完整 git 仓库 (2MB)，内含未抹除 token 的 config/config.py
  - 验证：`git show 6cfc287:config/config.py` 已抹去；备份目录作为历史副本独立存在
  - 风险：tar/cp -r 打包 / docker COPY / 误推远程会泄漏
- **P0 应判定为已修**，但新增 P0-新：备份目录未排除

### P0-S5: main.py run_batch path traversal
- 当前 `main.py:87-91` 仍是 `filename = f"./result/daily_score/{in_fname}.csv"` 直接拼接
- 仍接受 `../../../etc/...` 输入
- **P0 未修**

## 新增发现

### P0 / 严重 — feedback IP 仍写入文件
- `feedbacks.json` 仍在 git 跟踪（git log --follow 确认 2026-04-27 起）
- 含真实 IP `183.222.203.200`
- 未改 SQLite 存储
- **P0-S3 未修**

### P0 — requirements.txt 仍只 3 行
- 上次报告 P1-S7（api/feedbacks 缺依赖）实际应为 P0，因为 cron + 任何新机器部署必崩
- 仍只 `akshare / pandas / numpy`
- **P1 未修**

### P0 — 前导零 7 处裸 read_csv
- 上次发现 4 处（api/main.py:38, 91, 639, 670, 693 + main.py:61）
- 当前 7 处：新增 2 处（api/main.py:1053 = calc_signals 出口 + line 690/713 已存在）
- 具体行：
  - api/main.py:39（股票池加载）
  - api/main.py:111（get_stock_name 读 stock_full_pool）
  - api/main.py:659（reports/search）
  - api/main.py:690（reports/today）
  - api/main.py:713（reports/top）
  - api/main.py:1053（reports/individual 入口附近）
  - main.py:61（run_batch 入口）
- 仅 api/main.py:111 在读入后补了 `df['code'] = df['code'].astype(str).str.zfill(6)`，其余仍以原始 dtype 拿 → 002697 / 000001 / 300xxx 返回数字 2697 / 1 / 等
- **P1 未修，甚至新增 2 处**

### P0 — main.py input() 无 EOFError 处理
- 上次 P1-S5 仍存在
- 当前 main.py:100/103/107-108 4 处 input() 无 try
- 自动化环境 `printf` 没问题，**`python main.py < /dev/null` 仍崩**
- **P1 未修**

## HANDOVER.md / MAINTENANCE.md / CLAUDE.md

### HANDOVER.md (352 行)
- 写于 2026-05 阶段交付文档
- 阶段一~四（信号、前端、持仓后端、收益统计）标 ✅
- 阶段五（系统集成/部署）⏳ 待部署
- **缺点**：
  - 提及 v1 策略 30分/20%止盈/8%止损/1天冷却
  - **未提 V2 策略**（CLAUDE.md 已提 v2 = 首次突破）
  - **未提 sim_trader.py / 卖信号**
  - "下一步" 仍说"部署"——但实际 stock.auto-claw.top 已上线（CLAUDE.md / MAINTENANCE.md 都说）
  - 阶段五标 "⏳ 待部署" 但 stock-system 已上生产 → **过期**
  - "qq 通道" 信号推送说"待后续配置"——状态不明
- 文档与代码不同步：HANDOVER.md 是 5 月初的快照，CLAUDE.md 是 6 月 15 日版

### MAINTENANCE.md (169 行)
- Nginx 配置示例段（67-105 行）写死 `/home/admin/AUTO-STOCK` 路径
- 与上次审查 P2 跨平台 / 硬编码路径一致 → 重复
- 19:00 写 evening_pipeline.sh，19:30 写 calc_signals.py——**与实际 evening_pipeline.sh 不一致**：实际脚本只有 3 步（main.py / kline_analyzer / daily_report），**未调 calc_signals.py**！
- "MAINTENANCE.md" vs "CLAUDE.md" 内容 80% 重复（架构 + 命令 + 数据存储）

### CLAUDE.md
- 新增 6/15 commit 修改
- 与 6/14 上次审查时的版本相比：增加了 stock-system 描述 + 信号 v1/v2 + 数据存储
- 仍缺 miniprogram 段（小程序的 CLAUDE.md 独立存在）
- "运行测试" `python -m pytest` 写死但 requirements 缺 pytest

### miniprogram/CLAUDE.md
- 微信小程序版财报评分，AppID `wxf1b550fac7e720d6`
- 已注册 4 个页面（index / detail / reports / webview）
- **webview/ 目录存在但未在 app.json 注册**（CLAUDE.md 自己也说"暂未使用"）
- 2026-05-31 bug 修复 + 功能补齐
- node_modules 363MB **未跟踪**（git 干净）
- private key `private.wxf1b550fac7e720d6.key` 在 miniprogram/ 目录，git 已 ignore `*.key private.*` ✓

## meta/ 目录

- 3 文件：factor_config_v1.json / pool_config_v1.json / snapshot_manifest.csv
- `git ls-files meta/` → **不在 git 跟踪**
- `grep -r 'from meta\|import meta' --include='*.py'` → **0 处引用**
- ANALYZER_PLAN.md 提到过，但代码从未读
- factor_config_v1.json: 9 因子权重 100 分 —— 与 src/factors/ 内部硬编码 1:1 对应
- pool_config_v1.json: 自称 1384 股（hs300 + zz1000 + watchlist）但实际 stock_full_pool.csv 是 5000+（A 股全量去北交所/新三板/B股）
- snapshot_manifest.csv: 5/12~5/22 9 天后停更（26 天无更新）

**结论**：meta/ 是早期 plan 文档产物，**事实声明与代码脱节**。上次的 P2-meta 仍成立，甚至更糟（停更 26 天）。

## docs/ 文档站

- docs/README.md：43 行索引
- docs/FACTOR_GUIDE.md：旧文档（git 跟踪，从前存在）
- docs/stock-system/：7 文件（README/FEATURES/API/TESTING/CHANGELOG/DEPLOYMENT/CODE_REVIEW）
- 是 stock.auto-claw.top 系统的文档站骨架
- 重复内容：API.md 应当查 Signals.vue 的实际接口，FEATURES.md 应当查实际功能 → 实际还需到 stock-system 子报告交叉验证
- docs/stock-system/* 全部未跟踪（git status 显示 ??）

## main.py / pool.py / config/config.py

### main.py
- `name = code` (L29) 仍是 P3 小问题
- input() EOFError (L100/103/107-108) P1 未修
- path traversal (L87-91) P0 未修
- 缺 argparse

### pool.py
- 10 行极简
- 写死 `df.to_csv("stock_full_pool.csv", index=False)` 相对路径 P3
- `startswith(("8", "4","9"))` 过滤深 B "200xxx" 漏 → P2 维持
- 缺注释/常量

### config/config.py
- 6/15 commit 改成 env-based
- P0-S2 应已修（取决于 .env 真实值是否轮换 + 备份目录是否在打包外）

## feedbacks.json / miniprogram/node_modules

- `feedbacks.json` git 跟踪（含真实 IP 183.222.203.200）—— P0
- `miniprogram/node_modules` 363MB 未跟踪 ✓
- `miniprogram/CLAUDE.md` 未跟踪 ✓
- `miniprogram/package-lock.json` 未跟踪 ✓

## 上次 P0 修复状态总览

| # | 上次 P0 | 上次严重 | 状态 | 证据 |
|---|---------|---------|------|------|
| S2 | TUSHARE_TOKEN 泄漏 | P0 | ✅ 主体修复 | 改 .env + filter-repo；但 .git.backup-before-filter-repo/ 含未抹除副本 |
| S5 | main.py run_batch path traversal | P0 | ❌ 未修 | main.py:87-91 仍裸拼接 |
| S3 | feedbacks.json IP 隐私 | P0 | ❌ 未修 | 仍写 JSON + git 跟踪 + 含真实 IP |
| F4 | data_fetcher 0 字节 + sel.py | P0 | ✅ 已删 | git status D + .trash/2026-06-15/MANIFEST.md 记录 |
| S1 | API 无认证 | P0 | ✅ 已修 | api/security.py + 11 个 Depends（commit 3db04c0）|
| F5 | 行业映射 33 天未更新 | P0 | ✅ 应已修 | 16:00 数据恢复 + 17:00 cron |
| F10 | 前导零 4 处 | P1 | ❌ 未修 + 新增 3 处 | 当前 7 处裸 read_csv |
| S6 | 死文件 bak/fix | P2 | ✅ 已修 | .trash/2026-06-15/MANIFEST.md 13 个文件归档 |

## P0/P1/P2 数量预估

- P0：~4（feedbacks/S5 path traversal/前导零扩散/无依赖 lock）
- P1：~3（EOFError/无文件锁 feedbacks/无 argparse）
- P2：~5（HANDOVER 过期/meta 停更/pool.py 硬编码/CRON 缺失 calc_signals/main.py name=code）

## Top 3 本轮发现

1. **feedbacks.json 仍含真实 IP + git 跟踪 + 无并发保护**（P0，P0-S3 完全未动）
2. **.git.backup-before-filter-repo/ 是 P0-S2 的暗礁**：含未抹除 token 的完整 git 仓库（2MB），打包/部署/CI COPY 任何一处遗漏都重新泄漏
3. **HANDOVER.md 严重过期**——文档说"阶段五待部署"但 stock-system 已上线；不说 v2、不说 sim_trader、不说卖信号——已成误导文档
