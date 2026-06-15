# Raw notes: Cron / Deploy / API (#9 subagent)

## A. CRON vs reality

### Actual crontab -l (output)
```
0 17 * * 1-5 cd /home/admin/AUTO-STOCK && /usr/bin/python3 scripts/daily_data_fetch.py
0 3 * * * /home/admin/.openclaw/workspace/scripts/security_scan.sh >> /tmp/security_scan.log 2>&1
0 22 * * * /home/admin/.openclaw/workspace/scripts/daily_ip_report.sh >> /tmp/ip_report.log 2>&1
*/5 * * * * cd /home/admin/.openclaw/workspace/skills/sleep_skill/scripts && python3 sleep_cycle.py >> /tmp/sleep_cycle.log 2>&1
5 7 * * * /home/admin/.openclaw/workspace/scripts/sleep_report.sh >> /tmp/sleep_report.log 2>&1
0 3 * * * python3 /home/admin/scripts/r2_backup.py >> /home/admin/logs/r2-backup.log 2>&1
0 18 * * 1-5 cd /home/admin/AUTO-STOCK && bash scripts/daily_future_return.sh >> /tmp/future_return.log 2>&1
0 19 * * 1-5 bash /home/admin/AUTO-STOCK/scripts/evening_pipeline.sh >> /home/admin/AUTO-STOCK/logs/evening_pipeline.log 2>&1
0 3 1,16 * * rm -rf /home/admin/.openclaw/workspace/.trash/* && echo "$(date): trash cleaned" >> /home/admin/.openclaw/workspace/.trash/clean.log
45 22 * * * /bin/bash /home/admin/.openclaw/workspace/scripts/daily_briefing.sh >> /tmp/daily_briefing.log 2>&1
0 */2 * * * /bin/bash /home/admin/.openclaw/workspace/scripts/browse_forum.sh >> /tmp/browse_forum.log 2>&1
```

AUTO-STOCK 相关 cron（筛掉 5 个 openclaw/sleep/r2 行）：
1. `0 17 * * 1-5 cd /home/admin/AUTO-STOCK && /usr/bin/python3 scripts/daily_data_fetch.py`
2. `0 18 * * 1-5 cd /home/admin/AUTO-STOCK && bash scripts/daily_future_return.sh`
3. `0 19 * * 1-5 bash /home/admin/AUTO-STOCK/scripts/evening_pipeline.sh >> /home/admin/AUTO-STOCK/logs/evening_pipeline.log 2>&1`

### CRON.md 声称：
| 时间 | 任务 | 脚本 | 说明 |
|------|------|------|------|
| 17:00 | daily_download.sh | ❌ 脚本不存在 (`ls scripts/daily_download.sh` No such file) |
| 18:00 | daily_future_return.sh | ✓ 存在 |
| 19:00 | evening_pipeline.sh | ✓ 存在 |

### 不一致项
- CRON.md 第 11 行：`17:00 scripts/daily_download.sh` —— 实际 crontab 调的是 `scripts/daily_data_fetch.py`（不是 `.sh`）。脚本和路径都不匹配。
- CRON.md 没有列出任何"错误通知"机制——所有 cron 失败只会重定向到日志，没有 mailto 或 webhook。
- `daily_data_fetch.py` docstring（第 13-14 行）声称："定时任务（每天16:00执行）：`0 16 * * 1-5`"，与实际 cron（17:00）也不一致——docstring 误导。

### 工作目录 / 日志输出核对
- 17:00 任务：`cd /home/admin/AUTO-STOCK && /usr/bin/python3 scripts/daily_data_fetch.py` — 显式 cd，✓。但 cron 行 **没有重定向 stdout/stderr**（脚本本身写 logs/daily_fetch_YYYYMMDD.log，所以 stdout 进黑洞无影响）。
- 18:00 任务：`cd /home/admin/AUTO-STOCK && bash scripts/daily_future_return.sh >> /tmp/future_return.log 2>&1` — ✓。但日志写到 /tmp/ 而非项目 logs/，分散。
- 19:00 任务：✓ 写 `logs/evening_pipeline.log`，但脚本本身又写带时间戳的 `logs/evening_pipeline_${DATE}_${HMS}.log`——同一个流水线产生 2 份日志，不一致。

### 错误通知
- 没有任何 cron 行的 MAILTO，或 webhook 通知。失败只能靠人工查 log 发现。
- step 失败时 `evening_pipeline.sh` 会 `exit 1`，但 cron 不会把这个 exit 当成 mailto 触发。

