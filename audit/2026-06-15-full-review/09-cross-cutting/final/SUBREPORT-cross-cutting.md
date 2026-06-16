# 子报告：横向 / Cross-cutting

> 范围：`HANDOVER.md`、`MAINTENANCE.md`、`CLAUDE.md`、`miniprogram/CLAUDE.md`、`meta/`、`docs/`、`docs/stock-system/`、`main.py`、`pool.py`、`config/config.py`、`requirements.txt`、`feedbacks.json`、`.env`、`.git.backup-before-filter-repo/`、上次 P0 修复状态追踪
> 严重程度评级：P0=功能错误/安全漏洞/P1=性能或安全/P2=可改进/P3=小问题
> 审查日期：2026-06-15

## 1. 概览

横向问题集中在 5 个维度：**(a) 文档失同步**（HANDOVER/MAINTENANCE/CLAUDE 三层重叠且 HANDOVER 严重过期，未提 v2 / 卖信号 / sim_trader）、**(b) 上次 P0 修复不全**（path traversal 与 feedbacks IP 隐私完全未动，requirements 与前导零扩散恶化）、**(c) meta/ 失联**（3 个 JSON/CSV 早被代码脱钩，snapshot_manifest 停更 26 天）、**(d) .git.backup-before-filter-repo/ 暗礁**（完整 git 仓库在 working tree，含未抹除的旧 token，若被打包/部署/CI COPY 任何一处遗漏，S2 修复彻底失效）、**(e) 跨文件配置/依赖碎片化**（requirements 只 3 行、port/path 散布 7+ 处、文档/代码不一致）。好消息：S1（API 鉴权）、S2 主体（token env 化 + filter-repo）、F4（死文件清理）、S6（bak/fix 归档）已确认修复。但 S2 暗礁（备份目录）让 S2 实际未完全闭环。

整体评价：P0 仍存 4 处未修（P0-S3 + P0-S5 + 前导零扩散 + S2 暗礁），文档站新建但失同步，**整体评分与上次持平 = 2/5**。

## 2. 关键发现（按严重程度降序）

### [P0] `feedbacks.json` 仍 git 跟踪 + 含真实 IP + 无并发保护（P0-S3 完全未修）
- 位置：`/home/admin/AUTO-STOCK/feedbacks.json` + `api/main.py:599-635`
- 现象：
  ```python
  # api/main.py:599
  FEEDBACK_FILE = Path(__file__).parent.parent / "feedbacks.json"
  # L616-635
  feedbacks = []
  if FEEDBACK_FILE.exists():
      with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
          feedbacks = json.load(f)
  ...
  feedbacks.append(new_feedback)
  with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
      json.dump(feedbacks, f, ensure_ascii=False, indent=2)
  ```
  `git ls-files feedbacks.json` → 跟踪；`git log --follow feedbacks.json` → 2026-04-27 起入库。当前文件：
  ```json
  [{"id":1,"timestamp":"2026-04-27 23:48:52","ip":"183.222.203.200","code":"002697",...}]
  ```
- 后果：
  - **真实用户 IP 在 git 历史永久保留**（P0-S3 完全未动）
  - 同一毫秒两次 POST 互踩 read-modify-write
  - 单 IP 1s 可发 1000 次 → 文件 grow 至 GB（DoS）
  - 文件无 `.gitignore` 保护
- 证据：`git ls-files feedbacks.json` → 跟踪
- 建议：
  - `echo "feedbacks.json" >> .gitignore` + `git rm --cached feedbacks.json`
  - 写入时 `fcntl.flock(f, fcntl.LOCK_EX)` 或用 SQLite（`src/portfolio/database.py` 已存在可复用）
  - nginx `limit_req_zone` 限流

### [P0] `main.py run_batch` path traversal 完全未修（P0-S5 未动）
- 位置：`/home/admin/AUTO-STOCK/main.py:87-91, 107-108`
- 现象：
  ```python
  def main():
      ...
      elif mode == "2":
          in_file = input("请输入股票池CSV路径:").strip()
          in_fname = input("请输入结果名:").strip()
          run_batch(in_file, in_fname)
  ```
  ```python
  def run_batch(csv_file, in_fname):
      ...
      if in_fname == '':
          filename = f"./result/daily_score/batch_result_{datetime.today().strftime('%Y%m%d')}.csv"
      else:
          filename = f"./result/daily_score/{in_fname}.csv"
      result_df.to_csv(filename, index=False)
  ```
