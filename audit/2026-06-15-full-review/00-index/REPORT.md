# AUTO-STOCK 全量复查 — 主报告

> 实际审查日期：**2026-06-16**（目录名沿用 2026-06-15-full-review 作为内部标识）  
> 上次审查：`audit/2026-06-14-full-review/`（实际 2026-06-15 上午做的）  
> 重点关注：stock-system 的信号版本切换 + 卖信号集成  
> 审查方式：9 个子 agent 并行 + 与上次 P0 对照

---

## 0. 一句话结论

**24 小时里修了 4/6 主体 P0，但**：
1. **回测系统的 8 个 P0 一个没动**——V2 新增的逻辑完整继承前视偏差，"年均 +21.6%"等数字系统性高估
2. **stock-system 信号系统的"卖信号集成"是半成品**——calc_signals 算 SELL 写 CSV，sim_trader 根本不看 SELL 列，独立用 K 线扫描做止盈；且 V1/V2 策略双源不联通，前端切 V2 实际跑 V1 默认参数
3. **evening_pipeline.sh 从 4 步缩水到 3 步**——calc_signals / sim_trader 都不再被流水线调用，依赖外部 cron，仓库内**不可复现**

**整体评价**：2.5/5（与上次持平）—— 安全态势有进步（鉴权、env、部署），但**业务核心的可信度问题没改善**。

---

## 1. 子报告汇总表

| 维度 | P0 | P1 | P2 | P3 | 评分 | 变化 |
|------|----|----|----|----|------|------|
| 因子系统 | 3 | 6 | 7 | 2 | 2/5 | ⬇️ |
| 数据流水线 | 5 | 4 | 4 | 1 | — | ➡️ |
| 回测+V2 | 9 | 6 | 7 | 2 | 2/5 | ⬇️（P0 上升） |
| **stock-system 信号【重点】** | 4 | 5 | 4 | 3 | 3/5 | ➡️（V1/V2 优 / 卖信号半成品） |
| Web 前端 | 3 | 10 | 9 | 4 | 3/5 | ➡️ |
| 报告+流水线 | 5 | 7 | 3 | 3 | 2/5 | ⬇️（pipeline 缩水） |
| 持仓+信号 | 5 | 9 | 4 | 2 | 2.5/5 | ➡️ |
| Cron+部署 | 2 | 3 | 7 | 3 | 3/5 | ⬆️ |
| 横向 | 4 | 3 | 6 | 3 | 2/5 | ➡️ |
| **合计** | **40** | **53** | **51** | **23** | **2.5/5** | — |

---

## 2. 与上次审查（2026-06-14）P0 对比表

### 已修复（4 项）✅
| 编号 | 主题 | 证据 |
|------|------|------|
| S1 | API 鉴权 | api/security.py + 11 个 Depends + token 流程上线 |
| S2 | TUSHARE_TOKEN | 已轮换 + env 化 + git filter-repo（但有暗礁，见下） |
| S4 | systemd vs gunicorn 双服务 | gunicorn 已停，仅 systemd uvicorn |
| S6 | 死文件 .bak/.fix | 已建 .trash/2026-06-15/ 软删机制 |
| F4 | data_fetcher + sel.py 死 import | 文件已删（**但 src/backtester.py / src/tracker.py 还有 import**，F4 半修复） |
| F5（部分） | 行业映射 | mapping 仍 34 天未动（仅 change CSV 每天 cron 刷） |

### 仍未修复（15+ 项）❌
| 编号 | 主题 | 备注 |
|------|------|------|
| F1 | daily_change 找 `成交量` 而非 `成交额` | 实测仍 `volume_ratio=1.0` 死代码 |
| F2 | scoring_engine / factor_manager 死代码 | main.py 仍 `total_score += factor_score` |
| F3 | dp_diff_factor 命名误导 | 文件/类名/全局 cache 原样未动 |
| F6 | get_market_change 异常返 0.0 | 仍 0.0 |
| F7 | get_fund_flow_5day 双定义 | data_manager.py:384 + :426 |
| F8 | trade_days.csv 硬编码 | 2027+ 未续期 |
| F9 | 财务因子 final 截断边界 | 上下界仍超 |
| F10 | 前导零 4→7 处 | 4 → 7 处，**恶化** |
| S3 | feedbacks.json IP 隐私 | 0 改动，仍含 `183.222.203.200` |
| S5 | main.py path traversal | 0 改动 |
| S7 | requirements.txt | 仍 3 行 |
| S8 | CLI EOFError | 4 处 input() 无 try |
| 回测 A1 | scored 模式 T 日数据 | 完整继承至 V2 |
| 回测 A2 | financial_factor 3 季度窗口 | fallback 路径仍在 |
| 回测 A4 | 调仓价 T+1 开盘 | get_next_trade_day 已实现但无人调用 |
| 回测 E1 | print_signal_report 未定义 | 实测 run_signal.py 仍 ImportError |
| 报告 | 节假日跳过逻辑 | 整段被删，**恶化** |
| 报告 | daily_report 400KB JSON | 仍 418KB |
| 持仓 | accounts.strategy_id 漂移 | 实测 UPDATE 仍报错 no such column |
| 持仓 | TOCTOU 资金竞态 | trading.py:142-167 原样未动 |
| 持仓 | delete_trade 反转错位 | trading.py:582-586 死循环 |
| 部署 | CRON.md 死脚本引用 | CRON.md:11 + MAINTENANCE.md:114 仍写 `daily_download.sh` |
| 部署 | API str(e) 泄漏 | 至少 12 处未改 |

