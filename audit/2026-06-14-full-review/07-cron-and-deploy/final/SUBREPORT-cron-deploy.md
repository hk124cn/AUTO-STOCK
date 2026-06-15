# 子报告：Cron / 部署 / API

> 范围：CRON.md、deploy/、api/main.py（+ api/main.py.bak2）、scripts/start_financial_score.sh、stop_financial_score.sh、monitor_api.sh、sync_repo.sh、scripts/evening_pipeline.sh（cron 集成部分）、api/__pycache__/
> 严重程度评级：P0=功能错误/安全漏洞/P1=性能或安全/P2=可改进/P3=小问题
> 审查日期：2026-06-14

## 1. 概览

AUTO-STOCK 当前采用"systemd + 手动 start 脚本"双轨部署：systemd unit `stock-api.service` 用 uvicorn 监听 `127.0.0.1:8000`，而 `scripts/start_financial_score.sh` 用 gunicorn 监听 `0.0.0.0:8000`，**两套互相争抢同一端口**，实际是 systemd uvicorn 在跑（pid 1436084），gunicorn 早已停摆。CRON.md 文档与实际 `crontab -l` 有 3 处不一致，最严重的是 CRON.md 第 11 行声称的 `scripts/daily_download.sh` 在工作树中根本不存在。API 没有任何认证（无 JWT、无 API Key），但暴露了买入/卖出/删除交易/修改初始资金等高危写端点，配上 `allow_origins=["*"] + allow_credentials=True` 的不安全 CORS 配置，构成显著的横向提权风险。配置文件中**已提交**的 `TUSHARE_TOKEN` 是真实 token 且被 git 历史永久记录。

整体评价：可用但安全态势堪忧，文档与实现多处漂移，建议在合并 PR 前补齐认证 + 清理双轨部署。

## 2. 关键发现（按严重程度降序）

### [P0] API 无任何认证，写端点暴露在公网
- 位置：`/home/admin/AUTO-STOCK/api/main.py:1-1150`（整个 FastAPI 应用）
- 现象：`grep -nE "auth|jwt|API_KEY|Authorization|HTTPBearer" api/main.py` 零结果。所有路由（GET/POST/PUT/DELETE）均无身份验证。
- 后果：
  - 任何访问 `https://stock.auto-claw.top/api/v1/portfolio/buy`（已通过 nginx 代理暴露）的人都能下模拟/真实交易单
  - `POST /api/v1/portfolio/update-capital` 可**重置整个账户**
  - `POST /api/v1/portfolio/delete-trade` 可**任意删交易记录**（合规审计失效）
  - `DELETE /api/v1/strategies/{id}` 可**删策略**
  - `POST /api/v1/feedback` 无频率限制——可写满 `feedbacks.json`（文件无限增长）
- 证据：
  ```python
  # api/main.py:804
  @app.post("/api/v1/portfolio/buy")
  async def buy_stock(req: BuyRequest):    # 无 Depends(...)
  ```
- 建议：至少在写端点前加 `Depends(verify_api_key)`（静态 token 或环境变量）；考虑用 nginx IP 白名单 + fail2ban。