- 后果：
  - `in_fname = "../../../etc/cron.d/backdoor"` → 任意写入
  - 静默覆盖无任何提示
  - cron 用 `printf "2\nstock_pool.csv\n\n"` 没问题；任何人工误输入都触发
- 证据：上轮 P0-S5 报告 24h 前，本轮 0 改动
- 建议：
  - `in_fname = Path(in_fname).name`（强制只取 basename）
  - `if in_fname and not in_fname.replace('_','').isalnum(): raise`
  - 文件已存在时二次确认

### [P0] `.git.backup-before-filter-repo/` 含完整旧 git 仓库，S2 修复存在暗礁
- 位置：`/home/admin/AUTO-STOCK/.git.backup-before-filter-repo/`（2MB，未跟踪 ✓）
- 现象：
  - filter-repo 执行前用户/工具做了完整 `.git/` 备份
  - 备份目录是个**完整 git 仓库**（有 `config/HEAD/index/logs/refs/branches`）
  - 验证：从备份目录的 config 分支 checkout `config/config.py` 仍是旧版（含硬编码 token）
  - 验证：`git show 6cfc287:config/config.py` → 已被 filter-repo 抹除；但**备份目录独立**保存旧版
- 后果：
  - `tar -czf backup.tar.gz /home/admin/AUTO-STOCK` → 备份目录一并打包
  - `COPY . /app`（Dockerfile）→ COPY 进镜像
  - GitHub Actions `actions/checkout@v4` 默认开 `show-progress: true`，但若 `actions/upload-artifact` 配合 `if: always()` → 备份目录会进 artifact
  - r2_backup.py（HANDOVER 提及）备份整个 AUTO-STOCK → 备份目录进 R2
  - **任何一处遗漏 → S2 重新泄漏**
- 证据：`ls -la .git.backup-before-filter-repo/` 显示有 `.git` 内部结构
- 建议：
  - 立即删除 `rm -rf .git.backup-before-filter-repo/`（token 已轮换，旧副本无价值）
  - 或加 `.gitignore` + `mv .git.backup-before-filter-repo /tmp/`
  - 在 CLAUDE.md / 部署文档明示："filter-repo 完成后必须删除备份"

### [P0] `requirements.txt` 缺 7+ 关键依赖，干净环境 `pip install -r` 必崩
- 位置：`/home/admin/AUTO-STOCK/requirements.txt`
- 现象：只 3 行
  ```
  akshare>=1.13.99
  pandas>=2.0.0
  numpy>=1.24.0
  ```
- 后果：
  - `python api/main.py` → `ModuleNotFoundError: No module named 'fastapi'`
  - `python -m pytest` → `No module named 'pytest'`
  - `python -c "import uvicorn"` → 崩
  - `python -c "import pydantic"` → 崩
  - CLAUDE.md 写 `python -m pytest` 但 requirements 不支持（文档与实际不一致）
  - 任何新机器（CI / 同事本地 / 服务器迁移）装完 requirements 跑不了任何服务
- 证据：当前 main.py 已 commit，requirements 是上版
- 建议补齐：
  ```
  akshare>=1.13.99
  pandas>=2.0.0
  numpy>=1.24.0
  fastapi>=0.100.0
  uvicorn[standard]>=0.23.0
  pydantic>=2.0.0
  pytest>=7.0.0
  python-multipart>=0.0.5
  ```

### [P1] 前导零修复（上次 P1）扩散到 7 处裸 read_csv
- 位置：`api/main.py:39, 111, 659, 690, 713, 1053` + `main.py:61`
- 现象：commit `e1c8ea3` 在 `kline_analyzer.py` 加 `dtype={'code': str}`，但其他文件仍裸调用 `pd.read_csv(...)`
- 后果：深市 000xxx / 002xxx / 300xxx 在 API 返回 code 丢前导零（`002697` → `2697`）—— 直接影响：
  - `api/main.py:39` 股票池加载 → 全股票池 code 错
  - `api/main.py:111` get_stock_name → 找不到匹配（已用 `.str.zfill(6)` 救回）
  - `api/main.py:659` reports/search → 模糊匹配 `str.contains` 可能漏
  - `api/main.py:690` reports/today → 全量返回 code 错
  - `api/main.py:713` reports/top → top N code 错
  - `api/main.py:1053` individual reports → 单股报告 code 错
  - `main.py:61` run_batch 入口 → 输出的 batch_result CSV 的 code 列错
