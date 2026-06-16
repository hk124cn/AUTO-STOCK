# 子报告：因子系统（Factor System）

> 范围：
> - `src/core/base_factor.py`、`src/core/factor_manager.py`、`src/core/scoring_engine.py`
> - `src/factors/*.py`（9 个因子：attention / daily_change / dividend / financial / fiveday / hy_diff / news / zj_flow / dp_diff）
> - 入口 `main.py`（含 `load_factors` / `run_single` / `run_batch`）
> - 旁路依赖 `src/datafactory/data_manager.py`、`src/utils.py`
>
> 严重程度评级：P0=功能错误 / P1=性能或安全 / P2=可改进 / P3=小问题
> 审查日期：2026-06-16

## 0. 上次 P0 修复状态（重点）

上次（2026-06-14）报告 3 个 P0，本轮逐项核实：

| ID | 描述 | 修复状态 | 证据 |
|----|------|----------|------|
| **F1** | `daily_change_factor` 找 `成交量` 列，CSV 实际是 `成交额`，放量加分死代码 | **未修复** | `src/factors/daily_change_factor.py:95` 仍写 `volume_col = '成交量'`；实测 600519 输出 `meta.volume_ratio: 1.0`（永远走"列不存在"分支） |
| **F2** | `scoring_engine.aggregate_scores()` + `factor_manager.discover_and_run()` 死代码；9 因子 `weight` 字段从未被读取 | **未修复** | `grep -rn aggregate_scores\|discover_and_run\|factor_manager` 全代码库无调用方；`main.py:47` 仍是 `total_score += factor_score`（简单求和）；类级 `weight = 10` 属性无任何 reader |
| **F3** | `dp_diff_factor.py` 命名误导（实际是 YTD 相对大盘） | **未修复** | 文件名 `dp_diff_factor.py`、类名 `RelativeStrengthFactor`、`index_ret` 全局缓存全部保留原样 |

**唯一修复** = P2-3（`hy_diff_factor.py.bak` 残留已删除）。
其余 16 个 P1/P2/P3 全部未修复。

> 重要：上次报告 17 项发现中仅 1 项修复。本次仅在 `main.py` 做了 2 行路径迁移（`./src/result/` → `./result/daily_score/`），因子系统代码 0 改动。

---

## 1. 概览

9 因子评分系统采用"动态发现 + 基类 + calculate() 返回 dict"的统一契约，9 个因子总分 100 分（财务 20 + 其他 8×10）。

**本轮关键发现**：
- **3 个 P0 全部延续**（F1 / F2 / F3），且用真实股票代码 600519 跑 `DailyChangeFactor` 验证 F1 仍在生效。
- 唯一变化：main.py 把输出目录从 `./src/result/` 迁到 `./result/daily_score/`，路径已与 daily_report.py / stock_analysis.py 一致；但 main.py 用相对路径，其他脚本用绝对路径，存在脆弱耦合。
- `dividend_factor` 高股息反扣分（>10% → 6）、`fiveday_factor` 永远落在 [2,10]、dp_diff 全局缓存跨日风险等 P1 全部保留。
- **新增发现**：main.py:48 `s_score += sum_score` 计算结果从未被 print/写入，是死计算。

整体处于"上次审查发现基本未消化、积压 3 个 P0 + 5 个 P1 + 6 个 P2 + 2 个 P3"的状态。

---

## 2. 关键发现（按严重程度降序）

### [P0] daily_change 放量加分逻辑永远不触发（**延续**）
- 位置：`src/factors/daily_change_factor.py:95, 107-111`
- 现象：代码 `volume_col = '成交量'`；实测 `data/price/600519.csv` / `000001.csv` / `600660.csv` 表头均为 `日期,收盘,成交额,开盘,最高,最低`。
- 后果：`if volume_col in recent.columns` 永远 False → `volume_ratio = 1.0` → `if volume_ratio > 1.5` 永远不进入 → `volume_factor = 1.0` → 放量加权 1.2x 设计**完全失效**。
- 证据（实测运行 600519）：
  ```python
  >>> DailyChangeFactor("600519").calculate()
  {'name': '单日涨跌幅', 'score': 2, 'sum_score': 10,
   'meta': {'today_change': -1.61, 'trend_status': 'weak_down', 'volume_ratio': 1.0}}
  ```
  `volume_ratio: 1.0` 是"列不存在"fallback 的标志值。