### 恶化（3 项）⬇️
| 编号 | 主题 | 变化 |
|------|------|------|
| F10 | 前导零修复 | 4 处 → 7 处 |
| 报告 | 节假日跳过 | 整段 grep 逻辑被删 |
| 报告 | sim_trader 失败处理 | 静默吞 → 整个被从流水线删（更糟） |
| 数据 F4 | 死 import | 删了 data_fetcher 但没修 backtester.py/tracker.py 的 import |

---

## 3. 本轮新增 P0（用户特别要求关注）

### A. stock-system 信号【本轮重点】
1. **三个核心脚本 untracked**：`calc_signals.py` / `sim_trader.py` / `src/backtest/signal_engine.py` 全是 `??` 状态，从未 commit
2. **evening_pipeline.sh 不调信号计算**（与 #6 报告+流水线 P0-1 同源）
3. **卖信号"集成"是半成品**：
   - `calc_signals.generate_sell_signals()` 算 SELL 写 CSV
   - `sim_trader.py:244` 只看 `signal == 'BUY'`，**不看 SELL**
   - 独立用 K 线扫描做止盈止损
   - 两套数据源不同步（score_price_history vs 原始 K 线）、判定时机不同
4. **实盘（REAL）账户完全无监控**：
   - `calc_signals.py:291` 硬编码 `sim_account = db.get_account_by_mode('SIM')`
   - `sim_trader.py:318-332` 拒绝 REAL 模式
   - 用户 10 万本金实盘持仓无任何自动平仓机制

### B. 策略双源不联通（最危险）
- `portfolio.db.strategies` 表只有 V1 字段（schema 漂移）
- `src/backtest/strategies.py` `STRATEGIES` 注册表有 V2 字段（含 `first_break_only` / `max_pos_pct_basis` / `build_days`）
- `sim_trader.py:176` 读 DB **忽略注册表**
- **前端切 V2 实际跑 V1 默认参数（20%/8%）**
- 用户感知的"V2 行为" ≠ 实际跑的策略

### C. V2 完整继承前视偏差
- V2 用 `load_backtest_data` 读 `scores_*.csv` 预计算评分（含 T 日）
- `signal_engine.py:307 bp = get_price(code, date)` 仍 T 日收盘
- V2 自身有"首日盲区"新 bug（i=0 跳过整个检查）
- **"年均 +21.6%"等数字系统性高估**——用户决策依据存疑

### D. S2 修复暗礁
- `.git.backup-before-filter-repo/` 仍在工作树（2MB 完整 git 仓库）
- 含未抹除旧 token（虽然本机已废）
- 任何 `tar` / `docker COPY` / `upload-artifact` / `r2_backup.py` 都会重新泄漏
- **filter-repo 的修复不彻底**

### E. CORS + 跨域仍可利用
- 实测 `Origin: https://evil.com` 仍被允许（`allow_origins=["*"]` + `allow_credentials=True`）
- 所有 GET 端点公开数据可被任意站点代理抓取

### F. 其他新发现
- **`Strategies.vue:37-40` 三年回测数字硬编码**（+18%/+32%/+15%），应从后端拉
- **`docs/stock-system/`** 新文档站 7 文件，但 git 未跟踪
- **`meta/`** 3 文件 0 代码引用，`snapshot_manifest.csv` 停更 26 天
- **HANDOVER.md（352 行）严重过期**——说"阶段五待部署"但 stock-system 已上线
- **三份文档（HANDOVER/MAINTENANCE/CLAUDE）80% 重复**
- **`miniprogram/`** 微信小程序 CLAUDE.md 写得很完整但 pages/webview/ 4 文件未注册 = 死代码

---

## 4. 重点关注：stock-system 信号（用户特别要求）

### V1/V2 切换
- ✅ **合理**：`strategies.py` 用 `frozen dataclass` + 22 行顶部注释堪称教科书
- ✅ 前端三层防串数据：localStorage + API `?version=` + 缓存键加 version
- ⚠️ P1: `Signals.vue:177-178` 排序字段硬编码（v2→finance_score, v1→avg7_score），违背"加 v3 只改注册表"承诺