- 证据：`grep -nE 'pd\.read_csv' api/main.py main.py | grep -v dtype` → 7 处
- 建议：抽 `safe_read_csv(path, code_cols=['code'])` helper（src/datafactory/data_manager.py 已有雏形）

### [P1] `main.py` 交互模式 EOFError 未处理
- 位置：`/home/admin/AUTO-STOCK/main.py:100, 103, 107-108`
- 现象：4 处 `input()` 无 `try/except EOFError`
- 后果：`python main.py < /dev/null` 抛 EOFError → 流水线崩
- 证据：上轮已报，本轮 0 改动
- 建议：
  ```python
  def safe_input(prompt):
      try:
          return input(prompt).strip()
      except EOFError:
          print("非交互环境，请用 --code / --csv 参数")
          sys.exit(1)
  ```
  或加 `argparse` 支持 `python main.py --code 600519 --csv stock_pool.csv --out result`

### [P1] `feedbacks.json` 写入无文件锁（与 P0-S3 同源但侧重并发）
- 位置：`api/main.py:616-635`
- 现象：read-modify-write 模式无 `fcntl.flock`
- 后果：并发 POST 数据丢失
- 建议：`fcntl.flock(f, fcntl.LOCK_EX)` 或改 SQLite（同 P0-S3 建议）

### [P2] HANDOVER.md 严重过期（352 行误导文档）
- 位置：`/home/admin/AUTO-STOCK/HANDOVER.md`
- 现象：
  - 阶段五"系统集成 ⏳ 待部署"（L186-198）—— 但 stock.auto-claw.top 已上生产
  - "下一步：1. ⏳ 配置域名解析 stock.auto-claw.top → 服务器IP"（L344）—— 已完成
  - "下一步：2. ⏳ 部署前端到服务器" —— 已完成
  - "下一步：3. ⏳ 启用 Nginx 配置" —— 已完成
  - "阶段四：收益统计 ✅"——但 sim_trader 与卖信号在 HANDOVER 写时还未存在
  - **CLAUDE.md 提的 v2 策略**（首次突破）—— HANDOVER 完全没写
  - **scripts/sim_trader.py 卖信号自动平仓** —— HANDOVER 完全没提
  - **scripts/calc_signals.py generate_sell_signals**（L277-364）—— HANDOVER 完全没提
  - HANDOVER 阶段一~四都是 5 月初状态，6/15 已过 1.5 月
- 后果：新成员 / 自己回看时把 1.5 月前的状态当当前
- 建议：
  - 顶部加 "**最后更新：2026-05-12；6/15 后请参考 CLAUDE.md / docs/stock-system/**"
  - 删 HANDOVER.md 整体，统一进 CLAUDE.md
  - 或重写 HANDOVER.md：阶段六 = sim_trader 集成、阶段七 = 卖信号 v1/v2

### [P2] MAINTENANCE.md 重复内容 + 不准确 cron
- 位置：`/home/admin/AUTO-STOCK/MAINTENANCE.md`
- 现象：
  - L116-118 表：19:00 evening_pipeline，19:30 calc_signals.py
  - **实际** `scripts/evening_pipeline.sh`（本次审查重读）只有 3 步：main.py / kline_analyzer / daily_report——**未调 calc_signals.py**
  - 与 CLAUDE.md / HANDOVER.md 内容 80% 重复
  - Nginx 配置段（L67-105）写死 `/home/admin/AUTO-STOCK` 绝对路径
  - `web/maintenance.html` 提及但 `web/` 下不存在此文件（无 git 跟踪也未在工作树）
- 后果：文档失真，cron 表与实际脚本不一致
- 建议：
  - 删 MAINTENANCE.md 整体（与 CLAUDE.md 合并）
  - 至少把"19:30 calc_signals"改成"20:00 calc_signals（手动）"或标"独立脚本，未串入流水线"
  - 加 `web/maintenance.html` 现状说明（"暂无此文件"）

### [P2] `meta/` 目录与代码完全脱钩（5 个文件 0 引用）
- 位置：`/home/admin/AUTO-STOCK/meta/`
- 文件：
  - `factor_config_v1.json`（52 行）— 9 因子权重 100 分
  - `pool_config_v1.json`（16 行）— 自称 1384 股
  - `snapshot_manifest.csv`（9 行）— 5/12~5/22 9 天后停更（停更 26 天）
