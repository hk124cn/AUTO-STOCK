# 因子系统审查 - 草稿笔记

## 审查范围
- `src/core/base_factor.py`
- `src/core/factor_manager.py`
- `src/core/scoring_engine.py`
- `src/factors/*.py`（9 个）
- `main.py`

## 整体架构
- BaseFactor 基类定义 `calculate()` 接口
- factor_manager / main.py 用 `pkgutil.iter_modules` 动态发现因子
- 9 个因子总分 100 分：
  - attention 10
  - daily_change 10
  - dividend 10
  - financial 20
  - fiveday 10
  - hy_diff 10
  - news 10
  - zj_flow 10
  - dp_diff 10

## 关键代码片段摘录

### base_factor.py
```python
class BaseFactor:
    def __init__(self, code, name=None):
        self.code = code
        self.name = name or ""

    def calculate(self) -> Dict:
        raise NotImplementedError("子类必须实现 calculate 方法")
```
无 docstring 提示 weight 字段，但注释提到 "name, score, weight, meta"。

### scoring_engine.py - 关键发现
```python
def aggregate_scores(factors):
    wsum = sum(f.get('weight', 0) for f in factors)
    if wsum == 0:
        n = len(factors)
        for f in factors:
            f['_norm_weight'] = 1.0 / n
    else:
        for f in factors:
            f['_norm_weight'] = f.get('weight', 0) / wsum

    total = 0.0
    for f in factors:
        total += f.get('score', 0) * f['_norm_weight']
    return {"total_score": round(total, 2), "details": factors}
```
- 但所有因子返回的 dict 都没有 'weight' 字段！只有 'sum_score'。
- 所以 wsum 永远 = 0，走均等权重分支。

### main.py - 入口
```python
def load_factors():
    factors = []
    for _, module_name, _ in pkgutil.iter_modules([factors_path]):
        module = importlib.import_module(f"src.factors.{module_name}")
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, BaseFactor) and obj is not BaseFactor:
                factors.append(obj)
    return factors

def run_single(code):
    for cls in factor_classes:
        factor = cls(code, name)
        result = factor.calculate()
        factor_name = result.get('name', '因子X')
        factor_score = result.get('score', 0)
        sum_score = result.get('sum_score', 10)
        single_result.update({factor_name: factor_score})
        total_score += factor_score
        s_score += sum_score
```
- main.py 直接把每个因子的 score 相加（简单求和，不除以 sum_score 归一化）。
- 这意味着单个因子得分上限会影响总分上限。
- 财务因子满分 20，其他 8 个各 10 分 → 总分上限 = 20+10*8 = 100。
- 但 financial_factor.py 内部 total 限制为 [-10, 20]，实际可能为 -10~+20。
- daily_change_factor 内部 final_score 限制 [0, 10]，但 _base_scores 有 9 分值（最大 9）。

### 1. attention_factor.py
- 用 `get_attention(code)` → `data/attention/{code}.csv`
- 列名："交易日"、"用户关注指数"
- 评分：base_score + stable_bonus，限制 [1, 10]
- market_change 是全局大市涨幅，使用 src.utils.get_market_change()

```python
def calc_focus_score(df, market_change):
    mean_focus = df["用户关注指数"].mean()
    std_focus = df["用户关注指数"].std()
    base_score = (mean_focus - 80) / 2 - std_focus / 4 + market_change / 10
    base_score = max(0, min(7, base_score))   # ← 这里限制 [0, 7]
    if mean_focus < 85 and std_focus < 3:
        stable_bonus = 2.5 - (std_focus / 3)
    else:
        stable_bonus = 0
    final_score = base_score + stable_bonus
    final_score = round(min(10, max(1, final_score)), 1)   # ← 限制 [1, 10]
    return final_score
```
- df.tail(min(20, len(df)))：最多取最近 20 天
- 数据缺失 → 返回 0 (与 sum_score=10 不一致)
- 注：base_score 限制 [0,7] 但 final 是 [1,10]，边界处理 OK。
- market_change 是网络 IO（ak.stock_zh_index_daily），每个股票计算都会调用 → 性能瓶颈