## B. API

### FastAPI 路由
文件 `/home/admin/AUTO-STOCK/api/main.py`（1150 行）：
- `GET /`（index_simple.html fallback）
- `GET /index.html`
- `GET /api/v1/stock/search?q=&limit=10`
- `GET /api/v1/financial/score/{code}`
- `GET /api/v1/financial/detail/{code}`
- `GET /api/v1/financial/kline/{code}?quarter=`
- `POST /api/v1/feedback`
- `GET /api/v1/reports/search?q=`
- `GET /api/v1/reports/today`
- `GET /api/v1/reports/top?n=`
- `GET /api/v1/portfolio/account`
- `GET /api/v1/portfolio/positions`
- `GET /api/v1/portfolio/trades?limit=`
- `GET /api/v1/portfolio/stats`
- `POST /api/v1/portfolio/buy` ⚠ 无 auth
- `POST /api/v1/portfolio/sell` ⚠ 无 auth
- `POST /api/v1/portfolio/update-prices`
- `GET /api/v1/portfolio/nav`
- `POST /api/v1/portfolio/snapshot`
- `POST /api/v1/portfolio/dividend`
- `POST /api/v1/portfolio/update-capital` ⚠（修改初始资金/重置账户）
- `POST /api/v1/portfolio/delete-trade`
- `GET/POST/PUT/DELETE /api/v1/strategies` ⚠（增删策略）
- `GET /api/v1/portfolio/strategy`
- `POST /api/v1/portfolio/strategy`
- `GET /api/v1/backtest/top`
- `GET /api/v1/signals/latest`
- `GET /api/v1/scores/latest`

### 认证 / CORS
- 没有任何认证（grep "auth|jwt|HTTPBearer|Authorization" 零结果）。
- CORS (L47-53):
  ```python
  app.add_middleware(CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,    # ⚠ 与 origins="*" 组合违反 Starlette 规范
      allow_methods=["*"],
      allow_headers=["*"])
  ```
  FastAPI/Starlette 在 `allow_origins=["*"] + allow_credentials=True` 时启动会报 "Invalid args"——可能因 starlette 版本未检测到，但属不安全配置：CSRF 风险 + 任意源可读 cookie。
- systemD unit 用 `--host 127.0.0.1` 实际只本机可访问 ✓（但 `if __name__ == "__main__"` fallback 用 `0.0.0.0` ⚠——直接 `python3 api/main.py` 会全网暴露，且与 start_financial_score.sh 用 gunicorn `--bind 0.0.0.0:8000` 不一致，端口冲突）。

### hardcoded secrets
- `config/config.py:2` `TUSHARE_TOKEN = "OLD_TUSHARE_TOKEN_REDACTED"` — 已 **commit 到 git**（git ls-files 确认）。
- `scripts/daily_report.py.fix` 和 `daily_report.py.bak` 都有 `os.environ.get('MX_APIKEY', 'mkt_65LysqK_…')` —— **bak/fix 未被 git 跟踪**，但若有人 git checkout 旧版本会泄漏。
- 实测 `grep -rn tushare --include='*.py'`：**没有任何文件 import tushare 或读取 TUSHARE_TOKEN**。token 是死代码，但 git 历史保留——P1 安全风险。

### 端口绑定 / 进程管理
- systemd: `uvicorn --host 127.0.0.1 --port 8000 --workers 1` ✓（只本机）
- `start_financial_score.sh:22` `gunicorn --bind 0.0.0.0:8000` ⚠——绑定 0.0.0.0，又与 systemd 抢 8000 端口（实际 systemd 在跑，所以 gunicorn 起不来，详见下）。
- 当前实际：`ps aux` 显示 systemd uvicorn 在跑（pid 1436084），`ss -tlnp | grep :8000` 仅显示 127.0.0.1:8000 ✓（未启动 gunicorn——并存方式冲突）。
- 端口冲突会"看起来启动成功"，但 systemd 进程被 kill 后 `start_financial_score.sh` 的 gunicorn 才生效，但 systemctl restart stock-api.service 会再把它顶下去。**两套服务互相争抢**。

### 错误处理
- 每个路由都有 `try/except Exception` → JSONResponse(500) ✓。
- 但 access.log 第 481-483 行：`return JSONResponse(status_code=500, content={"error": str(e), "code": ...})` —— 把原始异常 str(e) 直接返回给客户端 ⚠（可能泄漏 stack trace / 内部路径）。

