# AUTO-STOCK 全量代码审查 — 主报告

> 审查日期：2026-06-14  
> 审查范围：因子系统 / 数据流水线 / 回测系统（设计+结果）/ Web 前端 / 报告+流水线 / 持仓+信号 / Cron+部署 / 横向  
> 审查方式：8 个并行子 agent + 1 轮收尾（429 限流后部分复用草稿）  
> 子报告：见 `audit/2026-06-14-full-review/0X-*/final/SUBREPORT-*.md`

---

## 0. 总评

| 维度 | P0 | P1 | P2 | P3 | 评分 | 可信度 |
|------|----|----|----|----|------|--------|
| 因子系统 | 3 | 4 | 6 | 2 | 3/5 | 因 weight 字段未生效，总分近似正确 |
| 数据流水线 | 5 | 6 | 7 | 0 | 3/5 | 静默降级风险高 |
| 回测系统（设计） | **6** | 17 | 18 | 4 | **2/5** | **结果大概率被高估** |
| 回测系统（结果） | 3 | 3 | 2 | 0 | 3/5 | 数字可复现但可比性差 |
| Web 前端 | 0 | 8 | 8 | 3 | 3/5 | 工程债务重但无 P0 |
| 报告+流水线 | — | — | — | — | 21KB | 见子报告 |
| 持仓+信号 | — | — | — | — | 17.7KB | 见子报告 |
| Cron+部署 | 4 | 5 | 7 | 3 | 2/5 | **安全态势堪忧** |
| 横向 | 2 | 3 | 7 | 3 | 2/5 | 安全+工程债务 |
| **合计** | **23+** | **46+** | **55+** | **15+** | **整体 2.5/5** | — |

**一句话总结**：系统能跑、功能大致对齐，但**回测结论不可全信 + 安全态势堪忧 + 数据静默降级**，是"功能性 MVP 已上线、生产化尚有距离"的状态。

---

## 1. ⚠️ 用户最关心：回测数据/方法是否靠谱？

**结论：已完成的回测结论需要打折看，部分关键数字甚至会误导决策。**

### 1.1 设计层（前视偏差）—— `SUBREPORT-backtest-engine.md`
三项 P0 叠加导致**系统性高估**：
- **A1+A2+A3**：scored 模式用了"今日 19:00 算的评分"回测"今日开盘前决策"——`financial_factor` 在 4-30 前用 Q1 季报做 Q1 季报披露后的回测决策，**用了未来才公开的数据**。
- **A4+C3+E6**：调仓/信号买入价用 T 日收盘价而非 T+1 开盘价。**隔夜跳空未建模**——实际你用 T 日的信号，T+1 开盘才能买，但回测里按 T 日收盘成交。
- **E1**：`print_signal_report`/`export_signal_trades` 在源码里没定义，`run_signal.py` 实际是 ImportError 死代码。CLAUDE.md 说"信号策略（规划中）"——其实是"半成品混入主干"。

**叠加后果**：2026 年 +5.43% 超额、2025 年 +32.88% 总收益（注意这是"跑输基准 -2.94%"，不是超额）大概率被**显著高估**。**建议把"超额"理解为"乐观上界"**。

### 1.2 结果层（数据与可比性）—— `SUBREPORT-backtest-results.md`
- **CLAUDE.md 表述误导**：原文写"2025 总收益+32.88%（基准+35.82%）"——读者会读成"超额 +35.82%"，**实际是跑输基准 -2.94%**。报告 README 内部数字正确，是 CLAUDE.md 顶部表达歧义。
- **股票池不一致**：2022/2023/2026 用 200 只自选股，2024/2025 用 1385 只全市场股。"按财报评分排序五年累计 478.53 万"在方法论上**不成立**（不同时段不可直接相加）。
- **样本量不足**：2026 年 9 因子 21 天只有 3 个调仓周期、60 笔交易，IC_IR 统计上完全不可靠。
- **数字抽查全部通过**：调仓次数、交易笔数与 README 报告一致——结论真实，**只是不可比**。

### 1.3 建议的"修复路线"
1. **立即**：把 scored 模式的"今日数据"限定到 T-1，财务因子改成"上一已披露季度"截断。
2. **2 周内**：所有回测调仓价改 T+1 开盘价 + 滑点假设（如 0.1%）。
3. **长期**：补一份"前视偏差修正版"回测，**重做全部历史数字**。

详见 `03-backtest-system/final/SUBREPORT-backtest-engine.md` 的 A 节和 E 节。

---

## 2. 🔒 P0 安全清单（必须立即处理）

按紧急度排序：

| # | 问题 | 位置 | 后果 |
|---|------|------|------|
| S1 | API 完全无认证（50+ 路由） | `api/main.py` | 任何人都能调 buy/sell/delete-trade |
| S2 | TUSHARE_TOKEN 真实值已 commit 到 git 历史 | `config/config.py:2` | 需轮换 + `git filter-repo` 清除 |
| S3 | `feedbacks.json` 含真实用户 IP（183.222.203.200）且 git 跟踪 | `feedbacks.json` | 隐私违规 + 改 SQLite + 加 `.gitignore` |
| S4 | systemd uvicorn vs gunicorn 双服务争抢 8000 端口 | `start_financial_score.sh` + systemd | 监控脚本失效 |
| S5 | CLI path traversal：`main.py run_batch` 把用户输入拼到 filename | `main.py:run_batch` | 任意路径写入/静默覆盖 |
| S6 | `daily_report.py.bak` 和 `.fix` 字节相同（100KB+ 死代码） | `scripts/` | 清理 |