### 2. daily_change_factor.py
```python
def trend_aware_change_score(today_change, trend_status, volume_ratio=1.0):
    base_scores = {
        'strong_up': {'ranges': [...], 'scores':[8,6,4,2,1,0]},
        ...
    }
    final_score = min(10, max(0, base_score * volume_factor))
    return round(final_score)
```
- 需要 21 天价格数据
- 字段使用中文列名 '日期'、'收盘'、'成交量'
- 注意：close_col=收盘，volume_col=成交量，但 price CSV 实际列是 "成交额"，不是"成交量"！
- 查看 data/price/000001.csv 头部：日期,收盘,成交额,开盘,最高,最低
- 这里 daily_change_factor.py 用 volume_col = '成交量' 会导致 KeyError 或永远走 volume_ratio=1.0 分支。
- 但有 except 兜底 (KeyError → 1.0)？看代码：
```python
if volume_col in recent.columns and len(recent) >= 20:
    vol_mean = recent[volume_col].rolling(20).mean().iloc[-1]
    volume_ratio = recent[volume_col].iloc[-1] / vol_mean if vol_mean > 0 else 1.0
else:
    volume_ratio = 1.0
```
- '成交量' 不在 columns → volume_ratio = 1.0 → 永不触发 volume_factor
- 这是个 bug：应该用 "成交额" 或兼容两者

### 3. dividend_factor.py
- 用 get_dividend + get_price
- 股息率 = sum(派息) / 价格
- 评分：dy > 0.10 → 6 分（非线性"封顶"）；分段线性 0~10
- 注意：> 0.10 时返回 6，而不是 10 — 这是反直觉设计。
- 数据列名 '公告日期' / '实施公告日' / '除权日' / '股权登记日' 4 选 1

### 4. financial_factor.py
- CLAUDE.md 说 "扣非 50% 权重，营收 25%" 但实际代码：
  - 扣非满分 10 分，归母满分 5 分，营收满分 5 分 → 总分 20
  - 这是**固定分值**而不是按权重比例
  - 内部计算：3 项独立打分再相加
  - 趋势分单项最多 ±10% × full_score（最高 ±1 分 for 扣非；±0.5 分 for 归母/营收）
- 例：茅台(600519) 2025Q4 扣非-30.83% → 基础分 = 50 × (-30.83/100) / 10 = -1.54；归母 -30.34% → -0.76；营收 -19.35% → -0.48 → 总和 = -2.78 + 趋势分。CLAUDE.md 例值 -4.29 是因为趋势分叠加。
- final = max(min(total, 20), -10)
- base_total 范围：[10+5+5=20(全正), -5-2.5-2.5=-10(全负)]（rate=-100% 时）
- 实际 rate=-100% → -5/-2.5/-2.5 → -10（封顶）

### 5. fiveday_factor.py
- 取最近 6 天收盘价：start=第一天，end=最后一天，差值百分比
- 简单阶梯评分：>10 → 10, >5 → 8, >0 → 6, >-5 → 4, else → 2
- 注：score 永远在 [2, 10]，无 0 或 1
- 没有负评分机制，下跌越凶得分可能反而不太低（跌超 -5% 仍是 2）
- 区间不平滑，比如 ret5=5.001 → 8 分；ret5=4.999 → 6 分

### 6. hy_diff_factor.py
- 行业因子，3 维度加权：relative 60% + momentum 20% + absolute 20%
- 总分范围 [0, 10]，永远不会为负
- 数据缺失时返回 0
- 注：score=0 时与 sum_score=10 比例 = 0；score=10 时比例 = 1.0（满分）
- 这是相对公平的设计

### 7. news_factor.py
- 用 get_news（按发布日期排序的累积 CSV）
- target_date 默认今天，filter 到 target 23:59:59
- 比较 recent_3 vs prev_3 的非负面新闻数量
- 关键词加权：["重组", "并购", "中标", "定增", "算力", "AI"]
- 评分上限 10 分
- 注：target_date 在 __init__ 时设定为今天，但 score 计算时新闻过滤时间是当天结束

### 8. zj_flow_factor.py
- 用 get_stock_fund_flow，从 5 日排行数据中查找单股
- 评分维度：净额方向 +3、换手率 +3、阶段涨幅 +3、净额规模 +1
- 注：换手率检查 10<=x<=20，>80% 才 0，但 0<turnover<10 也是 +1
- "阶段涨跌幅" 在 0~15% 给 +3，但 0~5% 给 0? → 看代码：0<=change_pct<=15 → +3。change_pct=-1% → 0 分。OK。
- 最大分 = 3+3+3+1 = 10

### 9. dp_diff_factor.py
- 用 `datetime.now().year` 计算 YTD 涨幅
- 强烈依赖当前系统时间，回测时不会自动调整
- `index_ret` 是模块级全局变量，但只在 None 时才获取一次
- 文件名虽叫 `dp_diff_factor.py` 但类名是 `RelativeStrengthFactor`，逻辑是"个股 vs 大盘 强弱"
- 全局缓存 bug：在批量评分时，第一个股票跑完后 index_ret 就固定了。如果跨年（极少见），不会刷新。