### Feedback 端点（`/api/v1/feedback`）
- 任意 POST 可写入 `feedbacks.json`，无验证码、无频率限制 ⚠——可被滥用做存储注入（json 文件 grow 无界）。
- 当前文件只有 1 条记录（真实 IP `183.222.203.200` 已写入 feedbacks.json.json）——这条 IP 看起来是用户自己测试。但**没有节流/鉴权**，未来若对外暴露就是 spam 入口。

## C. 部署脚本

### `deploy/deploy_stock_system.sh`（117 行）
- `set -euo pipefail` ✓
- 检查 EUID==0 ✓
- 备份现有 nginx 配置 `auto-claw.top.conf.bak.YYYYMMDD` ✓
- 用 `cp $NGINX_CONF_SRC $NGINX_CONF_DST` 后立即 `nginx -t` ✓
- 然后 `systemctl daemon-reload; enable; restart stock-api.service` ✓
- 健康检查：`curl 127.0.0.1:8000/api/v1/portfolio/account` ✓
- DNS 解析检查 `stock.auto-claw.top` ✓（带 10s 超时）

问题：
- 第 84 行：`--max-time 5` 后若 fail 还返回 0（`-f`），用 `|| echo "..."` 兜底。但没把失败告警送出去——只能看屏幕。
- 第 28-29 行：备份命名 `auto-claw.top.conf.bak.$(date +%Y%m%d)`，同一日多次跑会**覆盖**（应该用秒或 PID 区分）——P2。
- 第 39 行：同样 .bak.YYYYMMDD 覆盖。
- 没显示"如果 stock-api 在 systemd 跑 vs start_financial_score.sh 的 gunicorn 冲突"——这两个是双系统并存，**部署完没告知"再用 start 脚本会冲突"**。

### `deploy/stock-api.service`（systemd unit）
- `ExecStart=/usr/bin/python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1 --log-level info` ✓
- `Restart=always` ✓，`RestartSec=5` ✓
- `User=admin` (非 root) ✓
- `StandardOutput=append:` — 用 `append:` 是 systemd 234+ 特性，注意升级兼容性
- **没有 `NoNewPrivileges`、`PrivateTmp`、`ProtectSystem`** 等 hardening 选项——P2 安全

### `deploy/stock-system.conf`（nginx 110 行）
安全：
- SSL 证书 `/ssl/cert.pem` (通配符 *.auto-claw.top) ✓
- `ssl_protocols TLSv1.2 TLSv1.3` ✓
- HSTS, X-Frame-Options, X-Content-Type-Options ✓
- `location ~* \.(py|log|sql|sqlite|sqlite3|bak|env|ini|conf|cfg)$ { deny all; }` ✓ 防止代码/配置外泄
- `location ~* /data/.*\.db$ { deny all; }` ✓ 防止 SQLite 库外泄
- `location ~ /\.(git|svn|...)` ✓
- `location ~* /(bak|backup|__pycache__)/` ✓
- 前端 `try_files $uri $uri/ /index.html` ✓ Vue Router history

问题：
- `auto-claw.conf` vs `stock-system.conf`：stock-api 在 stock-system.conf 部署，但 start_financial_score.sh 在 auto-claw.conf 部署——**两套** nginx 配置共存，分散。
- `proxy_pass http://127.0.0.1:8000` 没有 timeout 设置（默认 60s）——长任务可能堆积 worker。
- `location /api/` 没有限制请求体大小（可能导致 DoS via 大 JSON）。

### `scripts/start_financial_score.sh`（48 行）
问题：
- L22 `gunicorn --bind 0.0.0.0:8000` ⚠ — **0.0.0.0 + 8000**（systemd 在 127.0.0.1:8000）——端口冲突。
- L29 `vite --host 0.0.0.0 --port 3000` ⚠ — 前端 3000 端口 0.0.0.0 监听。
- L34 `sudo rm -f /etc/nginx/conf.d/auto-claw.conf` ⚠ — 静默删除 nginx 配置（即使不存在也无害，但破坏性 + 需 sudo）。
- L48 `ps aux | grep ...` 没有任何 PID 文件记录——启动后无法用 pid 找进程，下次起停全靠 `pkill -f` 模式匹配（脆弱：任何命令行包含 `gunicorn api.main` 字符串都会被 kill）。
- L12-20 的 "等待旧进程退出" 循环最多 5 次后**直接 break 不报错**——如果 gunicorn 5 秒还没退出，脚本继续，可能 race condition。
- `cd /home/admin/AUTO-STOCK/web/financial-report` 然后 `nohup node node_modules/.bin/vite` 假设 node_modules 已安装——冷部署可能找不到 vite。

