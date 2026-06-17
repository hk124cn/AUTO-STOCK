# AUTO-STOCK 第三次审查主报告

> 实际审查日期：**2026-06-16**  
> 距离上次审查：约 8 小时  
> 上次审查：`audit/2026-06-15-full-review/00-index/REPORT.md`  
> 对方回应：`audit/2026-06-15-full-review/00-index/RESPONSE.md`（18KB）  
> 重点：**验证 RESPONSE.md 承诺的 9 项修复 + 找新引入问题**

---

## 0. 一句话结论

**RESPONSE.md 描述的修复思路正确，但代码落地 50% 失败**：

✅ **真修了**（5 项）：
- T-1 评分（scored 模式）
- T+1 开盘 + 0.1% 滑点
- 冷却期（scored 模式）
- 流水线 step 4/5 加了
- 横向 P0（.git.backup 删、CORS 变量、str(e) 脱敏、.gitignore 修齐）

❌ **没修或引入新问题**（13+ 项）：
- **`calc_signals.py 启动即崩**`（__init__.py 仍 import 旧 API `STRATEGIES`）—— 流水线 step 4/5 跑必失败
- **SELL 字段名漂移**（positions 表无 `avg_cost` / `buy_price`）—— SELL 信号永远不生成
- **buy_date 格式错位**（`"20260615 08:55:00"` vs K 线 `"20260615"`）—— K 线扫描区间为空
- **sim_trader `both_triggered` NameError** —— 启动崩
- **live 模式完全没修前视偏差**（engine.py:162 仍用 T 日评分）
- **V2 (signal_engine.py) 也没修**（T-1/T+1/滑点全无）
- **accounts.strategy_id 漂移未修**（实测 `UPDATE accounts SET strategy_id=2` 仍 `no such column`）
- **delete_trade 死循环未修**（`if trade['shares'] <= 0: break` 还在）
- **backtester.py / tracker.py 未删**（仍存在）
- **TOCTOU 未修**（无 EXCLUSIVE / 原子 UPDATE）
- **PUT /strategies/active 无鉴权**（新发现）
- **_active_config 无持久化**（重启即丢）
- **gunicorn 多 worker 配置不一致**（PUT 落 worker 1，GET 落 worker 2）

**整体评价**：2/5（**退步 0.5 分**）
- 横向 / 流水线骨架有进步（5 项真修）
- **核心信号/回测链路全断**（calc_signals 启动即崩，SELL 永远不生成）
- 用户的 **5 只实盘持仓完全无监控**（sim_trader 拒 REAL，calc_signals 硬编码 SIM）

---

## 1. 真修了（5 项）✅

| 主题 | 证据 | 来源 |
|------|------|------|
| T-1 评分（scored） | `engine.py:240,311` 显式"评分日 = T-1"，line 322 "加载评分（用 T-1 日的 batch_result）"，line 316 首日无 T-1 自动跳过 | 实测 + agent #3 |
| T+1 开盘 + 0.1% 滑点 | `data.py:206-207` `entry_price *= (1 + slippage); exit_price *= (1 - slippage)`，默认 `slippage=0.001` | 实测 |
| 冷却期（scored + V2） | `engine.py:279-281` 读 `cfg_strategy.get('cooldown_days', 0)`，line 280 `if cooldown_days > 0:`；V2 `signal_engine.py:225-226` 也加了 | 实测 |
| 流水线 step 4/5 | `evening_pipeline.sh:50-57` 新增 calc_signals v1+v2 + sim_trader --dry-run | 实测 |
| 横向 P0 一组 | `.git.backup-before-filter-repo` 删了 / CORS `ALLOWED_ORIGINS` 变量化 / `str(e)` 数量从 12 降到 0 / `.gitignore` 加 `.env` `.trash` `feedbacks.json` / `CRON.md` 死脚本引用修了 | 实测 |

---

## 2. 重大 P0 阻塞（5 项）❌ **SELL 端到端全断**

