# Raw notes: 横向 / Cross-cutting (#9 subagent)

## 1. 配置文件 vs 代码魔法数字

### config/config.py
```python
TUSHARE_TOKEN = "OLD_TUSHARE_TOKEN_REDACTED"
```
- ⚠ **hardcoded secret in git-tracked file**
- ⚠ **完全无人使用**：`grep -rn "TUSHARE_TOKEN\|tushare" --include='*.py' .` 全仓无 import tushare
- ⚠ `src/config.py` 存在但**是空文件**（0 字节）——有命名空间但没内容

### requirements.txt（只有 3 行）
```
akshare>=1.13.99
pandas>=2.0.0
numpy>=1.24.0
```
- ⚠ 缺 fastapi / uvicorn / pydantic / gunicorn（虽然 api/main.py import 了）
- ⚠ 缺 pytest（CLAUDE.md 说可以 `python -m pytest` 但 requirements 没列）
- ⚠ 缺 starlette（FastAPI 依赖）
- ⚠ 缺 pysqlite3（CLAUDE.md 文档里提到 Python 3.11+ 需要，但没列）

### 魔法数字散布
- `api/main.py:526`: `uvicorn.run(app, host="0.0.0.0", port=8000)` — 端口 8000 重复
- `api/main.py:461`: `timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")` — 4 处重复
- `deploy/stock-api.service`: `8000` 端口
- `deploy/stock-system.conf`: `127.0.0.1:8000`
- `scripts/start_financial_score.sh`: 8000, 3000 端口
- `scripts/monitor_api.sh`: `API_PORT=8000`, `API_URL="http://localhost:8000/api/v1/financial/score/600519"` — 600519 硬编码
- `api/main.py:481`: `status_code=500` 通用错误返回
- `api/main.py:633/655/687`: `today_str = datetime.now().strftime("%Y%m%d")` — 重复 3 次

## 2. 日志

### api/main.py L60-69
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',                       # ⚠ 无时间戳
    handlers=[
        logging.FileHandler(LOG_FILE),          # 无 maxBytes
        logging.StreamHandler()
    ]
)
```
- 格式 `%(message)s` 没有时间戳、level、module 信息——排查时极痛苦
- 无 logrotate 配置——`access.log` 自 2026-04-14 起累积 212KB 且无上限

### logs/ 目录
- 105+ 文件，分散命名 `daily_download_*.log`、`daily_fetch_*.log`、`evening_pipeline_*.log`、`future_return_*.log`、`api-stderr.log`、`api-stdout.log`、`gunicorn.log`、`uvicorn.log`
- ⚠ `/tmp/gunicorn.log`、`/tmp/future_return.log`、`/tmp/api.log`、`/tmp/security_scan.log` 等写到 /tmp（不同 cron 任务分散）
- `/tmp/gunicorn.log` 自 5 月起 1KB——5 月 16 后没新内容，说明 start_financial_score.sh 很久没跑（systemd uvicorn 在跑）

### 无统一日志框架
- 没用 `loguru` / `structlog`
- 各脚本各写各的，格式不统一

## 3. 跨平台

### Python 解释器
- `crontab`: `python3` 和 `/usr/bin/python3` 混用
- `scripts/start_financial_score.sh`: `python3`
- `scripts/evening_pipeline.sh`: `python3`
- `scripts/monitor_api.sh`: `python3`
- `deploy/stock-api.service`: `/usr/bin/python3`（绝对路径 ✓）
- ⚠ Windows 没有 `python3`，只有 `python`——无 fallback

### 路径
- 所有脚本 hardcode `/home/admin/AUTO-STOCK`
- `evening_pipeline.sh` L8: `cd /home/admin/AUTO-STOCK`
- `start_financial_score.sh` L7: `cd /home/admin/AUTO-STOCK`
- `deploy/stock-system.conf`: alias `/home/admin/AUTO-STOCK/...`
- ⚠ 完全不可移植——Windows 不能跑，Mac 上路径不存在

### date 命令
- `evening_pipeline.sh`: `$(date +%Y%m%d)` Linux GNU date ✓（macOS BSD date 也支持）
- `daily_data_fetch.py`: `today = datetime.today().strftime("%Y%m%d")` Python ✓

### shell 特性
- `set -euo pipefail` 用了 ✓
- `evening_pipeline.sh` L14: `exec > >(tee -a "$LOG") 2>&1` —— bash process substitution ✓
- Bash 4+ 特性（关联数组、`[[ ]]`）—— `/bin/sh` 调用会失败，但脚本用 `#!/bin/bash` shebang ✓

