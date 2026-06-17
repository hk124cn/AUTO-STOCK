# 25 项问题详细清单

> 每项格式：**问题 → 后果 → 修法 → 工作量 → 状态**  
> 修法是建议，**实际怎么改由另一模型决定**，但目标效果一致

## 状态图例

- ⏳ 待修
- 🔧 修复中
- ✅ 已修（需在 STATUS.md 标修复 commit hash）
- ⏭️ 跳过（需在 STATUS.md 写理由）
- ❌ 修复失败（需写原因）

---

## 🔴 第一波：4 个 P0 阻塞（10min）

### #1 P0-A `__init__.py` 导入错误
- **位置**：`src/backtest/__init__.py:7`
- **问题**：`from .strategies import STRATEGIES, get_strategy, list_strategies, Strategy` — `STRATEGIES` 和 `Strategy` 在 f21e127 commit 中已删除
- **实测**：`ImportError: cannot import name 'STRATEGIES' from 'src.backtest.strategies'`
- **后果**：API GET/PUT `/api/v1/strategies/active` 返回 500；calc_signals.py 启动即崩；sim_trader.py 启动即崩；f21e127 整个 commit 失效
- **修法**：
  ```python
  # src/backtest/__init__.py
  from .strategies import (
      get_strategy, list_strategies,
      get_active_config, update_active_config, switch_signal_version,
      DEFAULT_STRATEGY_VERSION, SIGNAL_VERSIONS,
  )
  __all__ = ["get_strategy", "list_strategies", "get_active_config",
             "update_active_config", "switch_signal_version",
             "DEFAULT_STRATEGY_VERSION", "SIGNAL_VERSIONS"]
  ```
  改前**先** `grep "^def \|^[A-Z_]\+ *=" src/backtest/strategies.py` 确认实际导出
- **工作量**：5min

### #2 P0-B positions 字段名漂移
- **位置**：`scripts/calc_signals.py:405-409`
- **问题**：读 `pos.get('avg_cost', 0)` 和 `pos.get('buy_price', 0)`，但 positions 表实际列名是 `cost_price`
- **实测**：5 只持仓的 SELL 信号全部因 buy_price=0 被跳过
- **后果**：SELL 信号永远不生成
- **修法**：
  ```python
  # calc_signals.py:405-407
  buy_price = pos.get('cost_price', 0)
  if buy_price <= 0:
      print(f"⚠️ {pos['code']} 成本价异常 ({buy_price})，跳过 SELL 检查")
      continue
  ```
- **工作量**：2min

### #3 P0-C buy_date 格式错位
- **位置**：`scripts/calc_signals.py:411`
- **问题**：`buy_date = str(pos.get('buy_date', '')).replace('-', '')` → "20260615 08:55:00"（带空格时间），K 线日期是 "20260615"（紧凑 8 位）
- **后果**：字典序比较失败，K 线扫描区间为空
- **修法**：
  ```python
  # calc_signals.py:411
  buy_date = str(pos.get('buy_date', ''))[:10].replace('-', '')
  # "2026-06-15 08:55:00"[:10] = "2026-06-15" → "20260615"
  ```
- **工作量**：1min

### #4 P0-D sim_trader both_triggered NameError
- **位置**：`scripts/sim_trader.py:171-182`
- **问题**：`if both_triggered:` 和 `for t in both_triggered:` 引用未定义变量（K 线扫描时代残留）
- **后果**：sim_trader 跑到 line 172 时 NameError，daily-run 必崩
- **修法**（方案 A 简单）：
  ```python
  # 删除 sim_trader.py:171-182 整段（双触达警告）
  # sim_trader 是纯执行器，警告逻辑不在这里
  ```
  或方案 B：保留功能，从 SELL CSV 的 `sell_type == 'both'` 读
- **工作量**：1min

---

## 🟠 第二波：7 个 P0（45min）

### #6 P0-F PUT `/api/v1/strategies/active` 无鉴权
- **位置**：`api/main.py:1223`
- **问题**：`@app.put("/api/v1/strategies/active")` 无 `dependencies=[Depends(verify_token)]`
- **前置**：必须**先**修 #1（__init__.py）让端点能跑起来
- **实测**：修 #1 后 curl 带 token 才能 200，否则 422
- **后果**：任何人能改全局策略配置（影响所有 calc_signals/sim_trader 行为）
- **修法**：
  ```python
  # api/main.py:1223
  @app.put("/api/v1/strategies/active", dependencies=[Depends(verify_token)])
  ```
- **工作量**：1min