## 数据流问题

### 价格列名不一致
- daily_change_factor.py: volume_col = '成交量'
- 实际 data/price/*.csv 列：日期,收盘,成交额,开盘,最高,最低
- 没有'成交量'列 → 永远走 volume_ratio = 1.0 分支
- 影响：volume_factor 永远不触发，加分逻辑失效

### 价格日期格式
- data/price/000001.csv 第一行：`20160104`（8位字符串）
- 各因子用 `pd.to_datetime(df['日期'].astype(str), format='%Y%m%d')`
- daily_change_factor.py 有 try/except 兜底

### 股票代码前导零
- data/price/000001.csv 文件名保留前导零
- normalize_code() 函数处理 6/8/其他情况
- main.py batch 模式 `code = str(code).zfill(6)` → OK
- 但 hy_diff_factor.py 的 _load_industry_mapping() 用 `dtype={'股票代码': str, '行业代码': str}` 读取 CSV → 保留前导零 OK
- risk: 如果某个文件代码列用 int 类型，前导零会被吞

## 缓存策略
- get_attention: 每次调用都远程拉新数据，merge 到本地 → IO 频繁
- get_news: 同上
- get_fund_flow_5day: 当天已更新就不重拉
- get_finance: local 优先，否则重拉
- get_dividend: 同上

## 异常吞噬
- factor_manager.discover_and_run:
  ```python
  except Exception as e:
      print(f"加载因子 {module_name} 失败: {e}")
      continue
  ```
- main.py load_factors() 没有 try/except
- 各因子 calculate() 内大多没有 try/except（除 dividend/financial 等）
- 若一个因子 calculate() 抛错，整个 run_single 崩溃？

## 错误处理
- factor_manager.py: 因子加载失败 → 打印 + continue（OK）
- factor_manager.py: 实例化失败 → 打印 + 跳过当次循环（但整个循环不会因单次失败退出）
- main.py load_factors: 没有 try/except，模块 import 失败整个崩溃

## 9 个因子结构不一致性
| 因子 | class 名 | has init | has weight class attr | 返回 sum_score |
|------|---------|----------|----------------------|---------------|
| attention | attentionFactor | yes | no | 10 |
| daily_change | DailyChangeFactor | no | yes (10) | 10 |
| dividend | dividendfactor (全小写!) | yes | no | 10 |
| financial | FinancialFactor | yes | no | 20 |
| fiveday | FiveDayReturnFactor | no | yes (10) | 10 |
| hy_diff | IndustryDiffFactor | no | no | 10 |
| news | NewsFactor | yes | no | 10 |
| zj_flow | FundFlowFactor | no | yes (10) | 10 |
| dp_diff | RelativeStrengthFactor | no | yes (10) | 10 |

- 命名风格混乱：attentionFactor、dividendfactor（小写）、其他 PascalCase
- 有些有 init()，有些没有（继承自 BaseFactor）
- class weight 属性 vs calculate() 返回 dict 里的 weight 字段，**不一致**
- main.py 没有用 class weight，只用 sum_score

## 关键文件路径
- /home/admin/AUTO-STOCK/src/core/base_factor.py
- /home/admin/AUTO-STOCK/src/core/factor_manager.py
- /home/admin/AUTO-STOCK/src/core/scoring_engine.py
- /home/admin/AUTO-STOCK/src/factors/attention_factor.py
- /home/admin/AUTO-STOCK/src/factors/daily_change_factor.py
- /home/admin/AUTO-STOCK/src/factors/dividend_factor.py
- /home/admin/AUTO-STOCK/src/factors/financial_factor.py
- /home/admin/AUTO-STOCK/src/factors/fiveday_factor.py
- /home/admin/AUTO-STOCK/src/factors/hy_diff_factor.py
- /home/admin/AUTO-STOCK/src/factors/news_factor.py
- /home/admin/AUTO-STOCK/src/factors/zj_flow_factor.py
- /home/admin/AUTO-STOCK/src/factors/dp_diff_factor.py
- /home/admin/AUTO-STOCK/src/factors/hy_diff_factor.py.bak  (bak 文件未清理)
- /home/admin/AUTO-STOCK/main.py
- /home/admin/AUTO-STOCK/src/datafactory/data_manager.py
- /home/admin/AUTO-STOCK/src/utils.py

## 待确认事项
- bak 文件为什么还在？
- scoring_engine.py aggregate_scores() 是否被实际调用？grep 确认。
- weight class attr 是否实际生效？
- dp_diff_factor 名字叫"DP差异"但逻辑是"个股 vs 大盘 强弱"——名字不符。

## 检查 scoring_engine 是否被使用