### P0-A：`calc_signals.py` 启动即 ImportError
- **位置**：`src/backtest/__init__.py:7`
- **现象**：`from .strategies import STRATEGIES, get_strategy, list_strategies, Strategy`
- **实测**：`python3 scripts/calc_signals.py --date 20260615 --strategy-version v1` 报 `ImportError: cannot import name 'STRATEGIES'`
- **根因**：strategies.py 重构后用 `SIGNAL_VERSIONS` / `_active_config`，但 `__init__.py` 没同步
- **后果**：流水线 step 4/5 跑必失败 → 信号系统在仓库内**仍不可复现**（RESPONSE 说"可复现"是假命题）
- **来源**：agent #2 独立发现 + 实测确认
- **修复**：改 `__init__.py` 为 `from .strategies import get_strategy, list_strategies, get_active_config, ...`

### P0-B：positions 字段名漂移，SELL 永远不生成
- **位置**：`scripts/calc_signals.py:405-409`（agent #2 指出）
- **代码**：`buy_price = pos.get('avg_cost', 0)` → `pos.get('buy_price', 0)` → 都 0 → `continue` 跳过
- **实际 schema**：`cost_price`（实测 sqlite3 PRAGMA 确认）
- **实测**：db.get_positions(1) 返回字典的 keys 是 `['id', 'account_id', 'code', 'name', 'shares', 'cost_price', 'current_price', 'buy_date', 'buy_score', 'closed_at', 'updated_at']`
- **后果**：5 只持仓的 SELL 信号 100% 跳空（buy_price=0），DataFrame 为空
- **修复**：`buy_price = pos.get('cost_price', 0)`

### P0-C：buy_date 格式错位
- **位置**：`scripts/calc_signals.py:411`
- **现象**：`buy_date = str(pos.get('buy_date', '')).replace('-', '')` → `"20260615 08:55:00"`
- **K 线格式**：`"20260615"`（无空格无时间）
- **比较**：`df['_date'] >= "20260615 08:55:00"` 字典序失败（`"20260615" < "20260615 08:55:00"`），K 线扫描区间为空
- **实测**：`buy_date = '2026-06-15 08:55:00'`（来自 positions 表的 datetime('now','localtime')）
- **修复**：`buy_date = str(pos.get('buy_date', ''))[:10].replace('-', '')`

### P0-D：`sim_trader` 残留 NameError
- **位置**：`scripts/sim_trader.py:172`（agent #2 指出）
- **代码**：`if both_triggered:` 变量从未定义
- **后果**：sim_trader 跑到 line 172 时 `NameError`
- **修复**：删除 171-182 整段"双触达警告"

### P0-E：5 只实盘持仓完全无监控
- **位置**：`scripts/calc_signals.py:291` + `sim_trader.py:318-332`
- **实测持仓**（用户 10 万本金）：
  | code | name | shares | cost | buy_date |
  |------|------|--------|------|----------|
  | 601138 | 工业富联 | 2800 | 69.52 | 2026-06-15 08:55 |
  | 000100 | TCL科技 | 44300 | 4.51 | 2026-06-15 08:55 |
  | 003004 | *ST声迅 | 3100 | 64.19 | 2026-06-15 08:55 |
  | 600176 | 中国巨石 | 4800 | 41.07 | 2026-06-15 08:55 |
  | 002008 | 大族激光 | 1600 | 121.45 | 2026-06-15 08:55 |
- **后果**：calc_signals 硬编码 `db.get_account_by_mode('SIM')` → 只扫 SIM 账户；sim_trader 拒 REAL → 5 只实盘持仓**完全没有止盈止损监控**
- **来源**：上次审查已发现的 P0-#4，至今未修

**这 5 项 P0 让 RESPONSE.md Q2 答案"已实施"成为假命题——SELL 端到端完全没通。**

---

## 3. 横向 P0 仍未修（4 项）❌