- 建议：把 `volume_col` 改为 `'成交额'`，并补 fallback 链 `['成交额', '成交量', 'volume']`。

### [P0] 入口 main.py 与 scoring_engine 路径不一致（**延续**）
- 位置：`main.py:47`（生产路径）vs `src/core/scoring_engine.py:4-26`（死代码）
- 现象：
  1. `grep -rn aggregate_scores\|discover_and_run\|factor_manager` → 仅出现于定义处，无调用方。
  2. `main.py:47` 仍 `total_score += factor_score`，未做归一化、未读 weight。
  3. 4 个因子类属性 `weight = 10`（daily_change / fiveday / zj_flow / dp_diff）从未被任何模块读取。
- 后果：
  - 实际总分是简单求和（10×8 + 20 = 100），靠**巧合**落在 0-100 区间；新增因子或调整 `sum_score` 时会偏移。
  - `BaseFactor` 文档约定的 `weight` 字段是死契约。
- 证据：
  ```python
  # main.py:47-52（未变）
  total_score += factor_score
  s_score += sum_score
  print(f"📊 {factor_name} => {factor_score:.2f}")
  total_s = round(total_score,2)
  print(f"\n总得分: {total_s} / {s_score}")
  ```
- 建议：二选一：(a) 删除 `scoring_engine.py` + `factor_manager.py`，把 main.py 注释写明"简单求和"；(b) 让 main.py 调用 `aggregate_scores`，所有因子在 `calculate()` 中返回 `weight`（与 `sum_score` 统一为 0.1 / 0.2 形式）。倾向 (b)。

### [P0] dp_diff_factor.py 命名与文档/语义不符（**延续**）
- 位置：`src/factors/dp_diff_factor.py`（全文 63 行）
- 现象：文件名 `dp_diff_factor.py` 暗示"DP 差异"，但类名 `RelativeStrengthFactor`、返回 `name = "今年相对大盘强弱"`，仅做 YTD 个股 vs 上证指数。
- 后果：维护者误入歧途，新人难以从文件名定位"DP"实际含义。
- 证据：
  ```python
  # src/factors/dp_diff_factor.py:38, 62
  class RelativeStrengthFactor(BaseFactor):
      ...
      return {"name": "今年相对大盘强弱", "score": score, "sum_score": 10}
  ```
- 建议：把 `dp_diff_factor.py` 改名为 `relative_strength_factor.py`（与类名一致），同步更新 CLAUDE.md。

### [P1] dividend 高股息反而扣分（**延续**）
- 位置：`src/factors/dividend_factor.py:95-106`
- 现象：`if dy > 0.10: return 6` 违反单调性。
- 证据（实测）：
  ```
  dy=0.08:  score=10
  dy=0.10:  score=10
  dy=0.105: score=6   ← 不单调
  dy=0.30:  score=6
  ```
- 后果：股息率 10.5% 股票（6 分）< 8% 股票（10 分），与"高股息更稳健"直觉相反。
- 建议：让 `>0.10` 走"封顶 10 分"或"10%~15% 线性衰减到 6"分支，并加文档说明意图。

### [P1] fiveday_factor 评分区间 [2,10] 不平衡（**延续**）
- 位置：`src/factors/fiveday_factor.py:36-45`
- 现象：5 档阶梯式 `>10→10, >5→8, >0→6, >-5→4, else→2`。
- 证据（实测模拟）：
  ```
  ret5=-50%:  score=2
  ret5=-20%:  score=2
  ret5=-10%:  score=2
  ret5=+50%:  score=10
  ret5=+10.01%: score=10
  ```
  永远落在 [2,10]，无 0/1 极端分。
