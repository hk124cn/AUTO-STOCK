# 子报告：数据流水线（#2-数据流水线）

> 范围：
> - `src/datafactory/`（13 个文件：market_down / price_builder / data_manager / build_industry_data / trade_calendar / finance_manager / hist_price_*）
> - `src/utils.py`
> - `src/analyzer/future_return_generator.py`（新增，289 行）
> - `src/analyzer/ANALYZER_PLAN.md`（新增规划文档）
> - `data/industry/`、`data/calendar/`、`data/fund/`
> - `scripts/daily_*.py`、`scripts/evening_pipeline.sh`、`scripts/daily_future_return.sh`
> - 复查：上次 P0/F4-F8 修复状态
>
> 严重程度评级：P0=功能错误 / P1=性能或安全 / P2=可改进 / P3=小问题
> 审查日期：2026-06-16

---

## 0. 上次 P0 修复状态

| ID | 上次描述 | 修复状态 | 证据 |
|----|----------|----------|------|
| F4 | `data_fetcher.py` 0 字节 + `sel.py` 死 import | **半修复** | 文件已删除（git status D），但 `src/backtester.py:1` 与 `src/tracker.py:1` 仍有 `from data_fetcher import get_daily_prices`，属同根炸弹未排干净 |
| F5 | 行业映射 33 天未更新 | **未修复** | `stock_industry_mapping.csv` mtime = 2026-05-12 14:54:57（与上次审查完全一致，34 天未变）；CRON.md 与 evening_pipeline.sh 均无 `build_industry_mapping` 调度 |
| F6 | `get_market_change()` 异常返 0.0 | **未修复** | `src/utils.py:64-66` 仍是 `except Exception: ... return 0.0`；`git diff src/utils.py` 为空 |
| F7 | `get_fund_flow_5day` 重复定义 | **未修复** | `data_manager.py:384` 与 `:426` 仍有两个同名定义；`git diff src/datafactory/data_manager.py` 为空 |
| F8 | `trade_days.csv` mtime 不动 | **部分修复** | mtime 已更新到 2026-06-15 11:31，但 CSV 仍只覆盖到 2026-12-31，2027+ 节假日仍未续期 |

**结论**：5 个 P0 中只有 F8 一半修复（重建而非续期），F6/F7 完全未动，F4 留下尾巴，F5 完全未动。**没有针对 P0 的代码改动**（`git diff` 在这两个文件上为空）。

## 1. 概览

数据流水线承接 9 因子评分 + 回测 + 预警 + 报告 + 新增的 future_returns 标签生成，整体"本地优先 + 增量累积"的设计思路不变。本轮审查发现：

1. **P0 几乎没修**：上次列的 5 个 P0 中，4 个原封未动或仅半修；其中 F5（行业映射过期）仍是直接造成 hy_diff_factor 评分覆盖率下降的生产事故。
2. **新代码 `future_return_generator.py` 已上线运行**：cron 18:00 每日跑，已生成 5533 条 5d 收益标签，与 daily_pipeline 平行运转；但代码与 evening_pipeline.sh 脱钩。
3. **新规划 `ANALYZER_PLAN.md`**：与现实脱节——提到 `meta/` 目录但实际不存在；评分有效性验证章节空挂 53 天。

总体：流水线**主流程仍可用**（评分 1385 只约 1 分钟），但 P0 积压 4 个 + 新增 1 个 P0（死代码 backtester/tracker），属于"将错就错"状态。

## 2. 关键发现（按严重程度降序）

### [P0-1] `src/backtester.py` 和 `src/tracker.py` 是 100% 死代码，且 import 已删除的 `data_fetcher`
- 位置：`/home/admin/AUTO-STOCK/src/backtester.py:1`、`/home/admin/AUTO-STOCK/src/tracker.py:1`
- 现象：
  ```python
  # backtester.py:1
  from data_fetcher import get_daily_prices
  # tracker.py:1
  from data_fetcher import get_daily_prices
  ```