### [P0] systemd 进程与 start_financial_score.sh 端口冲突，实际是双轨混乱
- 位置：`deploy/stock-api.service:12` + `scripts/start_financial_score.sh:22`
- 现象：
  - systemd: `ExecStart=/usr/bin/python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000`
  - 启动脚本: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000`
  - 两者绑定同一端口 8000，启动脚本 bind `0.0.0.0` 会**失败**（systemd 先占 127.0.0.1）
  - 监控脚本 `monitor_api.sh` L22 只检测 gunicorn，但实际在跑的是 uvicorn —— **监控失效**
  - `stop_financial_score.sh` 只杀 gunicorn，**不杀 uvicorn**
- 后果：运维认知错位；脚本表面"启动成功"，实际服务是 systemd 那一份；任何误判都会让运维找不到进程
- 证据：
  ```
  $ ss -tlnp | grep :8000
  LISTEN 0  2048  127.0.0.1:8000  ... users:(("python3",pid=1436084,...))
  $ ps aux | grep uvicorn
  admin 1436084 ... uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1
  ```
- 建议：删除 `start_financial_score.sh` 中的 gunicorn 启动逻辑，统一用 systemd；或者反过来废弃 systemd。但**不能两套并存**。

### [P0] CRON.md 第 11 行引用了不存在的脚本 `scripts/daily_download.sh`
- 位置：`CRON.md:11`
- 现象：
  ```
  | 17:00 | 拉取当天市场数据 | `scripts/daily_download.sh` | 下载价格、资金流向、行业等 |
  ```
  但 `ls /home/admin/AUTO-STOCK/scripts/daily_download.sh` → No such file or directory
- 实际 crontab 是 `0 17 * * 1-5 cd /home/admin/AUTO-STOCK && /usr/bin/python3 scripts/daily_data_fetch.py`
- 后果：新人按文档排查 "17:00 任务为什么没跑"会浪费时间找不存在的 .sh 脚本
- 建议：把 CRON.md 表格改为 `scripts/daily_data_fetch.py`（或反过来改名脚本）

### [P0] API 错误响应把原始异常 str(e) 返回客户端（信息泄漏）
- 位置：`/home/admin/AUTO-STOCK/api/main.py:483, 521, 575, 622, 679, 701, 813-818, 832-834, 845, 857, 867, 878, 902, 912, 955, 973, 984, 994, 1004, 1014, 1068, 1113, 1143`
- 现象：所有 500 异常都返回 `{"error": str(e), ...}` 给客户端
- 后果：可能泄漏内部路径、stack trace 片段、SQL 错误细节给攻击者（侦察阶段信息收集）
- 证据：
  ```python
  except Exception as e:
      return JSONResponse(status_code=500, content={"error": str(e), "code": code_normalized})
  ```
- 建议：对外只返回 `{"error": "内部错误", "request_id": "..."}`，把原始 str(e) 写日志但不返回。

### [P1] CORS 配置 `allow_origins=["*"] + allow_credentials=True` 违反规范且不安全
- 位置：`api/main.py:47-53`
- 现象：
  ```python
  app.add_middleware(CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,    # ⚠ 与 "*" 组合违反规范
      allow_methods=["*"],
      allow_headers=["*"])
  ```
- 后果：FastAPI/Starlette 启动时本应报警"Invalid args"（取决于版本）；同时任意 Origin 可携带 credentials（CSRF 风险）
- 建议：列出明确 origin（`["https://stock.auto-claw.top", "https://auto-claw.top"]`），或在不需要 credentials 时设为 `False`

### [P1] `config/config.py` 中的 TUSHARE_TOKEN 已 commit 到 git
- 位置：`/home/admin/AUTO-STOCK/config/config.py:2`
- 现象：`TUSHARE_TOKEN = "OLD_TUSHARE_TOKEN_REDACTED"` 是真实 token
- `git ls-files config/config.py` 确认在 git 跟踪
- `git log -- config/config.py` 验证存在历史
- 后果：token 在 git 历史中永久保留；即使从 working tree 删除，旧 commit 仍可读
- 当前**没人 import tushare**——token 是死代码，但暴露风险仍在
- 建议：
  1. 立即**轮换 token**（去 tushare 官网撤销旧 token）
  2. 从 git 历史用 `git filter-repo` 或 `bfg` 清除
  3. 改用环境变量 `os.environ.get('TUSHARE_TOKEN')`

### [P1] API 路由列表导出 / 写端点缺失 rate-limit
- 位置：`api/main.py:804-1014`（所有 POST/PUT/DELETE 路由）
- 现象：没有任何 `slowapi` / 自实现 token bucket / nginx limit_req
- 后果：单 IP 可发 1000 次/s 的 `update-prices`，刷爆数据库；feedback 接口可写满磁盘
- 建议：nginx 加 `limit_req_zone` 或 Python 层加 slowapi middleware。

### [P1] 前导零风险（08e6abb 修复未覆盖全部位置）
- 位置：`api/main.py:38, 91, 639, 670, 693` + `main.py:61`
- 现象：commit `08e6abb` 修复了 `kline_analyzer.py` 加 `dtype={'code': str}`，但 API 层和 CLI 层多处仍用 `pd.read_csv(...)` 而不指定 dtype
- 后果：深市股票（000xxx）经 pandas 后丢前导零；前端虽能兜底但 API 返回 code 不一致（`/api/v1/reports/today` 等）
- 证据：
  ```python
  # api/main.py:639
  df = pd.read_csv(result_file)               # 缺 dtype={'code': str}
  # api/main.py:670
  df = pd.read_csv(result_file)
  # api/main.py:693
  df = pd.read_csv(result_file)
  # main.py:61
  df = pd.read_csv(csv_file)
  ```
- 建议：统一在 `src/datafactory/data_manager.py` 加 `safe_read_csv(path)` helper；所有读 stock data 的地方改用它

### [P1] 端口 0.0.0.0:8000（start_financial_score.sh）+ 任意网络可达
- 位置：`scripts/start_financial_score.sh:22`
- 现象：`gunicorn ... --bind 0.0.0.0:8000`
- 后果：API（含无认证的写端点）直接暴露整个网段——不仅 nginx 入口，连带机器其他网络也可直连
- 建议：改为 `--bind 127.0.0.1:8000`，统一让 nginx 代理

### [P1] `sync_repo.sh` 静默回退到 main 分支
- 位置：`scripts/sync_repo.sh:23-27`
- 现象：
  ```bash
  if git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}"; then
      git checkout "${BRANCH}" ...
  else
      echo "⚠️  远端不存在 origin/${BRANCH}，回退到 origin/main"
      git checkout main 2>/dev/null || git checkout -b main origin/main
      git pull --ff-only origin main
  fi
  ```
- 后果：若 cron 误传不存在的分支名，脚本静默切到 main 并强制拉取——本地未提交工作可能被覆盖
- 建议：远端分支不存在时 `exit 1`，并附带 stderr 报警；不要静默 fallback

### [P2] `start_financial_score.sh` "等待旧进程退出" 循环 bug
- 位置：`scripts/start_financial_score.sh:12-20`
- 现象：5 次循环结束后若进程仍在跑，**直接 break 不报错**——后续 `nohup ... &` 会起新进程，端口冲突
- 建议：超时后 `exit 1` 或用 PID 文件记录

### [P2] `monitor_api.sh` LOG_FILE 变量未使用，写到了 `/tmp/api.log`
- 位置：`scripts/monitor_api.sh:4` vs L22
- 现象：`LOG_FILE="/home/admin/AUTO-STOCK/logs/api_monitor.log"` 定义但 L22 用 `> /tmp/api.log 2>&1 &`
- 后果：监控日志散落在 /tmp 不在项目 logs/
- 建议：去掉 LOG_FILE 定义，或者 redirect 到 LOG_FILE

### [P2] `monitor_api.sh` 健康检查 URL hardcode 600519
- 位置：`scripts/monitor_api.sh:6`
- 现象：`API_URL="http://localhost:${API_PORT}/api/v1/financial/score/600519"`
- 后果：600519 数据异常时误判 API 挂——增加无效重启
- 建议：用 `/api/v1/portfolio/account`（轻量级、纯 DB 查询）

### [P2] `monitor_api.sh` 未挂 cron，永不自动运行
- 现象：crontab -l 中**没有** monitor_api.sh 的调度
- 后果：监控脚本形同虚设——只在手工调用时生效
- 建议：加 `*/2 * * * * bash /home/admin/AUTO-STOCK/scripts/monitor_api.sh`

### [P2] `deploy/deploy_stock_system.sh` 备份命名重复会覆盖
- 位置：`deploy/deploy_stock_system.sh:29, 39`
- 现象：`.bak.$(date +%Y%m%d)` 同日多次跑**只保留最后一次**
- 建议：用秒或 hash 后缀区分：`bak.$(date +%Y%m%d-%H%M%S)`

### [P2] `deploy/stock-api.service` 缺 hardening 选项
- 位置：`deploy/stock-api.service:1-19`
- 现象：没有 `NoNewPrivileges=true`、`PrivateTmp=true`、`ProtectSystem=strict`、`ReadWritePaths=/home/admin/AUTO-STOCK/logs`、`MemoryMax=512M`
- 建议：补齐上述行（尤其 `ReadWritePaths` 限制 API 只能写 logs/）

### [P2] `evening_pipeline.sh` 双日志问题
- 位置：`scripts/evening_pipeline.sh:12` + cron 行（`>> logs/evening_pipeline.log`）
- 现象：
  - cron 把 stdout 写到 `logs/evening_pipeline.log`（固定文件名）
  - 脚本内 `exec > >(tee -a "$LOG") 2>&1` 又写 `logs/evening_pipeline_${DATE}_${HMS}.log`
- 后果：同一流水线产生两份日志（一份随脚本覆盖 / 一份累积），grep 排查需看两份
- 建议：cron 行不要 redirect（让脚本内 `tee` 统一管理），或者脚本内不要再 tee

### [P2] `CRON.md` 无错误通知机制说明
- 现象：所有 cron 行无 MAILTO、无 webhook
- 后果：失败只能人工 `grep ERROR`
- 建议：加 MAILTO 或用 `curl -X POST` 推送到通知服务

### [P2] `api/__pycache__/` 体积 65KB 在工作树（git 已忽略）
- 现象：`api/__pycache__/main.cpython-311.pyc` 65KB
- 建议：`find . -name __pycache__ -exec rm -rf {} \;` 清理

### [P3] `main.py:1089` 加了 `dtype={'code': str}` 但 `df` 字段类型可能混乱
- 位置：`api/main.py:1089, 1125`
- 现象：`pd.read_csv(signal_file, dtype={'code': str})` —— 但 close_price 列仍是 object，可能在 JSON 序列化出问题
- 建议：所有列都显式 dtype

### [P3] `api/main.py` 注释残留 "修复 6.1"（handover note）
- 位置：L707, 1071
- 现象：注释 `修复 6.1: 暴露 portfolio 端点` 指代不明
- 建议：清理或加注释解释

### [P3] `deploy/stock-system.conf` `proxy_pass` 无超时设置
- 位置：`deploy/stock-system.conf:48-54`
- 现象：`proxy_pass http://127.0.0.1:8000` 走默认 60s 超时
- 建议：加 `proxy_read_timeout 30s; proxy_send_timeout 30s;`

