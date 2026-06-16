# 08-cron-deploy 草稿笔记

> 审查时间：2026-06-16
> 范围：deploy/, CRON.md, MAINTENANCE.md, scripts/{start,stop,monitor,sync}_*, api/main.py (auth/err), /etc/systemd/system/stock-api.service, /etc/nginx/conf.d/{stock-system,auto-claw.top}.conf, crontab -l, ps/ss 现场, .env, .trash/

## A. 上次 P0 状态

### S4 双服务端口冲突 — **已修**
- `ps aux | grep -E "gunicorn|uvicorn"`：只剩 1 个 uvicorn 进程 (pid 1900978)
- `ss -tlnp | grep :8000` → `127.0.0.1:8000` 单一监听
- gunicorn 进程已不再运行（start_financial_score.sh 启动的 gunicorn 已废）
- 但 `scripts/start_financial_score.sh:22` 仍写 `gunicorn ... --bind 0.0.0.0:8000`（死代码，但被文档/MANUAL 引用）

### S6 死文件 bak/ — **部分修**
- `result/bak/`（旧 src/result/bak）已删除
- `result/daily_score/bak/` 仍存在（12 个 CSV，2026-05-24 时间戳）
- 上次审查标记的是 `src/result/bak/*` 14 个文件已移到 `.trash/src_result_bak_20260616/`
- 但 `result/daily_score/bak/*`（12 个 test/old batch_result 文件）**未清理**

### API 无认证 — **已修**
- `api/security.py` 实现单密码 + 24h in-memory token
- `api/main.py` 11 个写端点加 `Depends(verify_token)` (lines 824, 841, 857, 880, 890, 915, 925, 978, 996, 1007, 1027)
- 公开端点：所有 GET + POST /api/v1/feedback
- 新增 POST /api/v1/auth/login
- 实测：`curl -X POST http://127.0.0.1:8000/api/v1/portfolio/buy` → **401**
- 实测：错密码 → `{"detail":"密码错误"}`
- 配置文件：`config/config.py` 改从 .env 读，`.env` (600 perm) 含 TUSHARE_TOKEN / API_PASSWORD

### TUSHARE_TOKEN 泄漏 — **已修**
- `config/config.py` 现 `_require_env("TUSHARE_TOKEN")` 从 .env 读
- `.env` 文件 `600 admin admin` 权限正确
- 提交 8b938f2: git filter-repo 替换历史
- 提交 3db04c0: 已轮换 tushare token
- `.git.backup-before-filter-repo/` 是 filter-repo 前的备份，仍在工作树
- **风险**：`.env` 已在 .gitignore，但 `.git.backup-before-filter-repo/` 本身包含完整 git repo（filter-repo 前的全部历史）—— 万一这个目录被 push 出去，旧密钥仍可读

## B. 新部署文件

### deploy/deploy_stock_system.sh (117 行)
- 检查 root 权限（`EUID -ne 0` → exit 1）
- 步骤 0: 备份 `/etc/nginx/conf.d/auto-claw.top.conf` → `.bak.$(date +%Y%m%d)`
- 步骤 1: 复制 `deploy/stock-system.conf` → `/etc/nginx/conf.d/stock-system.conf`（若已存在 → 备份）
- 步骤 2: `nginx -t`
- 步骤 3: 复制 systemd unit + mkdir logs/
- 步骤 4: `systemctl daemon-reload && enable && restart stock-api.service`，检查 is-active
- 步骤 5: `systemctl reload nginx`
- 步骤 6: 健康检查 `curl http://127.0.0.1:8000/api/v1/portfolio/account`
- 步骤 7: DNS 解析 + HTTPS 响应检查
- **和 start_financial_score.sh 关系**：完全替代。start_financial_score.sh 启动 gunicorn（已废）；新脚本启 systemd uvicorn。

### deploy/stock-system.conf (111 行)
- 监听 80 (301 → HTTPS) + 443 ssl
- 用 `*.auto-claw.top` 通配符证书（Cloudflare Origin）
- 安全头：X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, HSTS, Referrer-Policy
- 前端：root `web/stock-system/dist/`，try_files vue router
- 静态资源缓存 7d
- `/api/` → `http://127.0.0.1:8000`（无超时配置）
- `/data/signals/`, `/data/daily_score/`, `/data/price/`, `/data/score_price_history.csv` 静态别名
- **敏感文件屏蔽**：`.db$`, `.py|.log|.sql|.sqlite|.bak|.env|.ini|.conf|.cfg`, `.git|.svn|.hg`, `/bak/|/backup/|/__pycache__/`, `/data/$`
- **无 CORS 配置**（继承 auto-claw.top.conf 父级或无 — FastAPI 自身 CORS）
- **无 IP 白名单**
- **无 rate-limit**（继承 auto-claw.top.conf？需查）
- **无 HSTS preload**