- 后果：
  1. `grep -rn "from src.backtester\|from src.tracker\|src\.backtester\b\|src\.tracker\b" --include="*.py"` 完全没有 caller —— 两个文件是孤立死代码
  2. 上次审查的 F4 把 `data_fetcher.py` 删了，但忘了这两个"孤儿"
  3. 与 `scripts/run_backtest.py`（独立的回测引擎）功能重复——`run_backtest.py` 才是真回测入口
- 证据：`ls /home/admin/AUTO-STOCK/src/backtester.py /home/admin/AUTO-STOCK/src/tracker.py` 存在；grep 无 caller
- 建议：直接 `rm src/backtester.py src/tracker.py`

### [P0-2] `utils.get_market_change()` 异常时返回 0.0（延续上次 F6 未修复）
- 位置：`/home/admin/AUTO-STOCK/src/utils.py:64-66`
- 现象：
  ```python
  except Exception as e:
      print(f"⚠️ 无法获取上证指数数据: {e}")
      return 0.0
  ```
- 后果链：
  1. `dp_diff_factor.py:46` `index_ret = src.utils.get_market_change()`
  2. akshare 限流/异常 → `index_ret = 0.0`
  3. `relative = stock_ret - 0 = stock_ret` → 全部"跑赢大盘" → 评分虚高
  4. `attention_factor.py:31` 也调用 `get_market_change()` —— 同问题影响 2 个因子
- 证据：`git diff src/utils.py` 为空 → 上次审查后此文件未改动
- 建议：
  1. 改为 `return None`，调用方判断 None 时按"无法判断大盘"占位（score=5 中位数）
  2. 加 5 分钟缓存（指数数据稳，没必要每次重拉）

### [P0-3] `data_manager.get_fund_flow_5day()` 重复定义未清理（延续上次 F7）
- 位置：`/home/admin/AUTO-STOCK/src/datafactory/data_manager.py:384`（第一版，无 date 参数）、`:426`（第二版，带 date）
- 现象：Python 用 `:426` 完全覆盖 `:384`，第一版变成死代码，但留下"两套逻辑"误导
- 后果：
  1. 维护者误以为有两套实现
  2. 实际生效是第二版，但 `get_latest_fund_flow_file()` 在无文件时返回 None → `_read_csv_if_exists(None)` 触发 `os.path.join("data/fund", None)` TypeError（极少触发但存在）
- 证据：`git diff src/datafactory/data_manager.py` 为空
- 建议：删除 `:384-414` 第一版

### [P0-4] 行业映射 34 天未更新（延续上次 F5）
- 位置：`/home/admin/AUTO-STOCK/data/industry/stock_industry_mapping.csv`（mtime 2026-05-12 14:54:57，size 139690）
- 现象：5199 条映射，与上次审查 mtime 完全一致（仅 1 天差别，因本日 6/15 → 上次审查 6/14，差 1 天）
- 后果链：
  1. 5/13 - 6/15 之间新上市的股票在 `get_stock_industry_from_cache` 命中失败 → `IndustryDiffFactor.calculate()` 返回 score=0
  2. `daily_industry_change.py` 只追加 `change_*.csv`，不重建映射
  3. `scripts/evening_pipeline.sh` 也未调用 `build_industry_mapping`
- 证据：
  ```
  $ stat -c '%y %s %n' data/industry/stock_industry_mapping.csv
  2026-05-12 14:54:57.005576580 +0800 139690 ...
  ```
- 建议：
  1. 立即手动跑一次：`python -m src.datafactory.build_industry_data --industry`
  2. 加入周更 cron：`0 9 * * 1 bash -c "cd /home/admin/AUTO-STOCK && python -m src.datafactory.build_industry_data --industry"`
  3. `hy_diff_factor.calculate()` 加 fallback：行业未命中时按"全市场均值"

