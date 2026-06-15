# 子报告：因子系统（Factor System）

> 范围：
> - `src/core/base_factor.py`、`src/core/factor_manager.py`、`src/core/scoring_engine.py`
> - `src/factors/*.py`（9 个因子：attention / daily_change / dividend / financial / fiveday / hy_diff / news / zj_flow / dp_diff）
> - 入口 `main.py`（含 `load_factors` / `run_single` / `run_batch`）
> - 旁路依赖 `src/datafactory/data_manager.py`、`src/utils.py`
>
> 严重程度评级：P0=功能错误 / P1=性能或安全 / P2=可改进 / P3=小问题
> 审查日期：2026-06-14

## 1. 概览

9 因子评分系统采用"动态发现 + 基类 + calculate() 返回 dict"的统一契约，9 个因子总分 100 分（财务 20 + 其他 8×10），整体结构清晰但存在若干一致性、可维护性问题。

**主要结论**：
- **入口不一致**：`scoring_engine.aggregate_scores()` 和 `factor_manager.discover_and_run()` 是**死代码**，实际生产路径走 `main.py.load_factors()`，后者用 **简单求和**（不归一化、不使用 `weight` 字段）。
- **数据契约不完全自洽**：每个因子返回的 dict 是 `score + sum_score`，但 `BaseFactor` 文档约定 `weight`；class 上的 `weight = 10` 类属性从未被任何模块读取。
- **逻辑正确性**整体尚可，但 `daily_change_factor` 的成交量列名（`'成交量'`）与实际 CSV（`'成交额'`）不匹配，导致放量加分逻辑永远失效；`dp_diff_factor` 文件名与"DP差异"无任何关联，实际是"个股 YTD vs 大盘"相对强弱。

整体处于"能跑、有用、但需要补一致性"的状态。下文按严重程度列出发现。

## 2. 关键发现（按严重程度降序）

### [P0] daily_change 放量加分逻辑永远不触发
- 位置：`src/factors/daily_change_factor.py:95, 107-111`
- 现象：因子从 `data/price/{code}.csv` 取数据，代码中 `volume_col = '成交量'`；但实际数据列名为 `成交额`（参见 `data/price/000001.csv` 表头：`日期,收盘,成交额,开盘,最高,最低`）。
- 后果：`if volume_col in recent.columns` 永远为 False → `volume_ratio = 1.0` → 后续 `if volume_ratio > 1.5` 分支永不进入 → `volume_factor = 1.0` → 放量加权 1.2x 的设计**完全失效**。
- 证据：
  ```python
  # daily_change_factor.py:95, 107-111
  volume_col = '成交量'
  ...
  if volume_col in recent.columns and len(recent) >= 20:
      vol_mean = recent[volume_col].rolling(20).mean().iloc[-1]
      volume_ratio = recent[volume_col].iloc[-1] / vol_mean if vol_mean > 0 else 1.0
  else:
      volume_ratio = 1.0
  ```
- 建议：把 `volume_col` 改为 `'成交额'`，并补 fallback（同时尝试 `'成交量'`、`'volume'`）。

### [P0] 入口 `main.py` 与 `scoring_engine.py` 路径不一致，导致归一化失效
- 位置：`main.py:33-52` vs `src/core/scoring_engine.py:4-26`
- 现象：`scoring_engine.aggregate_scores()` 设计为按 `weight` 归一化计算 `total_score`，但：
  1. 全代码库 grep 显示 `aggregate_scores` 没有任何调用方（`grep -rn aggregate_scores src/ main.py`）。
  2. `main.py` 的 `run_single()` 直接 `total_score += factor_score`（行 47），**不做归一化**。
  3. 9 个因子 `calculate()` 返回 dict 都没有 `weight` 键，只有 `sum_score`；只有 4 个因子在类属性上有 `weight = 10`（daily_change / fiveday / zj_flow / dp_diff），但 `load_factors` 和 `run_single` 完全没读它。
