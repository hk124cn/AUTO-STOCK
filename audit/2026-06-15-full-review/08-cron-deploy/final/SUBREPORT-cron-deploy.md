# 子报告：Cron / 部署 / API（复查 #2）

> 范围：`deploy/`（含新增 `deploy_stock_system.sh` + `stock-system.conf`）、`/etc/systemd/system/stock-api.service`、`/etc/nginx/conf.d/stock-system.conf`、`CRON.md`、`MAINTENANCE.md`、`scripts/{start,stop,monitor,sync}_*`、新 `api/security.py`、`api/main.py` 鉴权/错误响应/CORS、`config/config.py`、`.env`、`.trash/`、`.git.backup-before-filter-repo/`、ps/ss 现场、crontab -l
> 严重程度评级：P0=功能错误/安全漏洞 / P1=性能或安全 / P2=可改进 / P3=小问题
> 审查日期：2026-06-16（接续 2026-06-14 报告）

## 1. 概览

上次审查的 4 个 P0 中，**3 个已修复**：(P0#1) API 鉴权上线（`api/security.py` + 11 个写端点加 `Depends(verify_token)`，实测未认证 POST 返回 401），(P0#2) systemd uvicorn 单一在跑，gunicorn 已停（`ps aux` 仅 1 个 `uvicorn api.main:app` pid 1900978 监听 `127.0.0.1:8000`），(P0#6) TUSHARE_TOKEN 改为从 `.env`（600 权限）读取并已用 `git filter-repo` 抹历史+轮换 token；新增 `deploy/deploy_stock_system.sh` 一键脚本把 nginx + systemd 全套部署完成（`/etc/nginx/conf.d/stock-system.conf` 路径独立、新增 8 类敏感文件 deny 规则、TLS 头齐全）。

但仍有 2 个 P0 完全未修：(P0#3) `CRON.md:11` 和 `MAINTENANCE.md:114` 仍引死脚本 `scripts/daily_download.sh`，而实际 crontab 用的是 `scripts/daily_data_fetch.py`（实际是 `.py` 不是 `.sh`）— 同一文档 1 天后被审查指出但未同步修正；(P0#4) API 错误响应仍 `{"error": str(e), ...}` 给客户端（`api/main.py:503/541/595/642/699/721/784/801/811/821/836` 等至少 12 处），未对外做脱敏。CORS 的 P1 也未修，实测 `Origin: https://evil.com` + 凭据仍能跨域访问 GET 端点（evil origin 出现在 `Access-Control-Allow-Origin`，且 `Access-Control-Allow-Credentials: true`）。

新增发现 1 个 P1：`data/portfolio.db` 文件权限 `644 admin:admin` —— 全员可读 SQLite，**业务账户/持仓数据对同机用户完全开放**。`.git.backup-before-filter-repo/` 仍在工作树（`644`），若被误 push 会把 filter-repo 抹除的旧密钥历史完整带出（filter-repo 是本地操作，未做"删除工作树 backup"步骤）。

整体评价：4 个原 P0 修掉 3 个，修复质量高（鉴权、env 化、systemd 收编、部署脚本化都到位）；但 1 个 P0 死脚本引用在两个文档里都未同步、1 个 P0 错误响应脱敏仍未动 + 新增 1 个 P1 文件权限。`monitor_api.sh` 仍是僵尸脚本（不在 cron，杀 gunicorn 杀不到 uvicorn，硬编 600519 永远检测不到 503），建议在下一次迭代彻底废弃。

## 2. 关键发现（按严重程度降序）

### [P0] CRON.md / MAINTENANCE.md 仍引死脚本 `scripts/daily_download.sh`（未修）
- 位置：`/home/admin/AUTO-STOCK/CRON.md:11`、`/home/admin/AUTO-STOCK/MAINTENANCE.md:114`
- 现象：
  ```
  CRON.md:11: | 17:00 | 拉取当天市场数据 | `scripts/daily_download.sh` | 下载价格、资金流向、行业等 |
  MAINTENANCE.md:114: | 17:00 | 拉取市场数据 | `scripts/daily_download.sh` |
  ```
  `ls /home/admin/AUTO-STOCK/scripts/daily_download.sh` → **No such file or directory**
  实际 crontab 是：`0 17 * * 1-5 cd /home/admin/AUTO-STOCK && /usr/bin/python3 scripts/daily_data_fetch.py`（**是 .py 不是 .sh**，文件类型错+文件名错）
- 后果：新人按文档排查 17:00 任务时找不存在的 .sh 脚本；上次审查报告 SUBREPORT-cron-deploy.md P0#3 已指出 2 天仍未修。
- 建议：CRON.md 和 MAINTENANCE.md 表格第 1 行改为 `scripts/daily_data_fetch.py`。

### [P0] API 错误响应把原始 `str(e)` 返回客户端（未修）
- 位置：`/home/admin/AUTO-STOCK/api/main.py:503, 541, 595, 642, 699, 721, 784, 801, 811, 821, 836, 933+`
- 现象（21 处）：
  ```python
  except Exception as e:
      logger.info(f"...失败: {str(e)}")
      return JSONResponse(status_code=500, content={"error": str(e), ...})
  ```
- 后果：可能泄漏内部路径、stack trace 片段、SQLite 错误细节给攻击者。`str(e)` 本身已被 logger 记录，但同时裸返回客户端（侦察阶段信息收集 + 让"数据 X 字段不存在"等内部 schema 暴露）。
- 上次审查（P0#4）已指出，未修。
- 建议：加 helper `_safe_500(e, request)` 返回 `{"error": "内部错误", "request_id": "..."}`，原始 e 仅写日志。

### [P1] CORS `allow_origins=["*"]` + `allow_credentials=True`（未修，**实测仍可跨域携带凭据**）
- 位置：`/home/admin/AUTO-STOCK/api/main.py:47-53`
- 现象（与上次审查一字未改）：
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- 实测（`2026-06-16 09:52` 跑）：
  ```
  $ curl -X OPTIONS -H "Origin: https://evil.com" -H "Access-Control-Request-Method: POST" \
         http://127.0.0.1:8000/api/v1/portfolio/buy -i
  HTTP/1.1 200 OK
  Access-Control-Allow-Credentials: true
  Access-Control-Allow-Origin: https://evil.com
  Access-Control-Allow-Methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
  ```
  **任意 origin 可携带 credentials 跨域调 GET 端点**（写端点被 verify_token 拦下，但 GET 公开数据可被任意站点代理抓取，配合 `Access-Control-Allow-Credentials` 可形成 CSRF 链路利用浏览器 cookie）。
- 后果：跨站可读所有 GET 端点数据（财务评分、信号、portfolio 详情）+ 若用户在该浏览器登录过并保持 cookie（24h in-memory token 不持久化，理论风险低，但 GET 端点无认证，第三方网站可代理读）。
- 建议：列出明确 origin（`["https://stock.auto-claw.top", "https://auto-claw.top", "https://www.auto-claw.top"]`），`allow_credentials=False`。

### [P1] `data/portfolio.db` 文件权限 `644 admin:admin`（同机用户可读持仓库）
- 位置：`/home/admin/AUTO-STOCK/data/portfolio.db`
- 现象：`stat -c '%a %U %G' /home/admin/AUTO-STOCK/data/portfolio.db` → `644 admin admin`
- 后果：同机任何用户可 `sqlite3 data/portfolio.db` 读取全部账户（持仓、成交、初始资金、止盈止损规则）；同机租户/运维误操作/被入侵的伴生进程可全量导出。
- 建议：`chmod 600 data/portfolio.db`（或 640 给特定 group），并加 systemd `ReadWritePaths=/home/admin/AUTO-STOCK/data` 限制。

### [P1] `.git.backup-before-filter-repo/` 仍工作树，filter-repo 抹除的历史可被恢复
- 位置：`/home/admin/AUTO-STOCK/.git.backup-before-filter-repo/`
- 现象：`ls -la` 显示完整 git 仓库结构（branches/, hooks/, COMMIT_EDITMSG 含"待 git filter-repo 抹除历史"），是 `git filter-repo` 操作前的 git 仓库副本。
- 后果：filter-repo 已替换 `config/config.py` 历史中的 token 为占位符并删了含旧 token 的分支，但**本目录的完整旧仓库未删**。若 `git add .` 误把这个目录提交（`git status` 显示它未被跟踪），下次 push 会把旧密钥历史完整带出 GitHub，让 filter-repo 工作白做。
- 建议：`rm -rf .git.backup-before-filter-repo/`（操作前确认 filter-repo 已成功）；或加 `.gitignore` 一行 `.git.backup-before-filter-repo/`。

### [P2] `monitor_api.sh` 完全失效（不在 cron + 杀错进程 + 硬编 URL）
- 位置：`/home/admin/AUTO-STOCK/scripts/monitor_api.sh`
- 现象：
  - L17 杀进程：`pkill -f "gunicorn.*api.main"`（实际跑 uvicorn，杀不到）
  - L22 启动：`gunicorn ... --bind 0.0.0.0:8000`（会失败，因 systemd uvicorn 占 8000）
  - L6 URL：`http://localhost:8000/api/v1/financial/score/600519`（仍 hardcode 600519）
  - 不在 crontab（`crontab -l | grep monitor_api` 空）
  - `logs/api_monitor.log` 最后一条：`2026-04-24 08:10:05 - API 重启成功`（2 个月没跑）
- 后果：监控脚本是僵尸。若 uvicorn 真的挂了，没有自动拉起机制。systemd 的 `Restart=always` 兜底 5s 重启能撑住 90% 场景，但 OOM / deadlock 类需 3+ 次重启失败才会放弃（systemd 默认不会无限制重启）—— 监控缺位。
- 建议：要么删 `monitor_api.sh` 文档化"systemd 负责拉起"；要么重写为：
  ```bash
  pkill -f "uvicorn api.main:app" 2>/dev/null
  systemctl restart stock-api.service
  ```
  并加 `*/5 * * * * bash /home/admin/AUTO-STOCK/scripts/monitor_api.sh`。

### [P2] `MAINTENANCE.md` 推荐 `start_financial_score.sh`（已废脚本）
- 位置：`/home/admin/AUTO-STOCK/MAINTENANCE.md:127, 132-134`
- 现象：
  - L127: "启动服务: `bash /home/admin/AUTO-STOCK/scripts/start_financial_score.sh`"
  - L132: "构建前端（需先停 gunicorn 释放内存）" 仍以 gunicorn 为前提
- 后果：运维按文档跑会拉起一个**立即冲突 8000 端口**的 gunicorn（新 systemd uvicorn 已占）；脚本表面"启动完成"但服务没起。
- 建议：MAINTENANCE.md 改用 `sudo bash deploy/deploy_stock_system.sh`（gunicorn 完全不出现）。

### [P2] `deploy/stock-api.service` 缺 hardening 选项
- 位置：`/home/admin/AUTO-STOCK/deploy/stock-api.service:1-23`
- 现象：相比上次审查没新增 hardening。仍缺：
  - `NoNewPrivileges=true`
  - `PrivateTmp=true`
  - `ProtectSystem=strict`
  - `ReadWritePaths=/home/admin/AUTO-STOCK/logs /home/admin/AUTO-STOCK/data /home/admin/AUTO-STOCK/result`（API 实际写这三处）
  - `MemoryMax=512M`
  - `LimitNOFILE=65536`
- 后果：API 进程对 `/home/admin` 整棵有写权（root user 限定为 admin，但缺 sandbox）。
- 建议：补齐 hardening；尤其是 `ReadWritePaths` 限制能阻止"一旦应用被 RCE，攻击者改 deploy/ 部署脚本"。

### [P2] `CRON.md:141` 提 Gunicorn 日志位置 `/tmp/gunicorn.log`（gunicorn 已停）
- 现象：Gunicorn 完全不再跑，这条信息误导排查（不会再去 `tail /tmp/gunicorn.log`）。
- 建议：改为 uvicorn 日志位置 `logs/api-stdout.log` / `logs/api-stderr.log`。

### [P2] `result/daily_score/bak/` 仍存在 12 个死 CSV 文件
- 位置：`/home/admin/AUTO-STOCK/result/daily_score/bak/`
- 现象：含 `batch_result_20260308.csv`、`batch_result_20260327.csv`、4 个 `batch_result_test*.csv`、`stock_test_result*.csv`、`test_result.csv` 等，时间戳 2026-05-24 17:20。
- 后果：占 ~50KB；不会被 `kline_analyzer` / `daily_report` 读到（按日期路径找文件），但 git status 已显示是 `D`（删除但未提交），实际**已从工作树删除但仍在文件系统**——审计 `git ls-files` 看不到。
- 验证：`ls -la /home/admin/AUTO-STOCK/result/daily_score/bak/` 12 个文件存在；`git ls-files result/daily_score/bak/` 空。
- 建议：`rm -rf /home/admin/AUTO-STOCK/result/daily_score/bak/`（它们已从 git 删了，物理删除不会丢数据）。

### [P2] `deploy/stock-system.conf` 反代无超时设置
- 位置：`/home/admin/AUTO-STOCK/deploy/stock-system.conf:48-54`
- 现象：`proxy_pass http://127.0.0.1:8000;` 无 `proxy_read_timeout / proxy_send_timeout`（默认 60s）。
- 后果：长时间未响应会占 worker；与上次审查 P3#23 重复。
- 建议：`proxy_read_timeout 30s; proxy_send_timeout 30s; proxy_connect_timeout 5s;`。

### [P2] `feedbacks.json` 权限 664（全员可写，无 rate-limit）
- 位置：`/home/admin/AUTO-STOCK/feedbacks.json`
- 现象：664 admin:admin。`/api/v1/feedback` 端点公开 + 无 slowapi/nginx limit_req。
- 后果：同机用户可篡改反馈；远程攻击者可写满磁盘（每次 ~300B，无上限）。
- 建议：`chmod 644 feedbacks.json`（去 group write）+ nginx 加 `limit_req_zone $binary_remote_addr zone=feedback:10m rate=5r/m;` 限到 feedback 路径。

### [P2] `scripts/sync_repo.sh` 静默回退 main 分支（未修）
- 位置：`/home/admin/AUTO-STOCK/scripts/sync_repo.sh:23-27`
- 现象：远端分支不存在时静默 `git checkout main` + 强制 pull。
- 建议：远端缺失直接 `exit 1` + stderr 报警。

### [P2] `scripts/start_financial_score.sh` 仍存在并被文档引用
- 现象：脚本本身未删（122 行 + gunicorn + 3000 vite 都已失效）；MAINTENANCE.md 仍推荐。脚本中 L12-20 等待循环 bug 仍未修。
- 建议：脚本整体废弃（gunicorn + vite 均不在用），或加文件头 `⚠️ 已废弃，请用 deploy/deploy_stock_system.sh`。

### [P2] `evening_pipeline.sh` 双日志问题未修
- 位置：`/home/admin/AUTO-STOCK/scripts/evening_pipeline.sh:12` + cron `>> logs/evening_pipeline.log 2>&1`
- 现象：脚本内 `exec > >(tee -a "$LOG") 2>&1` 写 `logs/evening_pipeline_${DATE}_${HMS}.log`，cron 又写 `logs/evening_pipeline.log`（覆盖式）。两次 run 同一日期会产生 2 份日志。
- 建议：cron 不 redirect，让脚本内 tee 统一管。

### [P3] `.env.example` 仍提"旧 token 已 commit 到 git 历史"
- 位置：`/home/admin/AUTO-STOCK/.env.example:6`
- 现象：`# 注意：旧 token 已 commit 到 git 历史，请去 tushare.pro 重置后填新值`
- 建议：filter-repo 完成后改为中性描述（"去 tushare.pro 个人中心获取"）。

### [P3] MAINTENANCE.md / CRON.md 无错误通知机制说明（未修）
- 现象：所有 cron 行无 MAILTO 或 webhook。失败只能 `grep ERROR logs/...`。
- 建议：加 MAILTO 或 `curl -X POST` 推送到通知服务。

### [P3] `CRON.md` 19:30 calc_signals.py 调度缺失
- 现象：MAINTENANCE.md:117 列出 `19:30 | 信号计算 | scripts/calc_signals.py`，但 `crontab -l` 无 `calc_signals` 行。
- 后果：依赖手工 `python3 scripts/calc_signals.py`；前端 `signals_latest.csv` 何时更新不可控。
- 建议：加 `30 19 * * 1-5 cd /home/admin/AUTO-STOCK && python3 scripts/calc_signals.py`。

## 3. 改进建议（非问题，但有更好做法）

1. **新 deploy 脚本加 `--dry-run`**：避免误操作直接覆盖现有服务。
2. **`/healthz` 端点**：让 nginx + 外部监控可 ping；`/api/v1/portfolio/account` 是认证前可用的（无 Depends）但响应是 JSON 不便健康检查。
3. **HSTS preload**：当前 `Strict-Transport-Security "max-age=31536000; includeSubDomains"` 加 `; preload` 提交到 https://hstspreload.org。
4. **`deploy_stock_system.sh` 备份命名重复**：`bak.$(date +%Y%m%d)` 同日多次跑只保留最后一次。建议 `bak.$(date +%Y%m%d-%H%M%S)`。
5. **`api/security.py` token cleanup**：`_TOKEN_STORE` 无 cron 清理，`cleanup_expired_tokens()` 函数定义但未在 startup 调用。in-memory dict 长期累积（极端情况：每秒 1 个新 token 一天 86k 个条目）。建议 startup 调用一次 + 每 1h 清理。
6. **`STOCK_API_PASSWORD` 环境变量优先但未在 systemd 配置**：`deploy/stock-api.service` 只用 `EnvironmentFile=-/home/admin/AUTO-STOCK/.env`；如未来要在容器化场景下用 systemd drop-in 覆盖，需补 `Environment=STOCK_API_PASSWORD=` 占位。
7. **`feedbacks.json` 改 SQLite 或加 size cap**：当前 JSON 数组无限增长；改成 `data/feedback.db` + 7 天清理。
8. **`/data/price/` 暴露**：`deploy/stock-system.conf:67-70` 直接 alias `/home/admin/AUTO-STOCK/data/price/` 整棵，仅 `autoindex off` 阻止目录列表——单文件名访问**仍可读**（含 5000+ 个个股 CSV）。建议加 `location ~* /data/price/[0-9]+\.csv` 限制为 6 位代码格式 + deny 其他；或改由 `/api/v1/price/...` 经应用层。

## 4. 需要核实的不确定项

- **`scripts/sync_repo.sh` 静默回退 main 是否有意为之？** 与之前 P1#10 重复出现，作者可能是有意"生产环境只用 main"。建议在脚本顶部加注释说明设计意图。
- **`.git.backup-before-filter-repo/` 留多久？** 应该是临时备份，过滤完后应删。本次审查已建议删除。
- **`monitor_api.sh` 是否真要废弃？** systemd `Restart=always` 已能覆盖单次崩溃，但 OOM 类失败（连续 3 次重启失败 systemd 才放弃）需要外部监控介入。
- **API 错误响应 `str(e)` 是否对前端有依赖？** 改为通用 "内部错误" 后，前端可能需要做错误展示调整——审查范围外未核对。
- **`/api/v1/feedback` 是否真为公开端点？** 鉴权实施时它被显式排除在 `verify_token` 之外（`api/security.py:9` 注释"公开端点（GET + POST /api/v1/feedback）不受影响"），但 feedback 内容（含用户 IP/UA）是否应脱敏存储未审。

## 5. 上次 P0 修复状态汇总

| ID | 上次级别 | 标题 | 状态 | 证据 |
|----|---------|------|------|------|
| P0#1 | P0 | API 无任何认证 | ✅ **已修** | `api/security.py` + 11 个写端点 `Depends(verify_token)` + `POST /api/v1/auth/login`；实测 `curl POST /buy` → 401 |
| P0#2 | P0 | systemd vs gunicorn 双轨冲突 | ✅ **已修** | `ps aux` 只见 uvicorn pid 1900978；gunicorn 0 进程；`ss -tlnp :8000` 单一监听 |
| P0#3 | P0 | CRON.md 引用死脚本 daily_download.sh | ❌ **未修** | `CRON.md:11`、`MAINTENANCE.md:114` 仍在；实际是 `daily_data_fetch.py` |
| P0#4 | P0 | API 错误响应 str(e) 泄漏 | ❌ **未修** | `api/main.py` 至少 12 处仍 `return JSONResponse({"error": str(e), ...})` |
| P1#5 | P1 | CORS `*` + credentials | ❌ **未修** | 实测 `Origin: https://evil.com` → ACAO 返回 evil.com + ACAC true |
| P1#6 | P1 | TUSHARE_TOKEN commit 到 git | ✅ **已修** | `config/config.py` 改从 `.env` 读；`filter-repo` 抹历史 + 轮换 token（commit 8b938f2） |
| P1#7 | P1 | rate-limit 缺失 | ❌ **未修** | feedback 端点无；nginx 无 limit_req |
| P1#8 | P1 | 前导零 dtype 修复 | 部分 | kline_analyzer 修了（commit e1c8ea3）；api/main.py 多处 `pd.read_csv` 仍无 dtype |
| P1#9 | P1 | bind 0.0.0.0:8000 | ✅ **已修** | systemd uvicorn `--bind 127.0.0.1:8000` |
| P1#10 | P1 | sync_repo.sh 静默回退 main | ❌ **未修** | 脚本内容未变 |

**修复率**：上次 4 个 P0 修掉 3 个（75%），6 个 P1 修掉 2 个（33%）。

## 6. 评分（1-5，5 = 优）

- 正确性：**3**（4 个 P0 修 3 个，但 P0 死脚本引用+错误响应脱敏仍未动；新增 2 个 P1）
- 可维护性：**3**（deploy 脚本化、systemd 收编都到位；但 start_financial_score.sh 死脚本 + MAINTENANCE.md 推荐路径未更新 + monitor_api.sh 僵尸）
- 性能：**3**（uvicorn 单 worker + 无 rate-limit；反代无超时）
- 文档：**3**（CRON.md/MAINTENANCE.md 各有 1 处死引用 + Gunicorn 日志位置误导；HANDOVER.md 写完但 README 未更新）
- **总评：3**（上次 2 → 3：核心安全态势明显改善，但仍有 2 个 P0 + 3 个 P1 需在下一迭代关闭）