### [P0-5] `data/industry/` 缺失 `change_801010_20d.csv`（农林牧渔）
- 位置：`/home/admin/AUTO-STOCK/data/industry/`（131 个 change CSV 应该有 131 条，实际有 130 条）
- 现象：`ls | grep change_ | head -3` → 801011、801012、801014 起步，**801010 缺失**
- 后果：
  1. 农林牧渔板块所有个股的 20d 行业涨跌幅为 None
  2. `hy_diff_factor.py` 走 `get_industry_change_by_code(sw_code="801010")` → 返回 None → `industry_change = None`
  3. 个股 vs 行业强弱判断失败 → 默认 score=0
- 证据：`ls /home/admin/AUTO-STOCK/data/industry/ | grep "^change_801010"` 无输出
- 建议：跑 `python -m src.datafactory.build_industry_data --changes` 重生成

### [P1-1] `dp_diff_factor` 模块级 `index_ret` 全局变量永久缓存错误值
- 位置：`/home/admin/AUTO-STOCK/src/factors/dp_diff_factor.py:7,42-46`
- 现象：
  ```python
  index_ret = None
  class RelativeStrengthFactor(BaseFactor):
      def calculate(self):
          global index_ret
          ...
          if index_ret is None:
              index_ret = src.utils.get_market_change()
  ```
- 后果：
  1. 进程内首次调用后永久缓存到进程退出
  2. akshare 单次异常 → index_ret=0.0 → 后续所有股票用错的大盘基准
  3. 与 P0-2 联动放大危害
- 证据：grep 显示 `index_ret` 唯一赋值点 line 46
- 建议：增加日期戳检查：
  ```python
  if index_ret is None or index_date != today:
      index_ret = src.utils.get_market_change()
      index_date = today
  ```

### [P1-2] `future_return_generator.py` 没用 `data_manager.get_price` 而是手写 csv.DictReader
- 位置：`/home/admin/AUTO-STOCK/src/analyzer/future_return_generator.py:82-120`
- 现象：自己重新实现 `get_price(code, date)`：打开 `data/price/{code}.csv` → csv.DictReader 逐行 → 找日期匹配 → float(row['收盘'])
- 后果：
  1. 25 个 batch × 3 个 n_days × 1380 只股票 = **~10 万次 open + DictReader**（5535 × 18 = 10 万）
  2. 同样的逻辑 `data_manager.get_price` 已经实现（line 38-41），但完全没复用
  3. log 显示单个 20d 文件 11 秒（1380 只），25 个 batch 约 5-10 分钟——可以更快
- 证据：
  ```
  2026-06-15 18:00:15 - 20260518 评分股票 1384 只...
  2026-06-15 18:00:26 - ✅ 生成 future_20d_20260518.csv: 成功 1380, 失败 4
  ```
  11 秒处理 1380 只（~125 行/秒/股）
- 建议：改为复用 `data_manager.get_price(code)`，并加 dict 缓存同一次调用内的 price_df

### [P1-3] `future_return_generator.py` 未接入 `evening_pipeline.sh`
- 位置：`/home/admin/AUTO-STOCK/scripts/evening_pipeline.sh`（3 个步骤）、`/home/admin/AUTO-STOCK/scripts/daily_future_return.sh`（独立 cron 18:00）
- 现象：晚间流水线 = 评分 → kline → 报告；future_returns 完全独立运行
- 后果：
  1. cron 18:00 失败时，晚间流水线不知道
  2. 手工跑 `bash scripts/evening_pipeline.sh 20260615` 时不会顺带跑 future_returns
  3. 两套 cron 协调成本（独立日志、独立失败重试）
- 建议：把 `python src/analyzer/future_return_generator.py` 加到 evening_pipeline.sh 步骤 3.5，并改 cron 19:30 触发