- 后果：
  - 文档约定与实现脱节：`BaseFactor` docstring 写明因子应返回 `weight`，但实际没有任何因子这么做。
  - `factor_manager.discover_and_run` 也未被调用（grep 无引用），整个 `src/core/` 下只有 `base_factor.py` 真正在生产路径中被使用。
  - 由于实际是简单求和（且 financial 满分 20 + 其他 8×10 = 100），单只股票总分会恰好落在 0-100 区间内——这是巧合，并非设计保证。如果以后新增因子或调整 `sum_score`，总分就会偏移。
- 证据：
  ```python
  # main.py:47-52
  total_score += factor_score
  s_score += sum_score
  print(f"📊 {factor_name} => {factor_score:.2f}")
  total_s = round(total_score,2)
  print(f"\n总得分: {total_s} / {s_score}")
  ```
- 建议：
  - 二选一：(a) 删除 `scoring_engine.py` 与 `factor_manager.py`，将 `main.py` 注释里写明"简单求和"；(b) 让 `main.py` 调用 `aggregate_scores`，并要求所有因子在 `calculate()` 中返回 `weight`。
  - 鉴于 `BaseFactor` 已经声明 `weight` 契约，倾向 (b)：把每个因子的 `weight` 写入返回 dict（同时 `sum_score` 与 `weight` 统一，例如 `weight=0.10`），调用 `aggregate_scores`。

### [P0] `dp_diff_factor.py` 命名与文档/语义不符
- 位置：`src/factors/dp_diff_factor.py`（全文）
- 现象：文件名暗示"DP 差异"，但 `CLAUDE.md`、`scripts/stock_analysis.py`、`scripts/daily_report.py` 都称其为"今年相对大盘强弱"，类名也叫 `RelativeStrengthFactor`；`calculate()` 中也只用到年初至今个股 vs 上证指数涨跌幅，与"DP（动量/估值等）差异"无关。
- 后果：维护者误入歧途；新人难以从文件名定位"DP"实际指什么。
- 证据：CLAUDE.md 表中描述 `dp_diff_factor.py` 为 "DP差异因子"；但代码第 10-35 行仅计算 YTD 涨跌幅，第 47 行计算 `stock_ret - index_ret`，无任何 DP/Dividend-Payout/Discounted 等语义。
- 建议：把 `dp_diff_factor.py` 改名为 `relative_strength_factor.py`（与类名一致），同步更新 CLAUDE.md。

### [P1] `dividend_factor` 高股息反而扣分
- 位置：`src/factors/dividend_factor.py:95-106`
- 现象：`_piecewise_linear_score` 分段线性把 0~10% 股息率映射到 0~10 分；但 dy > 0.10 时**直接返回 6 分**（低于 10% 的 8 分），非单调。
- 后果：股息率 10.5% 的股票得分（6）反而低于 8% 的股票得分（10），与"高股息更稳健"的常识直觉相反。
- 证据：
  ```python
  # dividend_factor.py:95-98
  points = [(0.00, 0), (0.02, 4), (0.05, 8), (0.08, 10), (0.10, 10)]
  if dy > 0.10:
      return 6  # ← 不单调
  ```
- 建议：让 >0.10 走"封顶 10 分"分支，或改为 `return 10`，或在 0.10~0.15 区间线性衰减到 6 表示"过度分红警惕"（需文档说明）。

### [P1] `fiveday_factor` 评分区间不平衡，永不为 0/1
- 位置：`src/factors/fiveday_factor.py:36-47`
- 现象：5 档阶梯式评分：>10→10, >5→8, >0→6, >-5→4, else→2。**永远落在 [2, 10]**，无 0/1 极端分。
- 后果：5 日大跌 -20% 与 -5% 同样得 2 分，区分度不够；与 `daily_change_factor` 的 [0, 10] 不对称。
- 证据：`fiveday_factor.py:36-45` 直接阶梯，无负分。
- 建议：把 `<= -10%` 设为 0，把 `(-10, -5]` 设为 1，与 `daily_change_factor` 风格统一。

