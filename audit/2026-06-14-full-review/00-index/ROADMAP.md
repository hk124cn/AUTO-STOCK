# 改进路线图 — AUTO-STOCK 2026-06-14 全量审查

> 与 `00-index/REPORT.md` 配套使用。每项含：编号 / 标题 / 严重度 / 估计工作量 / 子报告位置

---

## 🔴 立即（24h 内） — 6 项安全 + 2 项数据完整性

### 安全
1. **S1 — 给 API 加认证** ⏱ 4h
   - 现状：`api/main.py` 50+ 路由（含 buy/sell/delete-trade/update-capital）全部无 auth
   - 建议：`Depends(verify_api_key)` 装饰所有写端点；或 nginx IP 白名单
   - 风险：不修复前**不建议任何生产环境暴露** `stock.auto-claw.top/api/`
   - 详见：07-cron-and-deploy/SUBREPORT-cron-deploy.md
   - **进度（2026-06-15）✅ 已完成**：实现"单密码 + 24h token"模式。改动 9 个文件：
     - 后端：`api/security.py`（新建，含 login/verify_token/cleanup）、`api/main.py`（+登录端点 +11 个 Depends）、`config/config.py`（+API_PASSWORD）
     - 前端：`web/stock-system/src/auth.js`（新建）、`PasswordModal.vue`（新建）、`authModal.js`（新建）、`loader.js`（postData→authedFetch）、`main.js`（注册）、`App.vue`（挂全局弹窗）、`Portfolio.vue`（6 处 fetch→authedFetch）、`Strategies.vue`（4 处 fetch→authedFetch）
     - 8 个 curl 场景全部按预期（读端点公开、写端点无 token 401、错密码 401、对密码 200+token、带 token 写 422 即"通过 token 进入业务校验"、feedback 仍公开、错 token 401、monitor 读端点 200）
     - 默认密码：`OLD_API_PASSWORD_REDACTED`（建议改 + 通过 `STOCK_API_PASSWORD` 环境变量覆盖，避免 commit）
     - 计划文件：`/home/admin/.claude/plans/sprightly-leaping-umbrella.md`
   - **线上部署 ✅**：`npm run build` 完成（599 modules, 26.4s），dist mtime 2026-06-15 10:41；nginx 直接 serve dist，端到端验证：读 200 / 写无 token 401 / 登录 200 / 带 token 写 422（通过 token 校验）

2. **S2 — 轮换 TUSHARE_TOKEN + git 历史清除** ⏱ 1h
   - 现状：`config/config.py:2` 含真实 token
   - 建议：① 在 tushare 控制台轮换 ② `git filter-repo --invert-paths --path config/config.py` ③ `.gitignore` 加 `config/*.py`（保留 `config.example.py`）
   - 详见：09-cross-cutting/SUBREPORT-cross-cutting.md
   - **进度（2026-06-15）✅ 已完成**：
     - 用户在 tushare.pro 重置 token，旧 token `616f037d...` 立刻失效，新 token `cfb700db...` 已写入 `.env`
     - `config/config.py` 改为从 `.env` 读 TUSHARE_TOKEN + API_PASSWORD（轻量 dotenv 加载器，不依赖 python-dotenv）
     - 新增 `.env.example` 模板（git 跟踪），`.env` 被 `.gitignore` 排除（验证：`git check-ignore .env` 通过）
     - `deploy/stock-api.service` 加 `EnvironmentFile=-/home/admin/AUTO-STOCK/.env`
     - 多机协作：本地/云服务器各自维护 `.env`，互不影响
     - `git filter-repo --replace-text` 把旧 token 和旧 API_PASSWORD 从所有历史 commit 替换为占位符
     - 删除含旧 token 的遗留分支 `origin/codex/check-status-of-last-pr`
     - **GitHub 验证**：所有远端 ref 中旧 token 出现 **0** 次，旧 API_PASSWORD 出现 **0** 次
     - 备份：`.git.backup-before-filter-repo/`（万一需回滚）
     - commit: `3db04c0 feat(security): API 加密码鉴权 + 密钥 env 化`


