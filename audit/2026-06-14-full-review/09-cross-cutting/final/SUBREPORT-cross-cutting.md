# 子报告：横向 / Cross-cutting

> 范围：`config/config.py`、`requirements.txt`、`pool.py`、`main.py`（CLI）、`feedbacks.json`、`meta/`、日志系统、跨平台兼容性、bak/fix 清理、前导零修复扩散、CLI 健壮性
> 严重程度评级：P0=功能错误/安全漏洞/P1=性能或安全/P2=可改进/P3=小问题
> 审查日期：2026-06-14

## 1. 概览

AUTO-STOCK 的横向问题集中在 4 个维度：**(a) 已 commit 的 secret**（TUSHARE_TOKEN）、**(b) 前导零修复不完整**（commit `08e6abb` 只修了一半位置）、**(c) CLI 的 path traversal 与 EOF 健壮性**（用户输入直接拼到 filename）、**(d) 日志/监控/路径的跨平台碎片化**（无 logrotate、`python3` hardcode、相对路径）。配置文件 `config/config.py` 只有一个无用变量，`src/config.py` 存在但是空文件——配置体系形同虚设，魔法数字散布在 7+ 个文件。git 对 `.bak/.fix` 文件保持干净（未跟踪）✓，但工作树仍存 3 个旧版本共 100KB+，与重复内容浪费。`requirements.txt` 只有 3 行，缺 fastapi/uvicorn/pydantic/starlette/pytest——任何干净环境装 requirements 后**跑不了 API 或测试**。

整体评价：能跑但脆弱；横向安全/可移植性需多文件协同重构。

## 2. 关键发现（按严重程度降序）

### [P0] TUSHARE_TOKEN 真实值已 commit 到 git，且无人使用
- 位置：`/home/admin/AUTO-STOCK/config/config.py:2`
- 现象：
  ```python
  TUSHARE_TOKEN = "OLD_TUSHARE_TOKEN_REDACTED"  # 去 tushare 官网注册并获取
  ```
  `git ls-files config/config.py` 确认在 git 跟踪
- 后果：
  - 即使 working tree 删除，git 历史永久保留 token
  - 任何人 clone 仓库都拿到 token
  - 攻击者可在 tushare.pro 用此 token 调 API（限速配额被滥用）
- 证据：`grep -rn "tushare" --include='*.py' .` → **零 import**。token 是死代码（dead config）。
- 建议：
  1. **立即轮换 token**（去 tushare 官网 revoke 旧值）
  2. `git filter-repo --invert-paths --path config/config.py` 或 `bfg --replace-text`
  3. 改用 `os.environ.get('TUSHARE_TOKEN')` + 在 README 加 "如何配置"
  4. 既然没人 import，要么补上 `src/datafactory/data_manager.py` 的 tushare 集成，要么**整个删除 config/config.py**