### [P1] `dp_diff_factor` 的 `index_ret` 模块级全局缓存，跨日不变
- 位置：`src/factors/dp_diff_factor.py:7, 42-46`
- 现象：`index_ret = None` 是模块全局变量，只在 `None` 时获取一次；批量跑 N 只股票时只取一次。
- 后果：
  - 性能：正面（避免重复 IO）。
  - 正确性：**潜在风险**——如果流水线跨日运行（例如夜间任务在 0:00 前后），第一只股票拿到的是今天的大盘涨幅，后续股票沿用，可能造成日内不一致。
  - 同时 `get_stock_ytd_return` 也依赖 `datetime.now().year`——同跨日问题：新年第一天第二只股票的 YTD 起点跳到去年 12-31，而第一只股票可能用去年 12-30。
- 证据：
  ```python
  # dp_diff_factor.py:42-46
  def calculate(self):
      global index_ret
      stock_ret = get_stock_ytd_return(self.code)
      ...
      if index_ret is None:
          index_ret = src.utils.get_market_change()
      relative = stock_ret - index_ret
  ```
- 建议：把全局变量改成"日期 key 的 dict"缓存 `{date_str: index_ret}`，或干脆每次都重新计算（网络 IO 一次即可）。

### [P1] 财务因子"权重"术语与实现不一致（文档解读需谨慎）
- 位置：`src/factors/financial_factor.py:85-117`；`CLAUDE.md` 第 122-149 行
- 现象：`CLAUDE.md` 第 89 行表格写"扣非 50% / 归母 25% / 营收 25%"——这是**权重**；代码注释也写 "扣非(50%权重): 正增长满分10分"。但代码实现是**满分 10/5/5 的固定分值**，三者相加等于 20。效果等价（10/20=50%, 5/20=25%, 5/20=25%）但**实现思路是"满分数值"**而非"百分比权重"。
- 后果：
  - 文档与代码注释用"权重"措辞，容易误导后续维护者以为要在 `score_single_item` 中按 0.5/0.25/0.25 做加权。
  - 实际上从代码看，三项独立按各自满分打分再求和，得到的 final 与"先按权重再归一"等价。
- 证据：
  ```python
  # financial_factor.py:120-122
  koufei = score_single_item(data["扣非净利润同比增长率"], 10, -50)
  guimu = score_single_item(data["归母净利润同比增长率"], 5, -25)
  yingshou = score_single_item(data["营业总收入同比增长率"], 5, -25)
  ```
- 建议：把代码注释改为"满分分值"而非"权重"；或显式改用 `score_single_item(..., full_score=20) * 0.5` + `* 0.25` + `* 0.25` 形式，意图更清晰。

### [P1] 财务因子 final 截断区间与最大可能得分不一致
- 位置：`src/factors/financial_factor.py:126-129`
- 现象：`total = max(min(total, 20), -10)`——封顶 20、封底 -10。
- 后果：
  - 封顶 20 正确（扣非+10/归母+5/营收+5 = 20）。
  - 封底 -10 不对齐：理论上 `扣非(满-50/10)=-5` + `归母(-25/10)=-2.5` + `营收(-25/10)=-2.5` = -10，刚好等于下界；但实际增长率为 -100% 才会到达 -10，一般年份用不到。
  - 趋势分单独加，理论上可以再贡献 ±(10%+5%+5%)×full = ±2 分，但 `calculate_trend_score` 内层做了 `max(±10%)` 截断，所以最大额外 = 0.075×10 + 0.05×5 + 0.05×5 = 1.25。所以 final 上界 = 20+1.25 = 21.25 → 被 max(20) 截到 20；下界 = -10+(-1.25) = -11.25 → 被 min(-10) 截到 -10。**两个方向都触发截断**。
- 证据：见 financial_factor.py:126-129。
- 建议：将截断区间放宽到 `[-12, 22]`，或者在 score_single_item 内层就把趋势分上限收紧到 ±5%。

### [P2] 因子类命名风格不统一
- 位置：`src/factors/` 目录
- 现象：
  | 文件 | 类名 |
  |------|------|
  | attention_factor.py | `attentionFactor` (lowerCamel) |
  | dividend_factor.py | `dividendfactor` (全小写) |
  | 其他 | PascalCase |