## 4. 死文件 / .bak / .fix

### git 跟踪状态
- `git ls-files | grep -E '\.bak|\.fix'` → **零结果** ✓（git 干净）
- `git ls-files | grep -E 'config\.py|requirements\.txt|pool\.py|main\.py|api/main\.py'`：
  - `api/main.py` ✓
  - `config/config.py` ✓
  - `main.py` ✓
  - `pool.py` ✓
  - `requirements.txt` ✓
  - `src/config.py` ✓（但空）

### 工作树仍存在
- `scripts/daily_report.py.bak` (45367 字节, 5月18)
- `scripts/daily_report.py.fix` (45367 字节, 5月18)
- `api/main.py.bak2` (17213 字节, 4月23)
- 这三个都是 `daily_report.py` / `api/main.py` 的旧版本（v1）
- ⚠ diff `daily_report.py.bak` 和 `daily_report.py.fix` 完全相同（45367 字节）——其中一份可删除
- ⚠ `api/main.py.bak2` 大小差异（v1 17KB，v2 41KB）——是早期代码，但含 hardcoded MX_APIKEY

### __pycache__
- `api/__pycache__/main.cpython-311.pyc` (65126 字节)
- `scripts/__pycache__/daily_report.cpython-311.pyc` 等 4 个
- `config/__pycache__/config.cpython-312.pyc`
- ⚠ **`.gitignore` 已经忽略 `__pycache__/` ✓**——但工作树存在，体积约 200KB

### meta/ 用途
- `meta/factor_config_v1.json` 9 因子权重定义
- `meta/pool_config_v1.json` 股票池元数据
- `meta/snapshot_manifest.csv` 5 天 snapshot 记录
- ⚠ **未被代码引用**（`grep -rn "meta/" --include='*.py' .` 仅返回 main.py.bak2、api/main.py、CLAUDE.md 等提及）
- 但是审计追溯有用——**保留**

## 5. 前导零风险（08e6abb commit）

### 已修复位置
- `src/analyzer/kline_analyzer.py` 加 `dtype={'code': str}`
- `scripts/calc_signals.py` 加 `dtype={'code': str}`

### ⚠ 未修复位置（同一类问题）
| 位置 | read_csv 缺 dtype |
|------|------------------|
| `api/main.py:38` | `pd.read_csv(STOCK_POOL_FILE)` — 股票池 |
| `api/main.py:91` | `pd.read_csv(pool_file)` — 股票池 |
| `api/main.py:639` | `pd.read_csv(result_file)` — batch_result |
| `api/main.py:670` | `pd.read_csv(result_file)` — batch_result |
| `api/main.py:693` | `pd.read_csv(result_file)` — batch_result |
| `main.py:61` | `df = pd.read_csv(csv_file)` — 批量评分 CSV |

**后果**：
- 深市股票（000xxx）若 CSV 含前导零，pandas 会推断为 int，丢前导零
- 前端 `/api/v1/reports/today`、`/api/v1/reports/top`、`/api/v1/scores/latest` 返回的 code 可能不带前导零
- Vue 前端 `code.padStart(6, '0')` 兜底可能掩盖问题

## 6. CLI main.py 健壮性

### 输入处理
- L100: `mode = input("请输入模式编号: ").strip()` —— **EOF 未处理**
- L103: `code = input(...)` —— 同上
- L107-108: 两次 input —— 同上
- ⚠ 在 cron / 非交互 stdin 下会 `EOFError` traceback
- ⚠ 没有 `if __name__ == "__main__"` 之外的 `--single --code 600519` CLI 参数