### #7 P0-G `_active_config` 无持久化
- **位置**：`src/backtest/strategies.py:60`（模块级 dict）
- **问题**：进程内存 dict，gunicorn 重启 / systemd 重启 / OOM 都丢失配置
- **后果**：每次重启都回到默认（v1 + 20%/8%）
- **修法**：
  ```python
  # strategies.py
  import json
  from pathlib import Path
  
  _ACTIVE_CONFIG_FILE = Path(__file__).parent.parent / "data" / "active_config.json"
  
  def _load_active_config() -> dict:
      if _ACTIVE_CONFIG_FILE.exists():
          try: return json.loads(_ACTIVE_CONFIG_FILE.read_text())
          except: pass
      return {**_SIGNAL_VERSIONS["v1"], **_DEFAULT_TRADING_PARAMS}
  
  _active_config: dict = _load_active_config()
  
  def _save_active_config():
      _ACTIVE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
      _ACTIVE_CONFIG_FILE.write_text(json.dumps(_active_config, ensure_ascii=False, indent=2))
  
  def update_active_config(updates: dict):
      _active_config.update(updates)
      _save_active_config()  # 每次写盘
  ```
  `data/active_config.json` 在 `.gitignore`（`data/` 已忽略）— 不用额外配置
- **注意**：不解决 P0-H 多 worker 问题
- **工作量**：15min

### #8 P0-H gunicorn 多 worker 一致性
- **位置**：`scripts/start_financial_score.sh:22`（`gunicorn -w 2`）
- **问题**：每个 worker 独立 `_active_config` dict
- **实测**：现在 systemd 单 worker **没中招**；`start_financial_score.sh` gunicorn 仍存在
- **后果**：用 gunicorn 时 PUT/GET 落不同 worker → 幽灵配置切换
- **修法（推荐）**：
  ```bash
  # start_financial_score.sh 改为：
  sudo systemctl restart stock-api
  # 不用 gunicorn 不用 -w
  ```
  或更彻底：`rm scripts/start_financial_score.sh`
- **工作量**：5min

### #10 P0 `accounts.strategy_id` 列漂移
- **位置**：`src/portfolio/database.py` `_init_db` 函数
- **问题**：实际 DB 缺 `strategy_id` 列，但 `_init_db` 用 `CREATE TABLE IF NOT EXISTS` 不补列
- **实测**：`UPDATE accounts SET strategy_id=2` → `Error: no such column`
- **后果**：API `set_account_strategy` 端点 500
- **修法**：
  ```python
  # database.py _init_db 末尾加：
  for stmt in [
      "ALTER TABLE accounts ADD COLUMN strategy_id INTEGER",
      # 未来迁移也加这里
  ]:
      try: c.execute(stmt)
      except sqlite3.OperationalError: pass  # 列已存在
  con.commit()
  ```
- **工作量**：5min

### #11 P0 main.py path traversal
- **位置**：`main.py:75-91`
- **问题**：`filename = f"./result/daily_score/{in_fname}.csv"`，用户输入 `../../etc/passwd` 可越权写
- **后果**：能写到任意路径（DoS、覆盖配置等）
- **修法**：
  ```python
  def run_batch(csv_file, in_fname):
      ...
      if in_fname == '':
          filename = f"./result/daily_score/batch_result_{datetime.today().strftime('%Y%m%d')}.csv"
      else:
          safe_name = os.path.basename(in_fname)
          if not safe_name.endswith('.csv'):
              safe_name += '.csv'
          filename = f"./result/daily_score/{safe_name}"
      # 验证最终路径仍在允许目录内
      abs_filename = os.path.abspath(filename)
      abs_allowed = os.path.abspath("./result/daily_score/")
      if not abs_filename.startswith(abs_allowed + os.sep):
          print(f"❌ 非法路径: {in_fname}")
          return
      result_df.to_csv(filename, index=False)
  ```
- **工作量**：5min

### #12 P0 CLI EOFError
- **位置**：`main.py:100, 103, 107, 108` 4 处 `input()`
- **问题**：非交互式场景（cron、管道、测试）直接 EOFError 崩
- **修法**：
  ```python
  def safe_input(prompt: str, default: str = '') -> str:
      try: return input(prompt).strip()
      except (EOFError, KeyboardInterrupt):
          print(); return default
  
  # 4 处 input() 替换为 safe_input(...)
  ```
- **工作量**：5min