| 编号 | 主题 | 状态 | 证据 |
|------|------|------|------|
| 持仓 #1 | accounts.strategy_id 漂移 | ❌ 未修 | 实测 `UPDATE accounts SET strategy_id=2 WHERE id=1` → `Error: no such column: strategy_id` |
| 持仓 #2 | TOCTOU 资金竞态 | ❌ 未修 | `trading.py` 搜不到 EXCLUSIVE / atomic 关键词 |
| 持仓 #3 | delete_trade 反转错位 | ⚠️ 修了死循环但**引入新 bug** | agent #4 发现：SELL 反转不回滚 `positions.shares`，永久少 1 笔（trading.py:587-610） |
| 持仓 #4 | TOCTOU 资金竞态 | ❌ 未修 | 无 EXCLUSIVE / 原子 UPDATE |
| 死代码 | backtester.py / tracker.py | ❌ 未删 | 文件仍存在（443 + 552 字节） |

---

## 4. 架构层 P0（agent #1 新发现）❌

### P0-F：PUT `/api/v1/strategies/active` 无鉴权
- **位置**：`api/main.py:1223`
- **代码**：`@app.put("/api/v1/strategies/active")` 无 `dependencies=[Depends(verify_token)]`
- **后果**：未登录用户可改全局策略配置
- **修复**：加鉴权

### P0-G：`_active_config` 无持久化
- **位置**：`src/backtest/strategies.py:60` 模块级 dict
- **后果**：gunicorn 重启 / cron 重启 / OOM / deploy 都丢失
- **修复**：JSON 文件或 SQLite 持久化，启动加载 + 每次 update 写盘

### P0-H：gunicorn 多 worker 配置不一致
- **位置**：`scripts/start_financial_score.sh:22` `-w 2`
- **现象**：每个 worker 独立 `_active_config`
- **后果**：PUT 落 worker 1，GET 落 worker 2 → 用户看到旧配置
- **修复**：单 worker / 文件持久化 / Redis

### P0-I：calc_signals 仍用 `db.get_strategy()` 而非 get_active_config
- **位置**：`scripts/calc_signals.py:387 generate_sell_signals`
- **后果**：运行时配置层不能完全覆盖（这处仍在读 DB strategies 表）
- **来源**：agent #1

---

## 5. 回测 P0 残留（4 项）⚠️

| 编号 | 主题 | 状态 |
|------|------|------|
| 回测 #1 | **live 模式完全没修** | engine.py:162 仍 `scores_df[date == entry_date]` 用 T 日评分 |
| 回测 #2 | **V2 (signal_engine.py) 也没修** | 全文无 T-1/T+1/slippage 关键词 |
| 回测 #3 | 流水线无交易日检查 | holiday cron 仍会失败（用 `batch_result_${holiday}.csv` 不存在） |
| 回测 #4 | sim_trader dry-run 失败软处理 | `\|\| echo` 静默吞错（line 57） |

---

## 6. 未 commit（仓库内不可复现）❌

`scripts/calc_signals.py` / `scripts/sim_trader.py` / `src/backtest/signal_engine.py` 仍 untracked，**虽然 P0-A 修好后能跑，但 clone 仓库后这三个文件缺失**。

---

## 7. 横向真修了 ✅

| 主题 | 状态 | 备注 |
|------|------|------|
| `.git.backup-before-filter-repo/` 暗礁 | ✅ 删了 | — |
| CORS 收紧 | ✅ | `ALLOWED_ORIGINS` 10 项 + nginx ACAO，但 `allow_methods=["*"]` 残留 P1 |
| `str(e)` 泄漏 | ✅ | 14 → 4（仅日志），safe_error_response 32 处 |
| `.gitignore` 修齐 | ✅ | `.env` / `.trash/` / `feedbacks.json` 全有 |
| `CRON.md` 死脚本引用 | ✅ | `daily_download.sh` 引用清零 |
| documents 去重 | ✅ | 三份文档更新 |
| accounts.strategy_id 列 | ❌ | 实测 UPDATE 仍 `no such column` |
| requirements.txt 补齐 | ❌ | 仍 3 行，缺 fastapi/uvicorn/pydantic |
| main.py path traversal | ❌ | in_fname 仍直接拼接到 filename |
| CLI EOFError | ❌ | 4 个 input() 仍无 try/except |
| feedbacks.json SQLite 迁移 | ❌ | 仅 .gitignore，git 历史 6cfc287 仍含 IP |
| deploy nginx vs web nginx 重复 | ⚠️ | 前者缺 ACAO，deploy 误用会失效 |
| calc_signals/sim_trader switch_signal_version 副作用 | ⚠️ | P2，calc_signals:472 / sim_trader:63 默默覆盖 v2 |