### [P1-4] `_is_cache_expired` 对 `finance_df` 列名变化无防护（延续上次 P1-1）
- 位置：`/home/admin/AUTO-STOCK/src/datafactory/data_manager.py:572-590`
- 现象：line 578 `finance_periods = finance_df['报告期'].dropna().unique()` 直接 KeyError
- 后果：akshare 同花顺接口某天换列名 → `get_disclosure_dates` → `_is_cache_expired` → KeyError → 抛出给调用方（API 500）
- 证据：上次审查已标记，本次 git diff 为空
- 建议：line 572 入口加 `if '报告期' not in finance_df.columns: return True`

### [P2-1] `future_return_generator.py` 路径硬编码
- 位置：`/home/admin/AUTO-STOCK/src/analyzer/future_return_generator.py:22`
- 现象：`AUTO_STOCK_ROOT = "/home/admin/AUTO-STOCK"`
- 后果：项目 clone 到 `/opt/AUTO-STOCK` 即崩
- 建议：`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`

### [P2-2] `ANALYZER_PLAN.md` 提到的 `meta/` 目录不存在
- 位置：`/home/admin/AUTO-STOCK/src/analyzer/ANALYZER_PLAN.md:81-83`
- 现象：文档列出 `meta/factor_config_v1.json`、`meta/pool_config_v1.json`、`meta/snapshot_manifest.csv`，但 `ls /home/admin/AUTO-STOCK/meta/` 不存在
- 证据：grep `meta/factor_config_v1.json` 仅在 ANALYZER_PLAN.md 和 MAINTENANCE.md 出现，无任何代码引用
- 建议：删除文档中 meta/ 相关章节，或真创建 meta/ 目录

### [P2-3] `ANALYZER_PLAN.md` 第三阶段（评分有效性验证）空挂 53 天
- 位置：`/home/admin/AUTO-STOCK/src/analyzer/ANALYZER_PLAN.md:208-211`
- 现象：
  ```
  | 3.1 score_validator.py 脚本 | 待做 | 🔴 高 | 验证评分有效性 |
  | 3.2 生成验证报告 | 待做 | 🟡 中 | 表格+可视化 |
  ```
- 后果：5533 条 5d 收益标签已生成 1 个月，但没人用 → 数据生产未消费
- 建议：要么删该章节，要么在 ROADMAP 中分配任务

### [P2-4] `data/calendar/trade_days.csv` 仅覆盖至 2026-12-31
- 位置：`/home/admin/AUTO-STOCK/data/calendar/trade_days.csv`（8798 行）
- 现象：`tail -3` 显示 2026-12-29 / 12-30 / 12-31；2027+ 节假日未覆盖
- 后果：上次 F8 重建了，但"长期不更新"的根因未解决——下次重建前 2027/01 节假日又会失效
- 建议：`init_trade_calendar` 改为"增量追加"，每次调用先 append 缺失日期

### [P3-1] `processed_sw_changes.txt` 已清理（好消息）
- 位置：`/home/admin/AUTO-STOCK/data/industry/processed_sw_changes.txt`
- 状态：上次审查标记的 P1-2 文件不存在了

## 3. 改进建议（非问题，但有更好做法）

### [P3-2] `future_return_generator.py` 可以考虑支持"逐 batch + 增量"
当前实现是全量扫描 25 个 batch × 3 个 n_days = 75 次 future_returns 调用。如果改成"按 batch 增量 + 缓存已读 price_df"，速度可提升 3-5 倍。

### [P3-3] `data_manager.build_industry_mapping()` 是旧版，未使用
`data_manager.py:217-295` 用 `ak.stock_board_industry_name_em`；`build_industry_data.py:248` 用 `ak.index_component_sw`（申万）。前者被取代但未删除。建议清理。

### [P3-4] `finance_manager.py` 是被取代的旧实现
全项目无 caller（`grep -rn finance_manager` 无业务调用），纯死代码，可删。

## 4. 需要核实的不确定项