### #13 P0 requirements.txt 缺依赖
- **位置**：`requirements.txt`（仅 3 行）
- **问题**：缺 fastapi / uvicorn / pydantic / starlette / httpx（TestClient 需）
- **后果**：新机器/CI 装 requirements 后 API 跑不起来
- **修法**：
  ```bash
  # 跑 pip freeze 看你 venv 实际装的版本，然后追加到 requirements.txt：
  pip freeze | grep -E "^(fastapi|uvicorn|pydantic|starlette|httpx|akshare|pandas|numpy)="
  ```
  追加：
  ```
  fastapi>=0.110.0
  uvicorn[standard]>=0.27.0
  pydantic>=2.5.0
  starlette>=0.36.0
  httpx>=0.27.0
  ```
- **工作量**：5min

---

## 🟡 第三波：5 个小 P1/P2（30min）

### #9 delete_trade SELL 不回滚 positions.shares
- **位置**：`src/portfolio/trading.py:587-610`（delete_trade 的 SELL 反转路径）
- **问题**：SELL 反转只回滚了资金和 trade_lots，**没有 `UPDATE positions SET shares = shares + ?`**
- **后果**：删除 SELL 交易记录后，positions 表的持仓数永久少 1 笔
- **修法**：
  ```python
  # 在 SELL 反转的 c.execute("UPDATE accounts ...") 之后加：
  c.execute(
      "UPDATE positions SET shares = shares + ? WHERE account_id = ? AND code = ? AND buy_date = ?",
      (trade['shares'], acc_id, code, trade['trade_date'])
  )
  ```
- **工作量**：10min

### #16 流水线无交易日检查
- **位置**：`scripts/evening_pipeline.sh:1` 之后
- **问题**：cron 周一到周五跑，国庆/清明等节假日也跑 → 出空报告
- **修法**：
  ```bash
  # evening_pipeline.sh 顶部加：
  if [ -f "data/calendar/trade_days.csv" ]; then
      DATE_HUMAN=$(date -d "${TARGET_DATE}" +%Y-%m-%d 2>/dev/null || echo "$TARGET_DATE")
      if ! grep -q "^${DATE_HUMAN}" data/calendar/trade_days.csv 2>/dev/null; then
          echo "⏭️  ${DATE_HUMAN} 不是交易日（节假日），跳过流水线"
          exit 0
      fi
  else
      echo "⚠️  交易日历文件不存在，继续执行"
  fi
  ```
- **工作量**：5min

### #17 sim_trader dry-run 软失败
- **位置**：`scripts/evening_pipeline.sh:57`
- **问题**：`|| echo "⚠️"` 静默吞错，监控失明
- **前置**：必须**先**修 #4（both_triggered NameError）
- **修法**：
  ```bash
  # evening_pipeline.sh:57
  python3 scripts/sim_trader.py --date "$TARGET_DATE" --dry-run || fail "sim_trader dry-run"
  ```
  如果用户最终想**真交易**（去掉 --dry-run），同样硬失败
- **工作量**：1min

### #18 calc_signals generate_sell_signals 用 db.get_strategy
- **位置**：`scripts/calc_signals.py:387`
- **问题**：SELL 计算用 `db.get_strategy()` 读 DB，应该用 `get_active_config()` 读运行时配置
- **后果**：BUY/SELL 配置源不一致，可能用错阈值
- **修法**：
  ```python
  # calc_signals.py:387 改为：
  config = get_active_config()  # 已在 main() 切过版本
  tp = config['take_profit']
  sl = config['stop_loss']
  # 删掉 db.get_strategy(strategy_id)
  ```
  更彻底：把 `generate_sell_signals` 函数签名改成 `def generate_sell_signals(positions, account_id, config: dict)`
- **工作量**：15min

### #19 allow_methods=["*"] 残留
- **位置**：`api/main.py:65`
- **问题**：CORS allow_methods 全开（最小权限原则违反）
- **修法**：
  ```python
  # api/main.py:65
  allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  ```
- **工作量**：1min

---

## 🟢 第四波：9 项（按需）

### #20 P2 deploy nginx vs web nginx 重复配置
- **位置**：`deploy/stock-system.conf` 与 `web/stock-system/nginx.conf`
- **问题**：deploy 那份缺 ACAO 头，运维可能误用
- **修法（推荐）**：删 `deploy/stock-system.conf`，统一用 `web/stock-system/nginx.conf`
- **工作量**：10min

### #14 P1 live 模式未修前视偏差
- **位置**：`src/backtest/engine.py:110-234` (`_run_live()`)
- **问题**：`line 162 day_scores = scores_df[date == entry_date]`（T 日评分）
- **修法 A（小）**：加 docstring "live 模式未修前视偏差，仅供实验"
- **修法 B（大）**：复制 scored 模式的 T-1 + 冷却期到 live
- **推荐 A**（你不用 --live 参数）
- **工作量**：A=5min / B=1-2h