### [P0] `main.py run_batch` 把用户输入直接拼到 filename（path traversal 任意写入）
- 位置：`/home/admin/AUTO-STOCK/main.py:107-108, 87-91`
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
      result_df.to_csv(filename, index=False)  # 静默覆盖
  ```
- 后果：
  - 用户输入 `in_fname = "../../../etc/cron.d/backdoor"` → **任意文件覆盖/写入**（若以 admin 跑 cron，威胁极大）
  - 用户输入 `in_fname = "/tmp/x"` → 写到 `/tmp/x` 绕过项目目录
  - **静默覆盖**已有同名文件无任何提示
- 证据：单股模式 + 批量模式均在 cron `evening_pipeline.sh` 调用：
  ```bash
  # scripts/evening_pipeline.sh:57
  printf "2\nstock_pool.csv\n\n" | python3 main.py
  ```
  自动化调用没问题，但**任何人工误输入**都触发路径遍历
- 建议：
  - `in_fname` 强制 `.csv` 后缀，strip `../`、`/`、空格
  - 用 `pathlib.Path(in_fname).name` 只取 basename
  - 文件已存在时 `print("已存在，是否覆盖？(y/N)")` 二次确认

### [P1] `requirements.txt` 缺 fastapi / uvicorn / pydantic / starlette / pytest
- 位置：`/home/admin/AUTO-STOCK/requirements.txt`
- 现象：只有 3 行
  ```
  akshare>=1.13.99
  pandas>=2.0.0
  numpy>=1.24.0
  ```
- 后果：
  - 新机器 `pip install -r requirements.txt` 后 `python api/main.py` 会 `ModuleNotFoundError: No module named 'fastapi'`
  - `python -m pytest` 也会失败（缺 pytest）
  - CLAUDE.md 写 `python -m pytest` 但 requirements 不支持
- 建议补齐：
  ```
  akshare>=1.13.99
  pandas>=2.0.0
  numpy>=1.24.0
  fastapi>=0.100.0
  uvicorn[standard]>=0.23.0
  gunicorn>=21.0.0
  pydantic>=2.0.0
  pysqlite3>=0.6.0; python_version >= '3.11'
  pytest>=7.0.0
  starlette>=0.27.0
  python-multipart>=0.0.5
  ```

### [P1] 前导零修复（commit 08e6abb）只覆盖部分位置
- 位置：`api/main.py:38, 91, 639, 670, 693` + `main.py:61`
- 现象：commit `08e6abb` 在 `kline_analyzer.py` 加 `dtype={'code': str}`，但其他地方仍裸调用 `pd.read_csv(...)`
- 后果：深市股票（000xxx / 002xxx / 300xxx）在 API 层（`/api/v1/reports/today`、`/api/v1/reports/top`、`/api/v1/scores/latest`）和 CLI 层（`main.py run_batch`）返回 code 可能丢前导零
- 证据：
  ```bash
  $ grep -nE 'pd\.read_csv' api/main.py main.py | grep -v 'dtype'
  api/main.py:38:  df = pd.read_csv(STOCK_POOL_FILE)
  api/main.py:91:  df = pd.read_csv(pool_file)
  api/main.py:639: df = pd.read_csv(result_file)
  api/main.py:670: df = pd.read_csv(result_file)
  api/main.py:693: df = pd.read_csv(result_file)
  main.py:61:  df = pd.read_csv(csv_file)
  ```
- 建议：抽 `src/datafactory/data_manager.py` 的 `safe_read_csv(path, code_cols=['code'])` helper，全部统一调用

### [P1] `main.py` 交互模式 EOF 未处理（非交互环境会 traceback）
- 位置：`/home/admin/AUTO-STOCK/main.py:100, 103, 107-108`
- 现象：3 处 `input()` 无 `try/except EOFError`
- 后果：cron 非交互环境下若 stdin 不是 tty，`input()` 抛 `EOFError` → 整个流水线 traceback 退出
- 证据：当前 cron 用 `printf "2\nstock_pool.csv\n\n" | python3 main.py` 提供 stdin → 不触发；但任何手工 `python main.py < /dev/null` 会崩
- 建议：包 `try/except EOFError`，或支持 `python main.py --code 600519` / `--csv stock_pool.csv` 的 CLI 参数

### [P1] `feedbacks.json` 写入无并发保护、无频率限制
- 位置：`api/main.py:588-622` + `/home/admin/AUTO-STOCK/feedbacks.json`
- 现象：
  ```python
  # L596-615
  feedbacks = []
  if FEEDBACK_FILE.exists():
      with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
          feedbacks = json.load(f)
  feedbacks.append(new_feedback)
  with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
      json.dump(feedbacks, f, ensure_ascii=False, indent=2)
  ```
- 后果：
  - 同一毫秒两个 POST 会**互踩**（read 各自拿到 n 条、write 互相覆盖 → 数据丢失）
  - 单 IP 可 1s 内发 1000 次 → 文件 grow 至 GB（DoS / 磁盘满）
  - feedbacks.json 在 git 跟踪——含真实 IP `183.222.203.200`，**泄漏用户 IP**
- 建议：
  - `fcntl.flock(f, fcntl.LOCK_EX)` 加文件锁
  - nginx `limit_req_zone` 或 Python slowapi
  - 把 feedbacks.json 加进 `.gitignore`，或改用 SQLite / 数据库

### [P2] 日志格式简陋、无轮转
- 位置：`api/main.py:60-68`
- 现象：
  ```python
  logging.basicConfig(
      level=logging.INFO,
      format='%(message)s',            # 没有时间戳、level、模块名
      handlers=[
          logging.FileHandler(LOG_FILE),   # 无 maxBytes
          logging.StreamHandler()
      ]
  )
  ```
- 后果：
  - 排查问题时不知道这条 log 何时产生
  - `logs/access.log` 自 2026-04-14 起累积 212KB，无上限
  - 无 logrotate 配置（`/etc/logrotate.d/` 找不到任何 AUTO-STOCK 条目）
- 建议：format 加时间戳，FileHandler 加 `maxBytes=10MB, backupCount=5`，加 `/etc/logrotate.d/auto-stock`

### [P2] 端口 / host 硬编码散布
- 现象：
  | 文件 | 行 | 内容 |
  |------|----|----|
  | `deploy/stock-api.service` | 12 | `--host 127.0.0.1 --port 8000` |
  | `deploy/stock-system.conf` | 49 | `proxy_pass http://127.0.0.1:8000` |
  | `scripts/start_financial_score.sh` | 22 | `--bind 0.0.0.0:8000` |
  | `scripts/start_financial_score.sh` | 29 | `--host 0.0.0.0 --port 3000` |
  | `scripts/monitor_api.sh` | 5-6 | `API_PORT=8000` `localhost:8000/api/v1/financial/score/600519` |
  | `api/main.py:526` | L526 | `host="0.0.0.0", port=8000` |
