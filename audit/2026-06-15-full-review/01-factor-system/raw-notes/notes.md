# Raw notes — 因子系统复查（2026-06-16）

> 审查日期：2026-06-16
> 审查者：#1-因子系统 subagent
> 范围：src/core/* + src/factors/* + main.py
> 任务：对比上次 06-14 报告的 P0/P1/P2/P3，逐项验证修复状态

## 工作树改动（git diff）

```
$ git diff --stat src/factors/ src/core/ main.py
 main.py | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)
```

仅 main.py 改 2 行：把批量结果输出从 `./src/result/...` 迁到 `./result/daily_score/...`。
src/factors/ 和 src/core/ 完全未改动。

```
$ git diff main.py
-        filename = f"./src/result/batch_result_{datetime.today().strftime('%Y%m%d')}.csv"
+        filename = f"./result/daily_score/batch_result_{datetime.today().strftime('%Y%m%d')}.csv"
-        filename = f"./src/result/{in_fname}.csv"
+        filename = f"./result/daily_score/{in_fname}.csv"
```

## 上次 P0 验证

### F1: daily_change_factor 找 `成交量` 而非 `成交额`（P0-1）
- 位置：src/factors/daily_change_factor.py:95, 107-111
- 现状：
  ```python
  # line 95
  volume_col = '成交量'
  # line 107
  if volume_col in recent.columns and len(recent) >= 20:
  ```
- 实测 CSV 列名（600519.csv、000001.csv、600660.csv）：`日期,收盘,成交额,开盘,最高,最低`
- **运行验证**：`DailyChangeFactor("600519").calculate()` 返回 `meta.volume_ratio: 1.0`（即"成交量列不存在"分支被命中，volume_factor=1.0）。
- 结论：**F1 未修复，仍然是 P0**。

### F2: aggregate_scores / discover_and_run 死代码（P0-2）
- 全代码库 grep 验证：
  ```
  $ grep -rn "aggregate_scores\|discover_and_run\|factor_manager" --include='*.py'
  /home/admin/AUTO-STOCK/src/core/factor_manager.py:9:def discover_and_run(...)
  /home/admin/AUTO-STOCK/src/core/scoring_engine.py:4:def aggregate_scores(...)
  ```
  → 无任何调用方。
- `main.py:47` 仍是 `total_score += factor_score`（简单求和）。
- `weight` 字段实际从未被读取：
  ```
  $ grep -rn "\.weight\b\|'weight'" src/ main.py api/ scripts/
  ```
  - src/core/scoring_engine.py:11,19 读了（但 aggregate_scores 没人调用）
  - src/factors/hy_diff_factor.py 内部 3 轴 weight（是局部 SCORE_CONFIG，与类级 weight 无关）
  - 类级 `weight = 10` 没有任何读取方
- 结论：**F2 未修复，仍然是 P0**。

### F3: dp_diff_factor 文件名误导（YTD 相对大盘）
- 文件仍是 `src/factors/dp_diff_factor.py`
- 类名仍是 `RelativeStrengthFactor`
- 全局 `index_ret` 缓存仍在 line 7
- 结论：**F3 未修复，仍然是 P0**。

## 重要新发现

### 真实运行：daily_change_factor 跑 600519
```
{'name': '单日涨跌幅', 'score': 2, 'sum_score': 10,
 'meta': {'today_change': -1.61, 'trend_status': 'weak_down', 'volume_ratio': 1.0}}
```
volume_ratio=1.0 是"列不存在"分支的默认值，证实 F1 仍在生效。

### dividend_factor 实测（P1 验证）
```
dy=0.00: score=0.0
dy=0.02: score=4.0
dy=0.05: score=8.0
dy=0.08: score=10.0
dy=0.10: score=10.0
dy=0.105: score=6   ← 不单调！
dy=0.15: score=6
dy=0.20: score=6
dy=0.30: score=6
```
**P1-1（高股息扣分）仍然存在**。

### fiveday_factor 实测
模拟打分（`ret5 < -5%` 永远得 2，`ret5 > 10%` 永远得 10）：
- -50%、-20%、-10% 都得 2
- +50%、+10.01% 都得 10
- 范围 [2, 10]，无 0/1 极端分
- **P1-2（fiveday 区间不平衡）仍然存在**。

### 其他发现

- **P2-7（hy_diff_factor.py.bak 残留）已修复** — `.bak` 文件已删除。
- **P3-1（test/import time.ini 命名异常）未修复** — 仍存在。
- **main.py:48 `s_score += sum_score`** 累计出总分母（满分 100），但 line 52 只 print `total_s`，`s_score` 从未输出。属于死计算。
- **路径迁移小问题**：main.py 用相对路径 `./result/daily_score/...`，而 daily_report.py / stock_analysis.py 用绝对路径 `/home/admin/AUTO-STOCK/result/daily_score`。相对路径假定 cwd 是项目根，cron 调用时容易因 `cd` 位置而失败（建议统一绝对路径）。

## 修复状态总览

| ID    | 等级 | 描述                                | 状态          |
|-------|------|-------------------------------------|---------------|
| F1    | P0   | daily_change 找 `成交量` 而非 `成交额` | **未修复**    |
| F2    | P0   | aggregate_scores / discover_and_run 死代码 | **未修复** |
| F3    | P0   | dp_diff_factor 命名误导              | **未修复**    |
| P1-1  | P1   | dividend 高股息扣分（>10% → 6）      | **未修复**    |
| P1-2  | P1   | fiveday 区间 [2,10] 不平衡          | **未修复**    |
| P1-3  | P1   | dp_diff `index_ret` 全局缓存跨日    | **未修复**    |
| P1-4  | P1   | financial "权重" vs "满分" 术语     | **未修复**    |
| P1-5  | P1   | financial final 截断偏紧            | **未修复**    |
| P2-1  | P2   | 因子类命名风格不统一（`attentionFactor`/`dividendfactor`）| **未修复** |
| P2-2  | P2   | main.load_factors 缺 try/except    | **未修复**    |
| P2-3  | P2   | hy_diff_factor.py.bak 残留          | **已修复**（已删） |
| P2-4  | P2   | 各因子 init() 风格不统一            | **未修复**    |
| P2-5  | P2   | attention_factor 每只股票拉大盘 K 线 | **未修复**    |
| P2-6  | P2   | 数据缺失无 meta.error               | **未修复**    |
| P2-7  | P2   | daily_change try/except 太宽        | **未修复**    |
| P3-1  | P3   | test/import time.ini 命名异常       | **未修复**    |
| P3-2  | P3   | fiveday 未使用成交量信息            | **未修复**    |

**唯一修复** = P2-3（hy_diff_factor.py.bak 删除）。
**新增发现** = main.py 路径相对 vs 绝对不一致，s_score 死计算。

## Top-3 本轮新发现

1. **P0 三大坑（F1/F2/F3）全部未修复**，任意一条都会让评分系统偏离设计意图。
2. **main.py:48 `s_score += sum_score` 是死计算**：累加 9 个因子的 `sum_score`（即 10 或 20），但 line 52 的 print 只输出 `total_s`，没输出 `s_score`；且没有写入 CSV 列。该变量是"假分母"。
3. **main.py 用相对路径 `./result/daily_score/`** 而 daily_report.py / stock_analysis.py 用绝对路径。evening_pipeline.sh 中 `cd` 到 `AUTO-STOCK` 才执行所以现在能跑，但属于脆弱耦合。