### 卖信号集成
- ⚠️ **半成品/有大坑**：
  - calc_signals 算的 SELL **未被 sim_trader 消费**
  - sim_trader 用 K 线扫描做止盈止损（独立于 SELL）
  - **数据源不同步**（score vs K 线）+ **判定时机不同**
  - 实盘（REAL）账户完全无监控
  - 持仓 `current_price` 经常是 1.0/None，return_pct 算式脆弱

### evening_pipeline.sh
- ❌ **缩水**：从 4 步 → 3 步
- ❌ **calc_signals / sim_trader 不再被调用**
- ⚠️ 整个信号系统在仓库内**不可复现**，依赖外部 cron

### 策略双源不联通（最危险）
- 见 §3.B
- 前端切 V2 实际跑 V1 参数
- **用户的"V2 行为" ≠ 实际跑的策略**

### 综合评分
- **V1/V2 切换**：3.5/5（工程化程度高，但前端写死排序字段、未接 cron）
- **卖信号集成**：2/5（calc_signals 算 SELL 无误，但下游消费完全缺失）

---

## 5. 与上次审查对比 — Top-3 重点

| 主题 | 上次 | 本次 | 评价 |
|------|------|------|------|
| **回测可信度** | 不可信（3 P0） | **更不可信**（9 P0，V2 继承） | ⬇️ |
| **信号系统** | 部分功能（仅买信号） | V1/V2 切换 + 卖信号 **半成品**（最危险 P0：策略双源不联通） | ⚠️ |
| **安全态势** | 多项 P0 | 4/6 主体修（S1/S2/S4/S6），但 CORS 仍跨域、S2 暗礁 | ⬆️ |

---

## 6. 改进路线（详见 ROADMAP.md）

- **🔴 立即（24h）**：5 项 — 删 .git.backup-before-filter-repo 暗礁 + 修 accounts.strategy_id 漂移（API 直接报错）+ 修 setStrategyVersion 清缓存粒度 + 修 main.py s_score 死计算 + 修前导零扩散
- **🟠 1 周内（5d）**：回测 P0 修复（A1/A4）+ 策略双源联通 + SELL 信号端到端 + 数据流水线 5 个 P0 + reports JSON 418KB
- **🟡 1 月内**：V1/V2 业务联调 / 文档去重 / 安全补全 / Web 工程质量
- **🟢 长期**：回测 v2 拆分 / 跨机同步策略

---

## 7. 给用户的关键判断

### 您的"实盘策略决策"（2026-06-15，10 万本金 v1+20%/8%/3 天，3 年年均 +21.6%）
- **底层回测数据系统性高估**（A1/A2/A4 三项叠加 + V2 继承）
- **策略双源不联通**——您以为是 v1+20%/8%，sim_trader 跑的可能不一样（DB schema 漂移）
- **信号未接 cron**——`stock.auto-claw.top/signals` 显示的可能是陈旧数据
- **建议**：先把"暗礁"和"不可信"标记清楚，等回测 P0 修了再重做决策

### 您最关心的"卖信号集成"
- **calc_signals 写 SELL 是新的**
- **sim_trader 消费 SELL 是空白的**
- **实盘账户完全无监控**（10 万本金裸奔）
- **建议**：要么把 sim_trader 改造成消费 SELL，要么明确"止盈止损由 sim_trader 独立做，calc_signals 只展示"

---

## 8. 完整子报告索引

| # | 主题 | 文件 | 字节 |
|---|------|------|------|
| 1 | 因子系统 | `01-factor-system/final/SUBREPORT-factors.md` | — |
| 2 | 数据流水线 | `02-data-pipeline/final/SUBREPORT-data-pipeline.md` | — |
| 3 | 回测+V2 | `03-backtest-system/final/SUBREPORT-backtest-engine.md` | — |
| 4 | **stock-system 信号** | `04-stock-system-signals/final/SUBREPORT-stock-system-signals.md` | — |
| 5 | Web 前端 | `05-web-frontend/final/SUBREPORT-web-frontend.md` | — |
| 6 | 报告+流水线 | `06-report-pipeline/final/SUBREPORT-report-pipeline.md` | — |
| 7 | 持仓+信号 | `07-portfolio/final/SUBREPORT-portfolio.md` | — |
| 8 | Cron+部署 | `08-cron-deploy/final/SUBREPORT-cron-deploy.md` | — |
| 9 | 横向 | `09-cross-cutting/final/SUBREPORT-cross-cutting.md` | — |

---

## 9. 审查方法说明 / 局限

- 9 个子 agent 全部完成，**无 429 限流**
- **没有运行**代码验证：所有发现基于静态阅读
- **没有做**性能基准测试
- **没有做**真实接口测试
- P0 中**安全类**已可信，**功能类**建议最小复现脚本二次确认
- **用户原话"重点关注 stock-system"已重点处理**（子任务 4 + 子任务 7 持仓+信号 双向覆盖）