### `scripts/stop_financial_score.sh`（57 行）
- pkill 同上，**没有 PID 文件**——只能 pattern match。
- L17-46 `sudo tee /etc/nginx/conf.d/auto-claw.conf << EOF` ⚠——把硬编码的 nginx 配置写入 system dir，且默认 503 所有 `/api/`——但 **没有保护 auto-claw.top.conf 已存在的服务**（用 `tee` 而不是 `cp` + 备份）。
- 没有任何"if process not running, no-op" 处理——pkill exit 1 被吞掉（`pkill ... 2>/dev/null`）✓

### `scripts/monitor_api.sh`（41 行）
- 健康检查 URL hardcode `600519`（茅台）——L6。这是"通过财务评分接口判断 API 健康"——但若 600519 数据出问题会误判 API 挂掉。
- 写到 `/tmp/api.log` 而不是 `/home/admin/AUTO-STOCK/logs/api_monitor.log`（L4 定义的 LOG_FILE 没用上，实际写 `/tmp/api.log` L22）⚠——日志位置 bug。
- 没有任何 crontab 配置调用 monitor_api.sh——**监控脚本从未自动运行**。需要手动或写 cron。

### `scripts/sync_repo.sh`（30 行）
- `git fetch origin --prune` ✓
- `git checkout ${BRANCH} 2>/dev/null || git checkout -b ${BRANCH} origin/${BRANCH}` ✓
- `git pull --ff-only origin ${BRANCH}` ✓ fast-forward only——若远端有 force-push 或本地有冲突会被拒绝 ✓（P2 安全特性）
- 但：
  - L17 `git fetch --prune` 会**删除本地不再有的远端分支 ref**——如果维护脚本依赖这些 ref 会丢数据。
  - L26-27 在远端没有指定分支时回退到 `origin/main`——静默回退，**日志里只有一行 `⚠️`**——易忽略。
  - 没有 `git status` 干净检查：若本地有 uncommitted，pull --ff-only 会**被拒绝但脚本不会退出非零**（因为 `2>/dev/null` 吞掉错误）——P1 操作风险：本地工作树被破坏。
  - `--ff-only` 不能 merge，意味着若远端是 merge commit，本地会被卡住。

## D. CLI / main.py

`main.py:95-115`：
```python
def main():
    print("选择模式:")
    print("1. 单股评分")
    print("2. 批量评分")
    mode = input("请输入模式编号: ").strip()
    if mode == "1":
        code = input("请输入股票代码: ").strip()
        run_single(str(code))
    elif mode == "2":
        in_file = input("请输入股票池CSV路径:").strip()
        in_fname = input("请输入结果名:").strip()
        run_batch(in_file,in_fname)
    else:
        print("无效输入")
```

`run_batch`：
- L57-60：`os.path.exists(csv_file)` 检查 ✓
- L63-65：检查 `code` 列 ✓
- L69：`zip(df["code"], df["name"])` —— 若 `df["name"]` 长度不等 → zip 截断
- L73-75：跳过无效代码 ✓
- L82-91：写到 `./result/daily_score/{batch_result_YYYYMMDD.csv | in_fname.csv}`
  - ⚠ **`in_fname` 是用户 input 字符串**——直接拼到文件名！若用户输入 `../../etc/passwd` 或 `/tmp/x` → **任意路径写入**（path traversal 写入）
  - ⚠ 文件存在会**静默覆盖**
  - 无 `--dry-run` / 无确认
- L88：`datetime.today()` 用于文件名（午夜边界可能写入前一天）
- L100：`input("请输入模式编号: ").strip()` 没有 EOF 处理——若 stdin EOF（cron 非交互）→ EOFError **未捕获** → traceback

`run_single`：
- L29：`name = code`（默认股票名 = 代码）
- L33：`load_factors()` —— 每次都重新加载（无缓存），慢
- 无 try/except 包裹 factor.calculate() —— 单个因子失败会中断整个

`pool.py`：
- L5：`df[~df["code"].str.startswith(("8","4","9"))]` —— 过滤北交所/新三板/B 股 ✓
- L7：写到 `stock_full_pool.csv`（cwd）—— **相对路径硬编码**——必须从 /home/admin/AUTO-STOCK 跑