### run_batch 风险
- L87-90: `in_fname` 直接拼到 filename —— **path traversal**（`../../foo` 或 `/tmp/x`）
- L91: `result_df.to_csv(filename, index=False)` —— **静默覆盖**同名文件
- L70: `time.sleep(0.5)` —— 1385 只股票 × 0.5s = ~12 分钟 sleep（即使 AKShare 缓存命中）
- L57: `os.path.exists(csv_file)` ✓ 但 pd.read_csv(csv_file) 失败 → **未捕获**
- L63: `"code" not in df.columns` 检查 ✓

### pool.py
- L6: `df[~df["code"].str.startswith(("8","4","9"))]` —— **魔法前缀字符串**
- ⚠ "8" 是北交所，"4" 是新三板，"9" 是 B 股——但 B 股部分用 "9" 开头不规范（沪 B "900xxx"、深 B "200xxx"）
- L7: 写到 `stock_full_pool.csv` —— **相对路径硬编码**，必须从项目根跑

## 7. TUSHARE_TOKEN & 其他 secrets

### 已 commit 的 secret
- `config/config.py:2` `TUSHARE_TOKEN = "OLD_TUSHARE_TOKEN_REDACTED"` —— 真实 token
- `git log` 验证：commit `d6572ab` 之前已存在

### bak/fix 中的 secret
- `scripts/daily_report.py.bak` L?: `os.environ.get('MX_APIKEY', 'mkt_65LysqK_vB294d8JkHEvwazCMpoMSfdWJFC0Ia1mYuo')`
- `scripts/daily_report.py.fix` L?: 同上
- ⚠ **不在 git**（`git ls-files` 验证）——但本地磁盘上有，万一被 tar/zip 打包泄漏

### 其他可能泄漏
- `feedbacks.json` 含真实 IP `183.222.203.200`（git 跟踪）

## 8. CRON 不一致汇总

| CRON.md 声称 | 实际 crontab | 一致? |
|--------------|--------------|-------|
| 17:00 daily_download.sh | 17:00 daily_data_fetch.py | ❌ 脚本名错（CRON.md 列了不存在的 .sh） |
| 18:00 daily_future_return.sh | 18:00 daily_future_return.sh | ✓ |
| 19:00 evening_pipeline.sh | 19:00 evening_pipeline.sh | ✓ |
| 错误通知机制 | 无（无 MAILTO） | ❌ |
| 日志路径 `logs/evening_pipeline_YYYYMMDD.log` | 实际 `logs/evening_pipeline.log` + 脚本内部又写 `logs/evening_pipeline_${DATE}_${HMS}.log` | ⚠ 双日志 |

## 9. systemd vs start_financial_score.sh 双服务冲突

- systemd `stock-api.service` 用 uvicorn 监听 `127.0.0.1:8000`
- `start_financial_score.sh` 用 gunicorn 监听 `0.0.0.0:8000`
- `stop_financial_score.sh` 杀 gunicorn，但**不杀 uvicorn**
- `monitor_api.sh` 只查 gunicorn，但**实际是 uvicorn 在跑**——监控会误判健康
- ⚠ 双系统并存、互不知情——P1 操作风险

## 10. 其他发现

### api/main.py 路由注释不一致
- L707: "修复 6.1: 暴露 portfolio 端点" —— 是 handover note 残留
- L1021: "信号 API（修复 6.1 配套）" —— 同
- L704: "持仓管理 API" section
- ⚠ 注释里的"修复 6.1"指代不明——可清理

### 双 FastAPI app
- L19: `app = FastAPI(title="财报评分API", version="1.0.0")` 单实例
- ✓ 但 L22 `startup_event` 每次启动 load_stock_pool——若 `stock_full_pool.csv` 更新**必须重启**服务才能生效

### `__pycache__` 进 git？
- `git status` 显示一堆 `__pycache__` 变更——**但 .gitignore 已忽略**——所以是本地未跟踪变更（不影响 git）

### sim_trader.py（CRON.md 没提）
- `scripts/sim_trader.py` 在 evening_pipeline.sh L75-81 被调用
- CRON.md 步骤说明**完全没提**——文档缺失

### self-reference 文件
- `scripts/evening_pipeline.sh` L57 `printf "2\nstock_pool.csv\n\n" | python3 main.py` —— **依赖 cwd 是项目根**——cron 用 `cd /home/admin/AUTO-STOCK &&` ✓ 但手动跑不 cd 会失败