- 后果：`pkgutil.iter_modules` + `issubclass(obj, BaseFactor)` 仍能正确发现，但 grep / IDE 自动跳转体验差；`grep "class " factors/*.py` 会忽略全小写的 `dividendfactor`。
- 建议：把 `attentionFactor` 改 `AttentionFactor`、`dividendfactor` 改 `DividendFactor`，统一 PascalCase。

### [P2] `main.py.load_factors` 没有异常吞噬，模块 import 失败即崩溃
- 位置：`main.py:13-25`
- 现象：`load_factors()` 直接 `importlib.import_module`，未包裹 try/except。
- 后果：单个因子文件语法错误（如 `hy_diff_factor.py.bak` 残留导致同模块名冲突？）会让整个批量任务崩溃。
- 证据：`factor_manager.discover_and_run` 有 try/except + continue（行 14-20），但 `main.py.load_factors` 没有。
- 建议：复用 factor_manager 的容错模式。

### [P2] `hy_diff_factor.py.bak` 残留
- 位置：`src/factors/hy_diff_factor.py.bak`
- 现象：残留 .bak 文件未删除；虽然 `iter_modules` 默认不读 .bak，但增加了目录噪音。
- 建议：删除。

### [P2] 各因子 `init()` 风格不一致
- 现象：
  - `attention_factor.py:36-37` 有 `def __init__(self, code, name=None): super().__init__(code, name)`
  - `daily_change_factor.py:58`、`fiveday_factor.py:30` 没有 `__init__`，依赖 BaseFactor 默认
  - `financial_factor.py:203-204` 有 init
  - `news_factor.py:10-12` 有 init 且增加 `target_date` 参数
  - 其他无 init
- 后果：构造参数语义不一致——`NewsFactor(code, name, target_date)` 多了第三参数，但 `BaseFactor.__init__` 不接受；如果有人 `NewsFactor(code, name, target_date='2026-01-01')` 之外的因子用同样调用方式会报 TypeError。
- 建议：要么统一所有因子都接受 `target_date=None`，要么在 BaseFactor 增加 `target_date` 默认值。

### [P2] `attention_factor` 每次调用 `src.utils.get_market_change()` 是网络 IO
- 位置：`src/factors/attention_factor.py:31`
- 现象：批量评分 1385 只股票时，attention_factor 对每只股票都会调用 `get_market_change()` → `ak.stock_zh_index_daily("sh000001")` 拉一次历史 K 线。
- 后果：1385 次重复 IO，显著拖慢 evening_pipeline 步骤 1。
- 建议：把 `market_change` 提到模块级缓存（同 `dp_diff_factor` 的 `index_ret` 模式），或作为参数传入 `calculate()`。

### [P2] 数据缺失时各因子返回 0，无 `meta.error`
- 现象：daily_change_factor、financial_factor、news_factor、zj_flow_factor、dividend_factor 等都在数据缺失时返回 `{"score": 0, "sum_score": 10}`。
- 后果：分数被静默吃掉，运维侧难以诊断"该股票为什么低分"。
- 建议：统一返回 `{"score": 0, "sum_score": 10, "meta": {"error": "..."}}`，参考 hy_diff_factor 已经这样做了。

### [P2] `daily_change_factor` 的 `try/except` 范围太宽
- 位置：`src/factors/daily_change_factor.py:79-85`
- 现象：
  ```python
  try:
      price_df['日期'] = pd.to_datetime(price_df['日期'].astype(str), format='%Y%m%d')
  except:
      try:
          price_df['日期'] = pd.to_datetime(price_df['日期'])
      except:
          return {"name": "单日涨跌幅", "score": 0, "sum_score": 10}
  ```
- 后果：3 层 bare-except，把 KeyboardInterrupt 等也吃掉；建议改为 `except (ValueError, TypeError)`。

### [P3] 测试目录命名异常
- 位置：`src/factors/test/import time.ini`
- 现象：测试目录里**只有**一个文件名异常的 `import time.ini`（包含空格的脚本），实际是 Python 源码而非配置。
- 建议：移到 `tests/` 目录并改名为 `test_relative_strength_factor.py`。