- 现象：
  - `git ls-files meta/` → **不在 git 跟踪**（✓ 不影响历史，但 working tree 占 3 文件）
  - `grep -rE 'from meta|import meta|meta\.factor|meta\.pool' --include='*.py'` → **0 处引用**
  - `factor_config_v1.json` 的"权重 / max_score / logic" 与 `src/factors/*.py` 内部硬编码一一对应
  - `pool_config_v1.json` 自称 1384 股（hs300+zz1000+watchlist），但 `stock_full_pool.csv` 实际是 5000+ A 股全量（去北交所/新三板/B股）—— 1384 是早期手工股票池的旧数据
  - `snapshot_manifest.csv` 5/22 后无新行（26 天停更）
- 后果：
  - meta 是"事实声明"但与代码脱节——audit trail 失效
  - 任何新成员看到 meta 不知道它已被废弃
  - ANALYZER_PLAN.md 引用了 meta 但代码没真接
- 建议：
  - 方案 A：让 `src/core/factor_manager.py` 真读 `meta/factor_config_v1.json`（让 meta 成为单一权威）
  - 方案 B：删 meta 整个目录，把权重当 `src/factors/` 顶部常量
  - 选 A：把 factor_manager 重构 + 让打分引擎用 meta
  - 选 B：删 `factor_config_v1.json`、`pool_config_v1.json`，保留 `snapshot_manifest.csv` 改为代码自动生成

### [P2] `pool.py` 过滤逻辑 hardcode 字符串 + 相对路径
- 位置：`/home/admin/AUTO-STOCK/pool.py:6-7`
- 现象：
  ```python
  df = df[~df["code"].str.startswith(("8", "4","9"))]  # 过滤北交所,新三板，B股
  df.to_csv("stock_full_pool.csv", index=False)
  ```
- 后果：
  - 沪 B "900xxx" 在 "9" 开头过滤掉 ✓
  - 深 B "200xxx" **不在 "9" 开头** → 漏（深 B 会被保留但 stock_full_pool.csv 用作 API 数据源）
  - 字符串字面量分散
  - `to_csv("stock_full_pool.csv")` 相对路径 → 必须 `cd /home/admin/AUTO-STOCK && python pool.py` 才正确
- 建议：
  ```python
  EXCLUDE_PREFIXES = ("4", "8", "9", "200")  # 新三板/北交所/沪B/深B
  ROOT = Path(__file__).resolve().parent
  df.to_csv(ROOT / "stock_full_pool.csv", index=False)
  ```
  写 unit test 验证深 B 也被过滤

### [P2] `evening_pipeline.sh` 未集成 `calc_signals.py`（与 HANDOVER/MAINTENANCE 不一致）
- 位置：`/home/admin/AUTO-STOCK/scripts/evening_pipeline.sh` + `MAINTENANCE.md:116-118`
- 现象：
  - `evening_pipeline.sh` 只有 3 步：main.py / kline_analyzer / daily_report
  - **未调** `scripts/calc_signals.py`
  - 但 HANDOVER L57-60 写"执行顺序：步骤3：计算每日信号（calc_signals.py，v1/v2 策略）"
  - MAINTENANCE L117 写"19:30 calc_signals.py"
  - CLAUDE.md L120 写"晚间流水线... 串联执行：批量评分 → kline_analyzer → 每日报告"
- 后果：
  - 信号 v1/v2 CSV 实际是手工 `python calc_signals.py`（CRON.md 未列）
  - 文档与脚本不同步
  - 新增 v2 卖信号若不串入流水线，sim_trader 卖信号自动平仓失灵
- 建议：
  - 在 `evening_pipeline.sh` 步骤 3 后加步骤 4：`python scripts/calc_signals.py || fail "signals"`
  - 或写 `scripts/daily_signal.sh` + 加 cron 20:00
  - 更新 CRON.md / MAINTENANCE.md 同步

### [P2] 端口/host 硬编码散布（与上轮 P2 一致，本轮新增 1 处）
- 现象：
  | 文件 | 行 | 内容 |
  |------|----|----|
  | `deploy/stock-api.service` | 12 | `--host 127.0.0.1 --port 8000` |
  | `deploy/stock-system.conf` | 49 | `proxy_pass http://127.0.0.1:8000` |
  | `scripts/start_financial_score.sh` | 22 | `--bind 0.0.0.0:8000` |
  | `scripts/start_financial_score.sh` | 29 | `--host 0.0.0.0 --port 3000` |
  | `scripts/monitor_api.sh` | 5-6 | `API_PORT=8000` |
  | `api/main.py:526` | L526 | `host="0.0.0.0", port=8000` |
  | `MAINTENANCE.md:11` | L11 | `/api/ FastAPI 后端（8000端口）` |