## E. 横向

### 死文件 / bak 跟踪
- `git ls-files | grep -E '\.bak|\.fix'` → **零结果** ✓（git 没跟踪 .bak/.fix）
- 但 .bak/.fix 仍在工作树，体积：
  - `scripts/daily_report.py.bak` (45367 字节)
  - `scripts/daily_report.py.fix` (45367 字节)
  - `api/main.py.bak2` (17213 字节)
- 推荐清理或移到 `.archive/`

### 重复文件（main.py 和 main.py.bak2）
- `api/main.py.bak2` 是 `api/main.py` 的早期版本（v1）——`git ls-files api/` 只有 `api/main.py`（.bak2 不在 git）✓。
- 但 `api/main.py` v2 有 `stock_pool` 全局变量（line 32），`startup_event` 在每次启动加载——但**修改 stock_pool 的代码没有 reload 机制**——改 CSV 后必须重启 API。

### 前导零风险扩散
commit `08e6abb` 修复了 `kline_analyzer.py`，但还有很多处没修：
- `api/main.py:38` `pd.read_csv(STOCK_POOL_FILE)` —— 加载股票池，无 `dtype={'code': str}`
- `api/main.py:91` `pd.read_csv(pool_file)` —— 同上
- `api/main.py:639` `pd.read_csv(result_file)` —— `batch_result_YYYYMMDD.csv` 加载，无 dtype
- `api/main.py:670` `pd.read_csv(result_file)` —— 同上
- `api/main.py:693` `pd.read_csv(result_file)` —— 同上
- `main.py:61` `df = pd.read_csv(csv_file)` —— 批量评分 CSV，无 dtype
- `scripts/daily_data_fetch.py` 等多处 —— 但这些是间接

⚠ 任何 000xxx 股票（深市）在这些路由可能返回 `1` 而不是 `000001`。

### 配置文件 vs 魔法数字
- `config/config.py` 只有一个 `TUSHARE_TOKEN`，**实际无人 import**——死配置。
- 大量魔法数字：
  - `api/main.py` L481: `status_code=500`
  - `deploy/stock-system.conf`: SSL certs path `/ssl/cert.pem` hardcoded
  - `api/main.py` L526 / L461 fallback: `host="0.0.0.0", port=8000`
  - `start_financial_score.sh`: port 8000, 3000
  - `monitor_api.sh`: hardcode 600519 / port 8000
  - `calc_signals.py` 隐含阈值（30 分）在另一文件

### 日志级别 / 格式 / 轮转
- `api/main.py` L61-68: `logging.basicConfig(level=INFO, format='%(message)s')` —— **没有时间戳格式**——日志只有消息。
- `logs/access.log` 212 KB（自 2026-04-14 起）—— 没有 logrotate 配置（`/etc/logrotate.d/` 找不到），可能无限增长。
- `logs/api-stderr.log` 18 KB —— 同样的无格式问题。
- 没有 `MaxBytes`/`backupCount` 配置。

### 跨平台
- 所有脚本 hardcode `python3`（无 fallback 到 `python`）——Windows 默认是 `python`。
- `/usr/bin/python3` 在 start_financial_score.sh cron 行，但脚本内是 `python3`——PATH 依赖不同。
- 路径全 Unix 风格——Windows 上 `/home/admin/AUTO-STOCK` 全不可用。
- `data/daily_market/${TARGET_DATE}.csv` 用 `${TARGET_DATE}` 由 `date +%Y%m%d` 决定——macOS `date` 没有 `%Y%m%d` 但 Linux 有——脚本只在 Linux cron 跑 ✓（但开发机 macOS 用户不能跑）。

### meta/ 用途
- `meta/factor_config_v1.json`: 9 因子版本号元数据
- `meta/pool_config_v1.json`: 股票池元数据
- `meta/snapshot_manifest.csv`: 每日 snapshot 清单
- **未被代码引用**（`grep -rn "meta/" --include='*.py' src/ scripts/ api/ main.py` → 仅 snapshot_manifest.csv 同名但路径不同）——可能是死的，但作为 audit trail 有保留价值。

### feedbacks.json
- 仅 1 条记录，IP `183.222.203.200` —— 用户自己测试
- 写入是 fire-and-forget JSON dump——并发 POST 可能 race condition（同时 open 文件、同时 dump → 丢更新）
- `FEEDBACK_FILE` 在 project root `/home/admin/AUTO-STOCK/feedbacks.json`（git 跟踪）