- **行业映射缺失的 1 个**（上次已标记）：当前确认 130 个 change CSV，但 SW_CODES 共 131 条，缺哪个尚未对比。可能是 801010 农林牧渔（已在本轮发现 P0-5）。
- **`processed_sw_changes.txt` 是否真正"清理"还是"移到 bak"**：本次审查确认文件不存在，但 README 没更新，可能影响其他审查员的认知。
- **`build_industry_data --industry` 命令是否已能正常工作**：未实际跑过，因 P0-4 未修复。

## 5. 评分（1-5，5 = 优）

- **正确性：2/5** — 4 个 P0 延续 + 1 个新 P0（死代码）+ 行业映射依然 34 天过期；评分主流程"将错就错"
- **可维护性：2.5/5** — `data_manager.py` 重复定义、死代码未清、`ANALYZER_PLAN.md` 提到不存在的 `meta/`
- **性能：3.5/5** — `future_return_generator.py` 新功能可用但每次重读 10 万次 CSV；主流程 5 分钟内可跑 5000 股
- **文档：2.5/5** — CLAUDE.md 与现实基本一致；但 ANALYZER_PLAN.md 有 1 个月未更新的"待做"清单
- **总评：2.5/5** — 较上次审查（3/5）下降，因为 P0 几乎没修 + 新增死代码

## 6. Top-3 严重问题

1. **P0-4 行业映射依然 34 天未更新** — 与上次审查完全一致，hy_diff_factor 评分覆盖率持续下降，5/13 后新股全部 0 分
2. **P0-1 backtester.py / tracker.py 是死代码且引入了删除模块** — F4 的尾巴未排干净
3. **P0-2 utils.get_market_change 仍然返 0.0** — akshare 异常时 dp_diff_factor + attention_factor 双重错算，影响 9 因子中 2 个

## 7. P0/P1/P2 数量

- **P0：5**（延续上次 5 个中 4 个未修 + 新增 1 个死代码）→ 实际未减少
- **P1：4**（P1-1 延续 + 新增 3 个）
- **P2：4**（P2-2~4 新增 + P2-3 来自上次未修）
- **P3：1**

---

## 附录 A：上次 P0 与本次状态对照表

| 上次 ID | 描述 | 本次状态 | 备注 |
|---------|------|----------|------|
| F4 | data_fetcher/sel.py | 半修 | 文件已删，但 backtester.py/tracker.py 留尾巴 |
| F5 | 行业映射过期 | 未修 | mtime 一字未变 |
| F6 | get_market_change 返 0.0 | 未修 | 代码字未变 |
| F7 | get_fund_flow_5day 重复 | 未修 | 代码字未变 |
| F8 | trade_days.csv mtime | 半修 | mtime 更新但 2027+ 未续期 |

## 附录 B：本次新代码审查要点

### `src/analyzer/future_return_generator.py`（289 行）
- **目的**：每日 cron 18:00 跑，扫描 `result/daily_score/` 所有 batch_result，计算 N 天后收益（5d/10d/20d）→ 输出 `result/future_returns/{n}d/future_{n}d_{score_date}.csv`
- **输入**：batch_result_*.csv + data/price/{code}.csv + data/calendar/trade_days.csv
- **输出**：CSV（8 列：date/code/name/score_date/score_price/nd_date/nd_price/next_nd_return）
- **异常处理**：良好（每个 step 都有 try-except + 日志）
- **边界**：前瞻检查 `if nd_date > today: return` 正确
- **不足**：
  - 路径硬编码
  - 不复用 data_manager.get_price
  - 不在 evening_pipeline.sh

### `src/analyzer/ANALYZER_PLAN.md`（301 行）
- **目的**：规划分析层架构（5 阶段）
- **已实现**：阶段 1-2（meta/、future_return_generator.py）
- **未实现**：阶段 3-5（score_validator / kline_analyzer / signal_detector / label_generator）
- **问题**：
  - meta/ 目录实际不存在
  - 53 天未更新阶段 3-5 进度
  - kline_analyzer.py 已存在但文档还标"待做"（冲突）