## C. 新进程管理

### deploy/stock-api.service
- Type=simple, User=admin, Group=admin
- WorkingDirectory=/home/admin/AUTO-STOCK
- Environment: PYTHONUNBUFFERED=1, PATH
- **EnvironmentFile=-/home/admin/AUTO-STOCK/.env**（`-` 前缀 → 文件缺失不报错）
- ExecStart: `uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1 --log-level info`
- Restart=always, RestartSec=5
- StandardOutput/Error → `logs/api-stdout.log` / `logs/api-stderr.log`
- **缺 hardening**：NoNewPrivileges, PrivateTmp, ProtectSystem, ReadWritePaths, MemoryMax
- 单 worker

### /etc/systemd/system/stock-api.service (live)
- Read 失败（权限被拒），但可由 deploy 脚本复制推断
- uvicorn 进程 pid 1900978 在 08:32 启动，**与 latest result 8:25 close 之后**（流水线 19:00 跑 → 评分完 8:32 启动合理）
- 0:0.0.0:8766 也有 python 进程在跑（report_api / stock_web.py 的 Flask 服务）

### pgrep 结果
- 1 个 uvicorn (pid 1900978)
- 1 个 python3 on :8766 (pid 1888060)
- 0 个 gunicorn
- 0 个 vite

## D. cron 现状

```
0 17 * * 1-5 cd /home/admin/AUTO-STOCK && /usr/bin/python3 scripts/daily_data_fetch.py
0 3 * * * /home/admin/.openclaw/workspace/scripts/security_scan.sh
0 22 * * * /home/admin/.openclaw/workspace/scripts/daily_ip_report.sh
*/5 * * * * /home/admin/.openclaw/workspace/skills/sleep_skill/scripts
5 7 * * * /home/admin/.openclaw/workspace/scripts/sleep_report.sh
0 3 * * * python3 /home/admin/scripts/r2_backup.py
0 18 * * 1-5 cd /home/admin/AUTO-STOCK && bash scripts/daily_future_return.sh
0 19 * * 1-5 bash /home/admin/AUTO-STOCK/scripts/evening_pipeline.sh
0 3 1,16 * * rm -rf /home/admin/.openclaw/workspace/.trash/*
45 22 * * * /home/admin/.openclaw/workspace/scripts/daily_briefing.sh
0 */2 * * * /home/admin/.openclaw/workspace/scripts/browse_forum.sh
```

**全部命中 A 的核对：**
- 17:00 → `daily_data_fetch.py`（**非** CRON.md 写的 `daily_download.sh`）— P0 漂移未修
- 18:00 → `daily_future_return.sh`（与 CRON.md 一致）
- 19:00 → `evening_pipeline.sh`（与 CRON.md 一致）
- 19:30 → `calc_signals.py` **不在 cron**（CRON.md/MAINTENANCE.md 提到但没调度）
- 监控：`monitor_api.sh` **不在 cron**（仍是 P2）
- 维护：`/etc/nginx/conf.d/auto-claw.conf.bak`（不是清理，是备份）

## E. 监控

- `monitor_api.sh:6` URL: `http://localhost:8000/api/v1/financial/score/600519` （仍 hardcode 600519）
- `monitor_api.sh:17` kill: `pkill -f "gunicorn.*api.main"` （杀 gunicorn，但**实际跑 uvicorn** — 监控完全失效）
- `monitor_api.sh:22` start: `gunicorn ...`（启动 gunicorn 会失败，因为 systemd uvicorn 占着 8000）
- **`api_monitor.log` 最后一条 2026-04-24**，至今没再跑（不在 cron）
- 结论：监控脚本实质上是**僵尸**（已存在但永不被调用）

## F. 安全

### API
- 写端点：已加 verify_token ✅
- GET 端点：无认证（设计为公开，OK）
- `feedback` 端点：公开（无 rate limit）
- 错误响应：仍 `return JSONResponse({"error": str(e)})`（P0 未修）
- CORS：`allow_origins=["*"] + allow_credentials=True`（P1 未修）
  - 实测：Origin: https://evil.com → 返回 `Access-Control-Allow-Origin: https://evil.com` + `Access-Control-Allow-Credentials: true`