3. **S3 — `feedbacks.json` 隐私治理** ⏱ 2h
   - 现状：含真实用户 IP（`183.222.203.200`）+ git 跟踪 + 并发不安全
   - 建议：① 改 SQLite（与 `portfolio.db` 同模式）② `.gitignore` 加 `feedbacks.json` ③ 旧文件 `git filter-repo` 清除
   - 详见：09-cross-cutting/SUBREPORT-cross-cutting.md

4. **S4 — 统一 API 启动方式** ⏱ 1h
   - 现状：systemd uvicorn + `start_financial_score.sh` gunicorn 双服务争抢 8000 端口
   - 建议：保留 systemd，删除 gunicorn 启动逻辑；`monitor_api.sh` 改查 uvicorn

5. **S5 — 修 CLI path traversal** ⏱ 30min
   - 现状：`main.py run_batch` 把 `in_fname` 拼到 filename
   - 建议：`os.path.basename(in_fname)` + 白名单允许目录

6. **S6 — 清理 bak/fix 死文件** ⏱ 10min
   - `scripts/daily_report.py.bak` 与 `.fix` 字节完全相同，删一份
   - `api/main.py.bak2` 含 `MX_APIKEY`，必须删

### 数据
7. **F4 — 修 `src/data_fetcher.py` 空文件 + `sel.py` 死 import** ⏱ 30min
   - 要么填实 data_fetcher.py，要么删 sel.py 的 import（`grep -r "from src.data_fetcher" .` 看实际调用）

8. **F5 — 行业映射数据** ⏱ 10min
   - 现状：`data/industry/stock_industry_mapping.csv` mtime 2026-05-12，33 天未更新
   - 建议：加进 `evening_pipeline.sh` 的步骤 0（或单独的 cron），加 staleness 检查（>14 天报警）

---

## 🟠 1 周内（最关键的"可信度修复"）

### 回测前视偏差（用户最关心）
9. **A1 — scored 模式"今日数据"截断** ⏱ 1d
   - 现状：scored 模式用当天 19:00 算的评分回测当天开盘前决策
   - 建议：scored 模式强制只用 T-1 及之前的 batch_result

10. **A2 — 财务因子 3 季度窗口修正** ⏱ 1d
    - 现状：4-30 前用 Q1 数据做 Q1 季报披露后的回测决策
    - 建议：改用"上一已披露季度"（披露日前 1 季度，披露日后最新季度）

11. **A4 — 调仓价改 T+1 开盘价 + 滑点** ⏱ 2d
    - 现状：调仓买入价用 T 日收盘价
    - 建议：所有 backtest engine 的 `execute_price` 改 T+1 open + 0.1% 滑点

12. **重做回测** ⏱ 1d
    - 修了 A1+A2+A4 后，重跑 2025_5日_1385_top 和 2026_5日_1385_9因子
    - 输出"前视偏差修正版"数字，更新 CLAUDE.md

### 代码
13. **F1 — `daily_change_factor` 放量加分列名修正** ⏱ 10min
    - 改 `if '成交量' in columns` → `if '成交额' in columns`

14. **CLAUDE.md 表述修正** ⏱ 10min
    - "2025 总收益+32.88%（基准+35.82%）" 改写为：
      > 2025 全年 5 因子策略 +32.88%，**跑输等权基准 -2.94%**（基准 +35.82%）

15. **F10 — 修前导零 4 处遗留** ⏱ 30min
    - `api/main.py:38,91,639,670,693` + `main.py:61` 全部加 `dtype={'code': str}`

16. **F6/F7 — `get_market_change` 异常处理 + `get_fund_flow_5day` 重名** ⏱ 30min
    - 异常时不要返回 0.0，抛错或返回 None 并强制调用方处理
    - 删 `data_manager.py:384` 的旧定义

---

## 🟡 1 月内（清理 + 文档刷新）

### 死代码清理
17. **F2 — `scoring_engine` / `factor_manager` 死代码** ⏱ 1d
    - 现状：全代码库 grep 无任何调用方；9 个因子的 `weight` 字段从未被读取
    - 二选一：① 让 main.py 走 `factor_manager.discover_and_run()`，weight 真正生效 ② 删 scoring_engine 和 factor_manager
    - **建议走①**（修复而非删除）：9 因子 weight 真正生效是工程化的一步