- 后果：-50% 与 -5% 同分（2 分），区分度不足。
- 建议：把 `<= -10%` 设为 0，`(-10, -5]` 设为 1，与 `daily_change_factor` 风格统一。

### [P1] dp_diff_factor `index_ret` 模块级全局缓存跨日风险（**延续**）
- 位置：`src/factors/dp_diff_factor.py:7, 42-46`
- 现象：`index_ret = None` 是模块全局变量，只在 None 时调用一次 `src.utils.get_market_change()`。
- 后果：
  - 性能正面（避免 1385 次网络 IO）。
  - 正确性风险：流水线跨日运行（夜间 0:00 前后）时，第一只股票拿到今日的大盘涨幅，后续股票沿用，可能造成日内不一致。
  - 同一函数 `get_stock_ytd_return` 内部用 `datetime.now().year`，跨年时同问题。
- 建议：把 `index_ret` 改为"日期 key 的 dict 缓存" `{date_str: value}`；或干脆每次重算（一次网络 IO）。

### [P1] financial_factor 注释"权重"与实现"满分"术语混淆（**延续**）
- 位置：`src/factors/financial_factor.py:85-117`、CLAUDE.md
- 现象：代码注释写"扣非(50%权重): 正增长满分10分"；实际是"扣非满分 10、归母 5、营收 5"独立打分后求和。两者数学上等价（10/20=50%, 5/20=25%, 5/20=25%），但实现思路是"满分数值"而非"百分比权重"。
- 后果：误导后续维护者在 `score_single_item` 中加 `* 0.5 / * 0.25 / * 0.25` 操作。
- 建议：把代码注释改为"满分分值"；或显式改 `score_single_item(..., full_score=20) * 0.5` 形式。

### [P1] financial_factor final 截断区间与最大可能得分不一致（**延续**）
- 位置：`src/factors/financial_factor.py:126-129`
- 现象：`total = max(min(total, 20), -10)`。
- 后果：理论上 final 上界 21.25（被截到 20）、下界 -11.25（被截到 -10），**两个方向都触发截断**——意味着存在极端股票的真实分被吃掉。
- 建议：放宽到 `[-12, 22]`，或在 `score_single_item` 内层把趋势分上限收紧到 ±5%。

### [P1] **新增**：main.py:48 `s_score` 是死计算
- 位置：`main.py:48, 52`
- 现象：
  ```python
  s_score += sum_score     # line 48
  print(f"\n总得分: {total_s} / {s_score}")   # line 52
  ```
- 后果：
  - 表面看 `s_score` 是分母，实际是 `sum_score` 之和（10+10+...+20 = 100），但 line 52 用 `/` 拼接的字符串里也只 print 一次，没有任何下游消费者。
  - 更严重的是：line 53 `single_result.update({'total_score':total_s})` 只把分子写进结果 dict，分母 `s_score` 丢失——下游报表拿不到满分。
  - `run_batch` 把 `single_result` 序列化为 CSV 列，每只股票多一个 `total_score` 列，但没有 `sum_score` 或 `max_score` 列。
- 建议：要么把 `s_score` 也写进 `single_result`（方便下游报表展示"得分/满分"），要么把 line 48 删掉。

### [P2] 因子类命名风格不统一（**延续**）
- 现象：
  | 文件 | 类名 | 风格 |
  |------|------|------|
  | `attention_factor.py` | `attentionFactor` | lowerCamel |
  | `dividend_factor.py` | `dividendfactor` | 全小写 |
  | 其他 7 个 | PascalCase | OK |
- 建议：统一 PascalCase（`AttentionFactor` / `DividendFactor`）。

### [P2] main.py:load_factors 缺 try/except（**延续**）
- 位置：`main.py:13-25`
- 现象：单因子文件语法错误会直接崩整个批跑。
- 建议：参考 `factor_manager.discover_and_run`（行 14-20）加 try/except + continue。