- 后果：改端口需 7+ 处同步
- 建议：抽 `.env` + `python-dotenv`，或至少加 `STOCK_API_PORT=8000` 常量

### [P2] miniprogram/webview 目录存在但未注册
- 位置：`/home/admin/AUTO-STOCK/miniprogram/pages/webview/`
- 现象：`webview.js / .wxml / .json / .wxss` 都存在，4 个文件
- `app.json` 实际未注册 `pages/webview/webview`（miniprogram/CLAUDE.md 自己说"暂未使用"）
- 后果：死代码 / 误导——新成员不知道能不能用
- 建议：删 `pages/webview/` 整个目录，或在 `app.json` 注册

### [P2] 日志格式简陋 / 无轮转（与上轮 P2 一致）
- 位置：`api/main.py:62-69`
- 现象：format 仍是 `'%(message)s'`，无 timestamp/level/模块
- 后果：`logs/access.log` 持续 grow（已 212KB → 当前更久）
- 建议：format 加 `%(asctime)s [%(levelname)s] %(name)s: %(message)s`；FileHandler 加 `maxBytes=10MB, backupCount=5`

### [P3] `main.py run_single` `name = code` 股票名始终是代码
- 位置：`/home/admin/AUTO-STOCK/main.py:29`
- 现象：`def run_single(code): name = code` —— 显示"=== 600519 多因子评分系统 ==="
- 建议：参考 `api/main.py:84-100` 的 `get_stock_name` 读 `stock_full_pool.csv`

### [P3] `src/config.py` 仍是空文件但 git 跟踪
- 位置：`/home/admin/AUTO-STOCK/src/config.py`（如存在）
- 现象：上轮 P2，本次未复查（不在本轮范围）
- 建议：`rm src/config.py`

### [P3] `docs/stock-system/` 文档站与 stock-system 子报告范围重叠
- 现象：`docs/stock-system/{README,FEATURES,API,TESTING,CHANGELOG,DEPLOYMENT,CODE_REVIEW}.md` 与 stock-system 子报告（04）范围重叠
- 建议：与 04 子报告交叉验证 API.md 是否与实际 API 一致；CHANGELOG.md 是否记了 v2 上线

### [P3] miniprogram/node_modules/ 363MB 在 working tree
- 现象：`du -sh miniprogram/node_modules/` → 363M
- 未跟踪 ✓（git 干净）
- 后果：占用磁盘
- 建议：`.gitignore` 加 `miniprogram/node_modules/`（已隐式忽略"node_modules"吗？验证：`git check-ignore` 不报错 → 未忽略）
  - 验证：`git check-ignore -v miniprogram/node_modules/foo` → 无 ignore（应加规则）

## 3. 改进建议（非问题，但有更好做法）

1. **统一文档站**：删 HANDOVER.md + 合并 MAINTENANCE.md 进 CLAUDE.md。三份文档 80% 重复。
2. **HANDOVER.md 重写**：把"阶段六 = sim_trader 集成 / 阶段七 = 卖信号 v1/v2"加上；删"待部署"等过期内容。
3. **`meta/` 决策**：选 A（让 factor_manager 读 meta）或选 B（删 meta），别再悬空。
4. **feedbacks.json 立即清理**：`.gitignore` + `git rm --cached` + IP 字段删。
5. **`.git.backup-before-filter-repo/` 立即删**：filter-repo 完成后没保留价值，留着是 S2 暗礁。
6. **`requirements.txt` 用 `pip-compile` 生成**：从 `pyproject.toml` 锁版本，避免人工漏包。
7. **argparse 加 main.py**：`python main.py --code 600519 --csv stock_pool.csv --out result.csv` —— 同时解决 EOF + path traversal。
8. **CLI 单因子失败不影响整体**：参考 `src/core/factor_manager.py:24-32` 的 try/except 模式，main.py 的 `run_single` 也加。
9. **`safe_read_csv` 抽 helper**：src/datafactory/data_manager.py 加 `def safe_read_csv(path, code_cols=('code',))`，7 处统一调用。
10. **CRON.md / MAINTENANCE.md 同步**：evening_pipeline.sh 加 calc_signals.py 步骤，三份文档同步。
11. **audit 目录 `audit/2026-06-15-full-review/` 自身同步**：00-index 写 README.md 但实际不存在——本目录的 README 改到 _shared/CHECKLIST 或自检。