---

## 8. 给用户的明确判断

### 你说"重新开始看看" → 我看完了

**结论**：**对方模型改坏了 1 件事、修对 5 件事、改一半 4 件事**：

| 类别 | 项 | 风险 |
|------|----|------|
| **改坏** | __init__.py 导入错误（导致整个 SELL 重构完全失效） | **P0 致命** |
| **改对** | T-1 评分 / T+1 滑点 / 冷却期 / 流水线骨架 / 横向 P0 | 良好 |
| **改一半** | 字段名漂移 / 日期格式错位 / live 模式 / V2 同步 / 鉴权 / 持久化 | 仍需补 |

### 关键三连问（你之前问的）

1. **"回测数字现在可信了吗？"** — **scored 模式：可信**（A1+A4+冷却期都修对了）；**live 模式：仍不可信**（没修）；**V2：仍不可信**（没修）。建议**只用 scored 数字**，旧"年均 +21.6%"必须重跑确认。

2. **"SELL 端到端真打通了吗？"** — **❌ 完全没通**。SELL 改得**写出来了代码但跑不起来**（__init__.py 导入崩 + 字段名漂移 + 日期错位 + NameError 4 重阻塞）。需要**先修 4 个 P0 才能验证 SELL 是否真的端到端通**。

3. **"信号系统仓库内可复现了吗？"** — **❌ 仍不可复现**。三个 untracked 脚本从未 commit；即便 commit 了，__init__.py 导入错也跑不起来。

### 你的 5 只实盘持仓
- **完全无监控**。sim_trader 拒 REAL 模式（line 318-332），calc_signals 硬编码 SIM 账户（line 291）。
- 5 只持仓 2026-06-15 08:55 买入，**买入至今 1 天多，没有任何止盈止损机制在跑**。
- 这是**最危险的事实**——你的 10 万本金（实际是 1.6M 本金：5 只持仓 × 当前价）**完全裸奔**。

---

## 9. 必须立刻修的 9 项

按紧迫度排序：

1. **修 __init__.py 导入**（5min）—— SELL 端到端全部失效
2. **修 SELL 字段名**（5min）—— `avg_cost` / `buy_price` → `cost_price`
3. **修 buy_date 格式**（2min）—— `[:10]` 取日期部分
4. **删 sim_trader both_triggered 段**（2min）—— 删 171-182
5. **实盘账户接入 SELL**（30min）—— 改 calc_signals 接受 REAL，sim_trader 也支持
6. **accounts.strategy_id 加 ALTER TABLE**（10min）—— 解决 API 端点报错
7. **delete_trade SELL 回滚 positions.shares**（10min）—— agent #4 发现的新 bug
8. **PUT /strategies/active 加 verify_token**（5min）—— 安全
9. **_active_config 持久化**（30min）—— 重启即丢

合计 ~1.5 小时。改完后 SELL 端到端 + 实盘监控才能真正工作。

---

## 10. 整体评价

| 维度 | 06-14 | 06-15 | 06-16 |
|------|-------|-------|-------|
| 评分 | 2.5/5 | 2.5/5 | **2/5** ⬇️ |
| 横向 P0 | 0/4 修 | 4/6 修 | **5/9 完整修，1/9 部分修，3/9 未修** ⬆️ |
| 核心链路 | 不可信 | 不可信 | **仍未可信**（写出来 ≠ 跑通） |
| 实盘监控 | 无 | 无 | **仍无**（5 只持仓裸奔） |

**最关键的发现**：RESPONSE.md 的 9 项修复**有 4 项在仓库内跑不起来**（P0-A/B/C/D）。表面看改了很多，**实际没改完的"已改"比"未改"更危险**——给了你虚假的"已修"印象。

**重要建议**：先看 `00-index/RESPONSE.md` 第 396-484 行的"已完成的修复"列表，**自己跑一次 `python3 scripts/calc_signals.py` 验证能否跑通**——实测 5 秒就能发现 P0-A。