### #15 P1 V2 signal_engine.py 未同步修
- **位置**：`src/backtest/signal_engine.py`
- **问题**：T-1 / T+1 / 滑点全无（仅冷却期）
- **修法**：补 3 个修复（T-1 评分 + T+1 open + 0.1% 滑点）
- **工作量**：~1h

### #21 P0 持仓 TOCTOU 资金竞态
- **位置**：`src/portfolio/trading.py:142-170`
- **问题**：读-改-写非原子，并发买入可能让 current_capital 变负
- **修法**：
  ```python
  # 替换 read-then-write 为条件 UPDATE：
  result = c.execute(
      "UPDATE accounts SET current_capital = current_capital - ? WHERE id = ? AND current_capital >= ?",
      (total_cost, acc_id, total_cost)
  )
  if result.rowcount == 0:
      return error("资金不足或账户不存在")
  # 删除 line 142 的 get_account 调用
  ```
- **工作量**：30min

### #22 P2 A 股 transfer_fee 漏算
- **位置**：`src/portfolio/database.py:28`（常量）+ `trading.py:22-38`（calc_cost）
- **问题**：算买卖成本时缺 0.001% 过户费
- **修法**：
  ```python
  # trading.py:22-38
  TRANSFER_FEE_RATE = 0.00001  # 0.001% A 股过户费
  def calc_cost(price, shares, side):
      amount = price * shares
      commission = max(amount * 0.00015, 5)
      stamp_tax = amount * 0.001 if side == 'SELL' else 0
      transfer_fee = amount * TRANSFER_FEE_RATE
      return commission + stamp_tax + transfer_fee
  ```
- **工作量**：15min

### #23 P2 胜率不扣手续费
- **位置**：`src/portfolio/database.py` 的 `get_trade_stats`
- **前置**：先修 #22（transfer_fee）
- **修法**：在 is_win 判定加 min threshold：
  ```python
  def is_win(net_return, threshold=0.5):  # 至少赚 0.5 元才算赢
      return net_return > threshold
  ```
- **工作量**：30min

### #24 P1 feedbacks.json IP 仍在 git 历史
- **位置**：git commit `6cfc287` 历史
- **问题**：`feedbacks.json` 含真实 IP `183.222.203.200`，仍可在 git log 中看到
- **修法**：
  ```bash
  echo "183.222.203.200==>REDACTED_IP" > /tmp/secrets.txt
  /home/admin/.local/bin/git-filter-repo --replace-text /tmp/secrets.txt --force
  git remote add origin git@github.com:hk124cn/AUTO-STOCK.git
  git push --force origin main
  ```
- **验证**：`git log --all -p | grep "183.222"` 应为 0
- **工作量**：30min

### #25 P2 sim_trader switch_signal_version 副作用
- **位置**：`scripts/sim_trader.py:62-64`、`scripts/calc_signals.py:471-473`
- **问题**：每次 CLI 跑 sim_trader 都把 `_active_config` 覆盖为 CLI 传入的版本
- **修法**：
  ```python
  # sim_trader.py / calc_signals.py
  if args.strategy_version:
      switch_signal_version(args.strategy_version)  # 仅显式传时切
  config = get_active_config()
  ```
- **工作量**：15min

---

## 工作量合计

| 波次 | 项数 | 总工作量 |
|------|------|----------|
| 🔴 第一波 | 4 | 10min |
| 🟠 第二波 | 7 | 45min |
| 🟡 第三波 | 5 | 30min |
| 🟢 第四波 | 9 | 4h+ |
| **🔴🟠🟡 必做** | **16** | **~1.5h** |

---

## 修复时的关键依赖关系

```
#1 (P0-A __init__.py)
   └→ 是 #2 #3 #4 #6 #16 #17 #18 #25 的前置（API/脚本能跑）
   └→ 是 #7 (持久化) 的前置（导入成功才能跑 load_active_config）

#2 → 是 #3 #4 修完后才能验证 SELL 信号生成
#3 → 同上
#4 → 是 #17 (软失败改硬失败) 的前置

#6 (PUT 鉴权) → 必须 #1 修完后才能测
#7 (_active_config 持久化) → 修后要重启 API 才会重新加载

#10 (accounts.strategy_id) → 修后要重启 API 才能让 ALTER 生效
```

**任何 P0 修完都要 `sudo systemctl restart stock-api`**（让 import 变更生效）。