## 3. 改进建议（非问题，但有更好做法）

1. **API 日志格式**：`api/main.py` L62 `format='%(message)s'` 改为 `'%(asctime)s [%(levelname)s] %(name)s: %(message)s'`。
2. **股票池加载**：用 `csv.DictReader` 替代 `pd.read_csv` —— 启动时减少 50MB 内存占用。
3. **CRON 文档化错误通知**：在 `CRON.md` 顶部加"运维通知"章节，列 MAILTO 或 webhook 配置。
4. **`stock_full_pool.csv` 加载失败时降级**：`api/main.py:33-44` 失败仅 print，应该 `raise` 让 systemd 重启。
5. **health check endpoint**：加 `GET /healthz` 返回 200，让 nginx + 监控可以 ping。
6. **HSTS preload**：当前 `Strict-Transport-Security max-age=31536000` 可以 `; preload` 让浏览器 preload。
7. **`deploy_stock_system.sh` 加 `--dry-run`**：避免误操作直接覆盖现有服务。

## 4. 需要核实的不确定项

- `daily_data_fetch.py` docstring 第 13 行声称 `0 16` cron，实际是 `0 17` —— **docstring 与 cron 不一致**，是否有意为之需询问作者。
- `evening_pipeline.sh` 步骤 3.5（模拟仓 sim_trader.py）CRON.md **完全没提** —— 是新增功能还是临时实验？
- `meta/` 目录是否还有维护价值？snapshot_manifest.csv 只到 20260522 后无更新。
- `scripts/r2_backup.py` 在 cron 中（`0 3 * * *`），但未审查（不在本子审查范围）。

## 5. 评分（1-5，5 = 优）

- 正确性：3（P0 多：认证缺失、双轨冲突、CRON.md 引用死脚本）
- 可维护性：2（systemd vs gunicorn 双轨、CRON 文档漂移、monitor 失效）
- 性能：3（端口冲突、单 worker、写端点无 rate-limit）
- 文档：2（CRON.md 3 处不一致，handover note 残留）
- **总评：2**（可生产运行但安全态势堪忧，必须在下一迭代修认证 + 清理双轨）