---

## 3. 🐛 P0 功能/正确性清单

| # | 问题 | 位置 | 后果 |
|---|------|------|------|
| F1 | `daily_change_factor` 放量加分逻辑永远失效（找 `成交量`，实际是 `成交额`） | `src/factors/daily_change_factor.py:95,107-111` | 死代码 |
| F2 | `scoring_engine.aggregate_scores()` 和 `factor_manager.discover_and_run()` 全代码库无调用方 | `src/core/scoring_engine.py` 等 | 死代码，weight 字段从未被读 |
| F3 | `dp_diff_factor.py` 文件名误导（类名 `RelativeStrengthFactor`，是 YTD 相对大盘） | `src/factors/dp_diff_factor.py` | 命名 vs 语义不符 |
| F4 | `src/data_fetcher.py` 是 0 字节空文件，但 `src/sel.py:1` 仍 import 其函数 | `src/data_fetcher.py` | import 即崩（如果 sel.py 被加载） |
| F5 | `data/industry/stock_industry_mapping.csv` 33 天未更新 | `data/industry/` | 5-6月新上市股票 IndustryDiffFactor 全部 0 分 |
| F6 | `get_market_change()` 异常返回 0.0 → `dp_diff_factor` 把"今年相对大盘"错算为 `stock_ret` | `src/utils.py:64-66` | 全部股票看起来跑赢大盘 |
| F7 | `data_manager.py` 存在两个 `get_fund_flow_5day` 定义互相覆盖 | `data_manager.py:384,426` | 后定义覆盖前定义，行为不确定 |
| F8 | `data/calendar/trade_days.csv` mtime 永不会动 | — | 2027 年起全错 |
| F9 | 财务因子 final 截断 `[-10, 20]` 在两端都会触发（理论上界 21.25 / 下界 −11.25） | `financial_factor.py` | 实际可超过 20 |
| F10 | 前导零修复 `08e6abb` 只修了 kline_analyzer，`api/main.py:38,91,639,670,693` + `main.py:61` 4 处仍裸 `pd.read_csv` | 多处 | 深市股票 code 仍可能丢前导零 |

---

## 4. 📊 子报告交叉印证

| 主题 | 在哪些子报告出现 | 性质 |
|------|----------------|------|
| 前视偏差 | 回测设计 + 回测结果 | **核心可信度问题** |
| 安全/认证 | Cron+部署 + 横向 | **生产化瓶颈** |
| `dp_diff_factor` 错 | 因子系统 + 数据流水线 | **同一问题两面** |
| 前导零 | 横向（`08e6abb` 修一半） | 已知 bug 漏修 |
| 死代码/半成品 | 因子（scoring/factor_manager）+ 横向（data_fetcher/sel.py/config.py）+ 回测（run_signal） | 清理优先级高 |
| 文档与实现漂移 | 横向 + 回测结果（CLAUDE.md）+ Cron（CRON.md） | 需要一次文档刷新 |

---

## 5. 改进路线（详见 ROADMAP.md）

按 4 个时间窗口划分：

- **🔴 立即（24h）**：6 项安全 + 2 项数据完整性（S1-S6 + F4）
- **🟠 1 周内**：回测前视偏差修复（F1/A1-A4）+ CLAUDE.md 表述修正
- **🟡 1 月内**：死代码清理、文档刷新、API 认证补全
- **🟢 长期**：补一份"前视偏差修正版"重做历史回测

详细任务清单见 `00-index/ROADMAP.md`。

---

## 6. 完整子报告索引

| # | 主题 | 文件 | 字节 |
|---|------|------|------|
| 2 | 因子系统 | `01-factor-system/final/SUBREPORT-factors.md` | — |
| 3 | 数据流水线 | `02-data-pipeline/final/SUBREPORT-data-pipeline.md` | — |
| 4 | 回测系统设计 | `03-backtest-system/final/SUBREPORT-backtest-engine.md` | — |
| 4b | 回测系统结果 | `03-backtest-system/final/SUBREPORT-backtest-results.md` | — |
| 5 | Web 前端 | `04-web-frontend/final/SUBREPORT-web-frontend.md` | — |
| 6 | 报告+流水线 | `05-report-system/final/SUBREPORT-report-pipeline.md` | 21KB |
| 7 | 持仓+信号 | `06-portfolio-and-signals/final/SUBREPORT-portfolio-signals.md` | 17.7KB |
| 8 | Cron+部署 | `07-cron-and-deploy/final/SUBREPORT-cron-deploy.md` | — |
| 9 | 横向 | `09-cross-cutting/final/SUBREPORT-cross-cutting.md` | — |

---

## 7. 审查方法说明 / 局限

- 9 个子 agent 全部完成，其中 3 个在 429 限流中部分产物已落盘，由收尾 agent 复用草稿
- **没有运行**代码验证：所有发现基于静态阅读（`Read` + `Grep`）
- **没有做**性能基准测试：所有性能问题来自代码审查推断
- **没有做**真实接口测试：API 路由只看了文件定义
- 因此：P0 中**安全类（S1-S4）已可信**（代码明显缺 auth），**功能性 P0（F1-F10）需用最小复现脚本二次确认**——已列入 ROADMAP