18. **`data_fetcher.py` / `sel.py` 清理** ⏱ 1h
    - 上面 F4 修了一半，这里确认 sel.py 是否还需要

19. **`src/config.py` 空文件** ⏱ 5min
    - git 跟踪但 0 字节，删

20. **`run_signal.py` 半成品** ⏱ 4h
    - 现状：`print_signal_report` / `export_signal_trades` 在源码未定义
    - 要么补实现，要么删 `run_signal.py`（CLAUDE.md 已标"规划中"）

21. **`hy_diff_factor.py.bak`** ⏱ 5min
    - 残留旧版，删

22. **Web 项目 3 处 `.bak` / `.backup` 文件** ⏱ 5min

23. **整个 `web/` 根目录旧 Flask/Vue 前端** ⏱ 30min
    - 移到 `web/_legacy/` 或直接 git rm

### 文档刷新
24. **CLAUDE.md 整体刷新** ⏱ 2h
    - 修正跑输基准表述
    - 加上 5 月以来的 9 因子全部就绪
    - 加上 stock-system nginx 部署
    - 修正各项命令的实际行为

25. **CRON.md 重写** ⏱ 30min
    - 删 `daily_download.sh`（不存在）
    - 修正 `daily_data_fetch.py` docstring 写"0 16"实际"0 17"
    - 补充 `monitor_api.sh` 调度（如启用）

26. **HANDOVER.md 过期内容** ⏱ 1h
    - 校对阶段一~五是否仍然成立

### 安全补全
27. **CORS 收紧** ⏱ 30min
    - `allow_origins=["*"]` 改为白名单域名（auto-claw.top 等）

28. **api 端口改 127.0.0.1 + nginx 反代** ⏱ 30min
    - 现状：uvicorn 绑 0.0.0.0:8000
    - 建议：改 127.0.0.1，由 nginx 反代

29. **加 monitor_api.sh 的 cron 调度** ⏱ 30min
    - 现状：监控脚本从未被任何 cron 调度
    - 建议：`*/5 * * * * /home/admin/AUTO-STOCK/scripts/monitor_api.sh`

### Web 工程质量
30. **stock-alert dist 392MB** ⏱ 4h
    - 现状：dist 与数据未分离，每次手动复制
    - 建议：nginx alias 共享 `AUTO-STOCK/data/price/`，与 stock-system.conf 一致

31. **Home.vue 14 处 console.log** ⏱ 30min

32. **Dashboard.vue `clearAllCache()` 强制清缓存** ⏱ 1h
    - 现状：破坏 cache.js 的 T1_DATA "日加载 1 次"设计
    - 建议：把缓存策略改 configurable，或去掉强制 clear

---

## 🟢 长期（架构级）

33. **补一份"前视偏差修正版"重做历史回测** ⏱ 1w
    - 用 live 模式（实时计算历史因子）+ 修后 A1+A2+A4
    - 输出新的 2022/2023/2024/2025/2026 全部回测
    - 与旧版做差异分析

34. **回测引擎 v2 拆分** ⏱ 1w
    - 把 backtest 拆成：① 数据层 ② 因子层（独立可测试）③ 组合层 ④ 报告层
    - 加单元测试覆盖每个 IC/分位收益计算

35. **Web 三件套统一数据加载层** ⏱ 3d
    - 三个项目各写一份 loader.js 重复
    - 抽到 `web/_shared/loader/` 共享

36. **`sync_repo.sh` 静默回退** ⏱ 1d
    - 现状：`git pull` 失败时可能静默回退，掩盖问题
    - 建议：失败硬退出

37. **`requirements.txt` 补齐** ⏱ 10min
    - 当前只 3 行，缺 fastapi/uvicorn/pydantic/starlette/pytest

---

## 工作量统计

- 🔴 立即：~10h（1 个工作日）
- 🟠 1 周：~5d
- 🟡 1 月：~10d
- 🟢 长期：~4w

---

## 审查质量声明

- P0 安全类（S1-S4）已可信，代码明显缺 auth，**不需要二次确认**
- P0 功能类（F1-F10）建议**用最小复现脚本二次确认**后修复（已列入 1 周内）
- P1-P3 为建议项，可按业务优先级取舍