## 4. 需要核实的不确定项

- `.git.backup-before-filter-repo/` 是否会被 CI 流程拷贝？（看 `.github/workflows/*.yml`）
- `evening_pipeline.sh` 加 calc_signals.py 后会否影响 v1/v2 signal CSV 命名约定（v1/signals_YYYYMMDD.csv vs v2/...）？
- `meta/factor_config_v1.json` 9 因子权重是否与 `src/factors/*.py` 完全一致？（需 factor-by-factor 对比）
- HANDOVER.md "5 阶段" 标的是否对应当前 git tag / commit？（建议与 5 月初的 commit 比对）
- `docs/stock-system/API.md` 是否与 `api/main.py` 实际路由一致？建议在 04 子报告交叉验证。
- `miniprogram/webview/` 4 个文件 —— 微信 web-view 组件需 ICP 备案域名才能用，可能是合规原因没启用。

## 5. 上次 P0 修复状态总表

| # | 上次 P0 | 上次严重 | 状态 | 证据 |
|---|---------|---------|------|------|
| S2 | TUSHARE_TOKEN 泄漏 | P0 | ⚠️ 主体修复，暗礁未消 | config.py 改 .env + filter-repo + 8b938f2 标记完成；但 .git.backup-before-filter-repo/ 含未抹除副本 |
| S5 | main.py run_batch path traversal | P0 | ❌ 完全未修 | main.py:87-91 仍裸拼接 |
| S3 | feedbacks.json IP 隐私 | P0 | ❌ 完全未修 | 仍写 JSON + git 跟踪 + 含真实 IP 183.222.203.200 |
| F4 | data_fetcher 0 字节 + sel.py | P0 | ✅ 已删 | git status D + .trash/2026-06-15/MANIFEST.md |
| S1 | API 无认证 | P0 | ✅ 已修 | api/security.py + 11 个 Depends（commit 3db04c0）|
| F5 | 行业映射 33 天未更新 | P0 | ✅ 应已修 | 16:00 数据恢复 + 17:00 cron |
| F10 | 前导零 4 处 | P1 | ❌ 恶化（4→7 处） | 当前 7 处裸 read_csv |
| S6 | 死文件 bak/fix | P2 | ✅ 已修 | .trash/2026-06-15/MANIFEST.md 归档 13 个文件 |
| S7 | requirements 缺 fastapi | P1 | ❌ 完全未修 | 仍只 3 行 |
| S8 | CLI EOFError | P1 | ❌ 完全未修 | 4 处 input() 仍无 try |

**P0 修复率：4/6 (S1/S2 主体/F4/F5/S6 = 5 修 + S2 暗礁 1 半修；S3/S5 = 2 完全未修)**
**P1 修复率：0/3 (F10 恶化 + S7/S8 完全未修)**

## 6. 评分（1-5，5 = 优）

- 正确性：2（feedbacks IP 隐私 / path traversal / 前导零扩散 / 依赖缺失 / 备份目录暗礁）
- 可维护性：2（3 份文档重复 + meta 脱钩 + HANDOVER 过期 + cron 与文档不一致）
- 性能：3（无显式瓶颈，但 main.py sleep(0.5) × 1385 是隐性慢）
- 文档：2（HANDOVER 过期 1.5 月 + meta 失同步 + 缺 miniprogram 段）
- **总评：2**（P0 修复不完整；新增 P0 暗礁 + 文档失同步；与上次基本持平）

---

## 附：本轮 Top-3 发现

1. **`feedbacks.json` 完全未修** —— 上次 P0-S3 24h 前报告，本轮 0 改动；含真实 IP `183.222.203.200`、git 跟踪、无文件锁
2. **`.git.backup-before-filter-repo/` 是 S2 修复暗礁** —— 2MB 完整 git 仓库在 working tree，含未抹除的旧 token；任何 `tar` / `docker COPY` / `upload-artifact` / r2_backup.py 备份都会重新泄漏
3. **HANDOVER.md 严重过期** —— 352 行文档说"阶段五待部署"但 stock-system 已上线；不提 v2、不提 sim_trader、不提卖信号；已变成误导文档