### nginx
- 无 IP 白名单
- CORS 不在 nginx 层（API 自管）
- HTTPS 配齐（用通配符证书）
- HSTS：`max-age=31536000; includeSubDomains`（无 preload）

### 文件权限
- `.env` 600 admin:admin ✅
- `data/portfolio.db` **644 admin:admin** ⚠️ 全员可读
- `feedbacks.json` **664 admin:admin** ⚠️ 全员可写
- `.trash/2026-06-15/src_data_fetcher.py` 0 字节（占位符，正常）
- `.git.backup-before-filter-repo/` 在工作树但未 commit，**但若 push 会带出旧密钥历史**

## G. 其他发现

### CRON.md
- L11: `scripts/daily_download.sh` 引用不存在（实际 `daily_data_fetch.py`）
- L141: `Gunicorn` 日志位置 `/tmp/gunicorn.log`（gunicorn 已停）

### MAINTENANCE.md
- L114: 同样 `scripts/daily_download.sh` 死引用
- L117: 19:30 calc_signals.py 提到但实际不在 cron
- L132: 启动命令 `start_financial_score.sh` 仍推荐 gunicorn

### scripts/sync_repo.sh
- 静默回退 main 未修（上次 P1）
- 仍 `git checkout main` 强制覆盖本地

### .trash 保留
- `.trash/2026-06-15/` 内 11+ 个旧 bak/backup 文件（api_main.py.bak2, daily_report.py.bak, batch_result_20260521.csv.bak 等）
- 实际上 1 个 `data_industry_backup_20260615_132319/` 133 个 CSV（重建恢复用，OK）
- 1 个 `src_result_bak_20260616/` 10 个 CSV（清理 src/result/bak 时备份）
- `.trash/2026-06-15/MANIFEST.md` 有清单

## H. 上次未修问题逐项状态

| ID | 上次级别 | 标题 | 状态 |
|----|---------|------|------|
| P0#1 | P0 | API 无认证 | ✅ 已修 (commit 3db04c0) |
| P0#2 | P0 | systemd vs gunicorn 双轨 | ✅ 已修 (gunicorn 已停) |
| P0#3 | P0 | CRON.md 引用 daily_download.sh | ❌ 未修 (CRON.md L11 + MAINTENANCE.md L114) |
| P0#4 | P0 | API 错误响应 str(e) 泄漏 | ❌ 未修 (api/main.py 多处) |
| P1#5 | P1 | CORS `*` + credentials=True | ❌ 未修 (实测 evil.com 仍可携带 credentials) |
| P1#6 | P1 | TUSHARE_TOKEN commit | ✅ 已修 (filter-repo + 轮换) |
| P1#7 | P1 | rate-limit 缺失 | ❌ 未修 |
| P1#8 | P1 | 前导零 dtype 修复未覆盖 | 部分修 (commit e1c8ea3 修 kline_analyzer，api/main.py 多处未改) |
| P1#9 | P1 | bind 0.0.0.0:8000 | ✅ 已修 (systemd uvicorn 127.0.0.1) |
| P1#10 | P1 | sync_repo.sh 静默回退 main | ❌ 未修 |
| P2#11 | P2 | start_financial_score.sh 等待循环 bug | ❌ 未修（脚本仍存在，已废） |
| P2#12 | P2 | monitor_api.sh LOG_FILE 未用 | ❌ 未修 |
| P2#13 | P2 | monitor_api.sh hardcode 600519 | ❌ 未修 |
| P2#14 | P2 | monitor_api.sh 不在 cron | ❌ 未修 |
| P2#15 | P2 | deploy_stock_system.sh 备份命名重复 | 部分修（备份日期但同日仍重复） |
| P2#16 | P2 | deploy/stock-api.service hardening | ❌ 未修（但新 unit 加了 EnvironmentFile 和日志文件） |
| P2#17 | P2 | evening_pipeline.sh 双日志 | ❌ 未修 |
| P2#18 | P2 | CRON.md 无错误通知 | ❌ 未修 |
| P2#19 | P2 | api/__pycache__/ 65KB | ❌ 未修 |
| P2#20 | P2 | `result/daily_score/bak/` 死文件 | ❌ 未修（新增发现） |
| P3#21 | P3 | main.py:1089 dtype 字段类型混乱 | 未核查 |
| P3#22 | P3 | api/main.py 注释 "修复 6.1" 残留 | 未核查 |
| P3#23 | P3 | stock-system.conf proxy_pass 无超时 | ❌ 未修 |