- 后果：改端口需改 7+ 处；容易遗漏（已在 CRON.md / 部署子报告发现不一致）
- 建议：抽 `.env` 文件 + `python-dotenv` 读 `API_HOST`、`API_PORT`

### [P2] `pool.py` 过滤逻辑 hardcode 字符串前缀
- 位置：`/home/admin/AUTO-STOCK/pool.py:6`
- 现象：`df[~df["code"].str.startswith(("8", "4","9"))]` —— 过滤北交所/新三板/B 股
- 后果：
  - 沪 B "900xxx"、深 B "200xxx" 都会漏（深 B 不在 "9" 开头）
  - 字符串字面量分散（注释只在 docstring 隐含）
- 建议：
  ```python
  EXCLUDE_PREFIXES = ("4", "8", "9")   # 新三板 / 北交所 / B股(沪B)
  EXCLUDE_PREFIXES_BSE = ("83", "87")  # 北交所细分
  ```
  明确注释 + 写 unit test

### [P2] `meta/` 目录未引用但仍在维护
- 位置：`/home/admin/AUTO-STOCK/meta/`
- 文件：`factor_config_v1.json`、`pool_config_v1.json`、`snapshot_manifest.csv`
- 现象：
  - `factor_config_v1.json` 定义了 9 因子权重，但 `src/factors/*.py` 没读它（权重硬编码在各因子文件）
  - `pool_config_v1.json` 声明 1384 只股票，但 `main.py run_batch` 从 `stock_pool.csv` 读
  - `snapshot_manifest.csv` 5 条记录后停更（最新 20260522）
- 后果：meta 是"事实声明"但与代码脱节——更新代码忘了更新 meta → audit trail 失效
- 建议：
  - 方案 A：让 `src/core/factor_manager.py` 读 `meta/factor_config_v1.json` 权重
  - 方案 B：删掉 meta，改为 `src/factors/` 顶部常量注释
  - `snapshot_manifest.csv` 改由代码生成（CLI 加 `python -m src.tools.snapshot`）

### [P2] 死文件 / 重复文件仍在工作树
- 位置：
  - `scripts/daily_report.py.bak` (45367 字节, 5月18)
  - `scripts/daily_report.py.fix` (45367 字节, 5月18)
  - `api/main.py.bak2` (17213 字节, 4月23)
- 现象：
  - `git ls-files | grep .bak` → 0（git 干净 ✓）
  - 但 `diff daily_report.py.bak daily_report.py.fix` → **完全相同**（45367 == 45367）—— 其中一份可立即删除
  - `api/main.py.bak2` 是 v1，含 hardcoded `MX_APIKEY` —— 若被 tar 打包泄漏
- 建议：
  - `mkdir .archive/ && mv *.bak *.fix *.bak2 .archive/` 隔离
  - 或直接 `rm scripts/daily_report.py.fix api/main.py.bak2`
  - `.gitignore` 加 `*.bak *.fix *.bak2`