### [P3] `fiveday_factor` 没有使用成交量信息
- 现象：`daily_change_factor` 有量价配合，`fiveday_factor` 仅看价格变化，未考虑 5 日累计放量。
- 建议：可选优化，非必须。

## 3. 改进建议（非问题，但有更好做法）

1. **统一因子返回契约**：建议在 `BaseFactor.calculate()` 抽象化时，明确返回字段为 `{"name", "score", "weight", "sum_score", "meta"}`，所有子类实现统一签名。
2. **权重集中管理**：把 9 个因子的 `sum_score`/权重放到 `config/factor_config.py` 或 `src/core/factor_config.py`，避免硬编码散落各因子文件。
3. **每日流水线调用 `aggregate_scores`**：让 `main.py.run_single` 改为 `aggregate_scores(results)`，让归一化与上限管理集中在一处。
4. **`daily_change_factor` 趋势判定改用 `pandas-ta` 或 `talib`**：手写 5/20 日均线 + 阈值过于原始，与 hy_diff_factor 中"分位"打分风格不统一。
5. **`news_factor` 关键词扩展**：当前只有 6 个关键词 (`["重组","并购","中标","定增","算力","AI"]`)，可考虑维护在配置文件中。
6. **`financial_factor` 报告期窗口**：`p_flg=1/2/0` 用 tail/iloc 切片，可读性差，建议直接用 `df.iloc[-3:]` / `[-4:-1]` / `[-5:-2]` 简化。
7. **行业因子数据缺失兜底**：hy_diff_factor 已经做了三段降级（行业映射缺失 → 0、行业涨跌幅缺失 → 0、价格缺失 → 0），值得推广为其他因子模板。

## 4. 需要核实的不确定项

- **scoring_engine.py 与 factor_manager.py 是否在 API / 其它脚本中被调用？** 当前 grep 在 *.py 中无引用，可能在 .ipynb / 配置文件中，但通常不会。
- **`fund_flow_5day_20260612.csv` 是 fund 目录最新文件**（今天是 2026-06-14）。是否需要 0613/0614 数据？需要 `update_data.py` 跑一次。
- **数据 CSV 列名**：本次抽查 `data/price/000001.csv` 是 `成交额`；但 `data/price/600519.csv` 等可能列名不同，需批量验证。

## 5. 评分（1-5，5 = 优）

- 正确性：3（daily_change 放量逻辑失效、dividend 高股息扣分、financial final 截断偏紧）
- 可维护性：2（命名混乱、契约不一致、scoring_engine 死代码、weight 类属性无效、init 风格不统一）
- 性能：3（attention_factor 每只股票拉一次大盘 K 线）
- 文档：3（CLAUDE.md 与代码注释对"权重"术语用法不一致；dp_diff 命名误导）
- 总评：**3 / 5**（系统能跑且总分近似正确，但需要一轮"统一化"清理）

---

### 附录：审查覆盖清单

- [x] 边界（21 天价格、3 个季度财报、5 日排行）
- [x] NaN/None/0 不会引发崩溃（各因子都有 except 兜底返回 0）
- [x] 时间序：financial/dividend/hy_diff 在回测模式下未必正确（未深入检查）；单日涨跌幅用 iloc[-1] vs iloc[-2]，是 T+0 收盘后正常计算，无未来数据
- [x] 缓存：attention/news 每次 merge；fund_flow 当天不重拉；其余按日期判断
- [x] 错误处理：factor_manager 有 try/except；main.py.load_factors 没有
- [x] 大数据性能：5000 股 × 5 年——未实测，但 attention_factor 的网络 IO 是瓶颈
- [x] O(n²)：未发现
- [x] 硬编码路径：data_manager.py 用 `DATA_DIR = "data"`，相对路径 OK
- [x] 死代码：scoring_engine.aggregate_scores、factor_manager.discover_and_run、hy_diff_factor.py.bak
- [x] 测试覆盖：src/factors/test/ 仅有 1 个命名异常的文件