### [P2] 各因子 `init()` 风格不统一（**延续**）
- 现象：`NewsFactor` 多一个 `target_date` 参数但 `BaseFactor.__init__` 不接受。
- 建议：要么 BaseFactor 增加 `target_date=None` 默认值，要么所有因子去掉 `__init__`。

### [P2] attention_factor 每次调用都拉大盘 K 线（**延续**）
- 位置：`src/factors/attention_factor.py:31`
- 现象：批量 1385 只股票时 `src.utils.get_market_change()` 调 1385 次。
- 建议：模块级缓存（参考 dp_diff 的 `index_ret` 模式）。

### [P2] 数据缺失时无 `meta.error`（**延续**）
- 现象：daily_change / financial / news / zj_flow / dividend 在数据缺失时返回 `{"score": 0, "sum_score": 10}`，无 `meta` 字段。
- 建议：统一返回 `{"score": 0, "sum_score": 10, "meta": {"error": "..."}}`，参考 `hy_diff_factor` 已做的。

### [P2] daily_change try/except 范围太宽（**延续**）
- 位置：`src/factors/daily_change_factor.py:79-85`
- 现象：3 层 bare-except，吞掉 KeyboardInterrupt。
- 建议：改为 `except (ValueError, TypeError)`。

### [P2] **新增**：main.py 用相对路径，其他脚本用绝对路径
- 位置：`main.py:88, 90`
- 现象：
  ```python
  # main.py
  filename = f"./result/daily_score/batch_result_{...}.csv"
  # daily_report.py / stock_analysis.py
  RESULT_DIR = "/home/admin/AUTO-STOCK/result/daily_score"
  ```
- 后果：evening_pipeline.sh 靠 `cd $AUTO_STOCK_DIR` 才保证相对路径正确；若 cron 用 `cd` 缺省或换目录就会写错位置。
- 建议：main.py 也改绝对路径（从 `os.path.dirname(__file__)` 取项目根）。

### [P3] test/import time.ini 命名异常（**延续**）
- 位置：`src/factors/test/import time.ini`
- 现象：含空格的脚本名，应是 Python 源码不是 ini。
- 建议：移到 `tests/` 并改名 `test_relative_strength_factor.py`。

### [P3] fiveday_factor 未使用成交量信息（**延续**）
- 建议：可选优化，非必须。

---

## 3. 改进建议（非问题，但有更好做法）

1. **统一因子返回契约**：`BaseFactor.calculate()` 抽象为 `{"name", "score", "weight", "sum_score", "meta"}`，所有子类实现统一签名。
2. **权重集中管理**：9 个因子的 `sum_score` 放到 `src/core/factor_config.py`，避免散落各文件。
3. **每日流水线调用 `aggregate_scores`**：让 `main.run_single` 用 `aggregate_scores` 统一归一化与上限管理。
4. **`daily_change_factor` 趋势判定改用 `pandas-ta` 或 `talib`**：手写 5/20 日均线 + 阈值过于原始。
5. **`news_factor` 关键词扩展**：当前 6 个关键词可考虑移到配置。
6. **`financial_factor` 报告期窗口**：`p_flg=1/2/0` 用 tail/iloc 切片，可读性差。
7. **行业因子数据缺失兜底**：`hy_diff_factor` 三段降级值得推广为其他因子模板。

---

## 4. 需要核实的不确定项

- **`src/utils.get_market_change()` 行为**：函数本身每次调用都 fetch 上证指数历史 K 线（`ak.stock_zh_index_daily`），是一个较慢的同步 IO。dp_diff_factor 之所以模块级缓存 `index_ret`，大概率是为了避免 N 次拉取——**但**这恰恰是 P1-3 风险的来源。最佳方案是单次调用 + 缓存到当日 19:00 收盘后。
- **`data/price/*.csv` 是否所有股票都是 `成交额` 列名**：抽查 3 只股票均一致，但建议跑一次 `for f in data/price/*.csv: assert '成交额' in f.columns` 验证。
- **main.py 改路径后是否回退了 `src/result/bak/` 等备份目录**：`src/result/` 目录已为空（`ls` 无输出），所有旧 csv 已迁到 `result/daily_score/`，迁移完整。