### [P2] `src/config.py` 是空文件但 git 跟踪
- 位置：`/home/admin/AUTO-STOCK/src/config.py`
- 现象：`cat src/config.py` → 0 字节（空文件）
- 后果：误导新成员以为有配置可读
- 建议：`rm src/config.py` 或填充内容（统一配置入口）

### [P3] `__pycache__` 工作树累积
- 位置：`api/__pycache__/`、`scripts/__pycache__/`、`config/__pycache__/`
- 现象：约 200KB 编译产物在 working tree
- `.gitignore` 已经忽略 `__pycache__/` ✓——但磁盘占用仍累积
- 建议：`find . -name __pycache__ -exec rm -rf {} \;` 清理脚本加到 README

### [P3] 跨平台：python3 / 绝对路径不可移植
- 现象：
  - 所有 shell 用 `python3`（Windows 默认是 `python`）
  - 所有路径 hardcode `/home/admin/AUTO-STOCK`
  - `deploy/stock-system.conf` 写死 `/home/admin/AUTO-STOCK/web/stock-system/dist`、`/ssl/cert.pem`
- 后果：开发机 Windows / Mac 用户不能本地跑
- 建议：抽环境变量；Python 加 `# -*- coding: utf-8 -*-` + shebang `#!/usr/bin/env python3`

### [P3] `main.py` 单股模式 `name = code`（股票名始终是代码）
- 位置：`main.py:29`
- 现象：`def run_single(code): name = code` —— 股票名默认是代码字符串
- 后果：单股评分时显示"=== 600519 多因子评分系统 ==="而非"=== 600519 贵州茅台 ==="
- 建议：参考 `api/main.py:84-100` 的 `get_stock_name` 读 `stock_full_pool.csv`

### [P3] `pool.py` 写 `stock_full_pool.csv` 用相对路径
- 位置：`pool.py:7`
- 现象：`df.to_csv("stock_full_pool.csv", index=False)`
- 后果：必须从项目根目录跑（cd /home/admin/AUTO-STOCK && python pool.py）
- 建议：用 `Path(__file__).parent.parent / "stock_full_pool.csv"`

## 3. 改进建议（非问题，但有更好做法）

1. **统一配置层**：用 `pydantic.BaseSettings` + `.env` 文件读 `TUSHARE_TOKEN`、`API_HOST`、`API_PORT`、`LOG_LEVEL`——消除魔法数字。
2. **CLI 框架**：`main.py` 加 `argparse`，支持 `python main.py --single 600519`、`python main.py --batch stock_pool.csv --out result.csv`。
3. **日志标准化**：所有 `scripts/*.py` 用同一 `logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s')`；加 logrotate。
4. **secret 扫描**：`scripts/check_secrets.sh` 用 `gitleaks` 或 `trufflehog` 在 CI 跑——阻止新 secret 进 git。
5. **`feedbacks.json` → SQLite**：api/main.py 已经依赖 `src/portfolio/database.py`，feedback 也存同一库——省去并发风险。
6. **meta/ 文档化**：在 CLAUDE.md 解释 meta/ 用途 + 维护规则。
7. **`requirements.txt` 锁版本**：用 `pip freeze > requirements.txt` 或 `pip-compile` 生成完整列表。
8. **CLI 异常处理**：每个 `run_single` 调用 factor.calculate() 时 try/except，让单因子失败不影响整体。

## 4. 需要核实的不确定项

- `daily_data_fetch.py` L13-14 docstring 声称 `0 16` cron，实际 crontab 是 `0 17` —— **有意为之还是笔误**？
- `meta/snapshot_manifest.csv` 5 条记录后无更新（最新 20260522）—— 是已废弃还是有 cron 漏跑？
- `src/config.py` 是有意保留（占位）还是无意中创建的空文件？
- `requirements.txt` 缺 fastapi 是因为用 `systemd` 时 OS 包管理提供？还是漏了？

## 5. 评分（1-5，5 = 优）

- 正确性：2（TUSHARE_TOKEN 暴露 + path traversal + 并发写 feedbacks）
- 可维护性：2（requirements 不全、配置体系空、meta 脱节、bak 堆积）
- 性能：3（无显式瓶颈，但 sleep(0.5) × 1385 是隐性慢）
- 文档：2（meta 失同步、docstring 与 cron 不一致）
- **总评：2**（需多文件协同修复 secret + CLI + 配置）