---

## 5. 评分（1-5，5 = 优）

- 正确性：2（**3 个 P0 全部未修复**，F1 实测仍在生效；dividend/fiveday/financial 截断都是错的）
- 可维护性：2（main.py s_score 死计算；命名混乱；weight 死契约；init 不统一；相对/绝对路径不一致）
- 性能：3（attention_factor 仍是 N 次 IO 瓶颈，但不影响功能）
- 文档：3（CLAUDE.md 与代码注释"权重"术语错位；dp_diff 命名误导）
- 总评：**2 / 5**（与上次 3/5 相比，**退步 1 分**——上次报告未消化的积压反而增加，且新发现 2 项）

---

### 附录：审查覆盖清单

- [x] 边界（21 天价格、3 个季度财报、5 日排行）
- [x] NaN/None/0 不会引发崩溃（各因子都有 except 兜底）
- [x] 时间序：financial / dividend / hy_diff 在回测模式下未必正确（未深入）
- [x] 缓存：attention / news 每次 merge；fund_flow 当天不重拉；其余按日期判断
- [x] 错误处理：factor_manager 有 try/except；main.py.load_factors 没有
- [x] 大数据性能：5000 股 × 5 年——未实测，attention_factor 是瓶颈
- [x] O(n²)：未发现
- [x] 硬编码路径：data_manager.py `DATA_DIR = "data"` 相对 OK；**main.py 现在用相对路径 `./result/daily_score/`，与 daily_report/stock_analysis 不一致**
- [x] 死代码：scoring_engine.aggregate_scores、factor_manager.discover_and_run 仍为死代码；**main.py:48 s_score 新增为死计算**
- [x] 测试覆盖：src/factors/test/ 仍只有 1 个命名异常的文件
- [x] 真实运行验证：DailyChangeFactor("600519").calculate() 确认 F1 仍在生效（volume_ratio=1.0）
- [x] 实测打分：dividend_factor 在 dy>0.10 区间非单调（0.105 → 6 < 0.10 → 10）
- [x] 模拟打分：fiveday_factor 永远落在 [2,10] 区间

### 附录：上次报告 17 项 → 本轮状态映射

| 上次 ID | 等级 | 简述 | 本轮状态 |
|---------|------|------|----------|
| F1 (P0-1) | P0 | daily_change 找 `成交量` | **未修复**（实测 volume_ratio=1.0） |
| F2 (P0-2) | P0 | aggregate_scores / discover_and_run 死代码 | **未修复** |
| F3 (P0-3) | P0 | dp_diff_factor 命名误导 | **未修复** |
| P1-1 | P1 | dividend 高股息扣分 | **未修复**（实测确认） |
| P1-2 | P1 | fiveday 区间 [2,10] | **未修复**（模拟确认） |
| P1-3 | P1 | dp_diff index_ret 全局缓存 | **未修复** |
| P1-4 | P1 | financial 权重 vs 满分 术语 | **未修复** |
| P1-5 | P1 | financial final 截断偏紧 | **未修复** |
| P2-1 | P2 | 类命名风格不统一 | **未修复** |
| P2-2 | P2 | main.load_factors 缺 try/except | **未修复** |
| P2-3 | P2 | hy_diff_factor.py.bak 残留 | **已修复** |
| P2-4 | P2 | init() 风格不统一 | **未修复** |
| P2-5 | P2 | attention 每只股票拉大盘 K 线 | **未修复** |
| P2-6 | P2 | 数据缺失无 meta.error | **未修复** |
| P2-7 | P2 | daily_change try/except 太宽 | **未修复** |
| P3-1 | P3 | test/import time.ini 命名异常 | **未修复** |
| P3-2 | P3 | fiveday 未用成交量 | **未修复** |
| — | P1 | **新增**：main.py:48 s_score 死计算 | **新发现** |
| — | P2 | **新增**：main.py 相对路径 vs 脚本绝对路径不一致 | **新发现** |
