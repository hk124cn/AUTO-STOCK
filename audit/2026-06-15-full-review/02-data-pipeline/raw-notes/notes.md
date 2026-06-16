# 子报告 #2：数据流水线 — 草稿

## 上次 P0 修复状态

| ID | 上次描述 | 修复状态 | 证据 |
|----|----------|----------|------|
| F4 | `data_fetcher.py` 0 字节 + `sel.py` 死 import | **半修复** | 文件已删（git status D），但 `src/backtester.py:1` 和 `src/tracker.py:1` 仍有 `from data_fetcher import get_daily_prices` ——这两个文件本身是 100% 死代码（无任何 caller）|
| F5 | 行业映射 33 天未更新 | **未修复** | `stock_industry_mapping.csv` mtime = 2026-05-12 14:54（与上次审查完全一致），仍然 34 天未变。CRON.md 也没有"重建行业映射"的 cron 任务 |
| F6 | `get_market_change()` 异常返 0.0 | **未修复** | `src/utils.py:64-66` 仍是 `except Exception as e: ... return 0.0`；git diff 为空 |
| F7 | `get_fund_flow_5day` 重复定义 | **未修复** | `data_manager.py:384` 与 `:426` 仍有两个同名定义，git diff 为空 |
| F8 | `trade_days.csv` mtime 不动 | **已修复** | mtime = 2026-06-15 11:31:12；行数 8798 行；仍只到 2026-12-31（2027+ 仍需自动续期） |

## 上次 P1/P2 修复状态

| ID | 描述 | 状态 |
|----|------|------|
| P1-1 | `_is_cache_expired` 列名变化无防护 | 未修复（代码未改动）|
| P1-2 | `processed_sw_changes.txt` 与 daily 不兼容 | **已清理**（文件已不存在）|
| P1-3 | `market_down.py` 单次下载无 jitter | 未修复（代码未改动）|
| P1-4 | `get_news` `refresh` 参数被忽略 | 未修复 |
| P1-5 | `data/finance/` 含大量 "False" 字符串 | 未修复 |
| P1-6 | 行业映射 5199 行 vs 全 A 5400 | 仍存在 |
| P2-1~7 | 性能优化、删除死代码等 | 均未修复 |

## 本轮新发现

### [P0-NEW] `src/backtester.py` 和 `src/tracker.py` 是 100% 死代码，import 已删除的 `data_fetcher`
- 位置：`/home/admin/AUTO-STOCK/src/backtester.py:1`、`/home/admin/AUTO-STOCK/src/tracker.py:1`
- 现象：两个文件第一行都是 `from data_fetcher import get_daily_prices`
- 严重性：这两个文件**完全没有 caller**（`grep -rn "from src.backtester\|from src.tracker\|src.backtester\|src.tracker" --include="*.py"` 无任何命中）
- 后果：
  1. 任何导入这两个文件的脚本立即 ImportError
  2. 当前主流程不引用，所以暂时没崩——但属于"代码里有炸弹"
  3. 与上次 P0-1 同根问题未根除
- 建议：直接删除 `src/backtester.py` 和 `src/tracker.py`

### [P0-NEW] `result/future_returns/{10d,20d}` 历史生成永远填不满
- 位置：`src/analyzer/future_return_generator.py:281-285`
- 现象：脚本每次扫描所有 batch_result，对每个日期 × 3 个 n_days 跑 `generate_future_returns`，但**前瞻检查** `if nd_date > today: return` 导致最近的几个评分日的 20d 永远是空
- 后果：20d 数据要等 20 天后才开始填，今天（2026-06-15）最近的 20d 数据只到 20260518.csv，5 天前的评分还没 20d 数据 → **信号系统 v2 想用 20d 数据判断收益时数据稀疏**
- 建议：增加 10d/20d 历史的"未来补齐"机制（数据足够时自动追写）

### [P1-NEW] `future_return_generator.py` 读 5535 个价格 CSV 用纯 Python `csv.DictReader`，无任何缓存
- 位置：`src/analyzer/future_return_generator.py:103-115`
- 现象：每个股票 × 每个评分日都重新 open + DictReader 解析一次文件
- 实测（看 2026-06-15 18:00:15 → 18:00:26）：单个 20d 文件 11 秒内处理 1380 条 → 但每个 batch × 3 个 n_days 都重读 = **大量重复 IO**
- 证据（log）：
  ```
  2026-06-15 18:00:15,611 - INFO - 20260518 评分股票 1384 只，其中 1384 只有价格数据
  2026-06-15 18:00:26,667 - INFO - ✅ 生成 future_20d_20260518.csv: 成功 1380, 失败 4
  ```
  11 秒处理 1380 只（约 12.5 行/秒/股），如果再多 1 个 batch 就接近分钟级
- 建议：缓存已读过的 price_df（dict），或直接走 `data_manager.get_price` 复用其逻辑

### [P1-NEW] `future_return_generator.py` 不在 `evening_pipeline.sh` 中
- 位置：`scripts/evening_pipeline.sh`（3 个步骤：评分 → kline → 报告）
- 现象：未来收益由独立 `scripts/daily_future_return.sh`（cron 18:00）跑，**不在晚间流水线里**
- 后果：万一 cron 失败或机器重启，晚间流水线不会触发 future_returns 生成
- 建议：把 `python src/analyzer/future_return_generator.py` 加到 evening_pipeline.sh 步骤 3.5

### [P1-NEW] `dp_diff_factor` 全局缓存 `index_ret` 永远不变
- 位置：`src/factors/dp_diff_factor.py:7,42-46`
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
  1. 进程内首次调用后永远缓存到进程退出
  2. 即便 akshare 暂时返回错误值（如网络抖动），后续所有评分都用错的值
  3. 与 `F6` 联动：单次异常 → 0.0 → 全市场分数虚高 → 后续无法纠正
- 建议：增加日期戳检查（`if index_date != today: reindex`），或用 `functools.lru_cache` + `datetime.now().date()` 作为 key

### [P2-NEW] `ANALYZER_PLAN.md` 第三阶段（评分有效性验证）说"待做"但已 53 天未启动
- 位置：`src/analyzer/ANALYZER_PLAN.md:208-211`
- 现象：
  ```
  | 3.1 score_validator.py 脚本 | 待做 | 🔴 高 | 验证评分有效性 |
  | 3.2 生成验证报告 | 待做 | 🟡 中 | 表格+可视化 |
  | 3.3 各因子有效性分析 | 待做 | 🟢 低 | 后续研究 |
  ```
- 后果：未来收益标签已经在生成 1 个月（5533 条 5d 数据），但**没人用这些数据验证评分有效性**——典型"数据生成但未消费"
- 建议：要么删 ANALYZER_PLAN.md 第四第五阶段（信号系统已实现在别处），要么在第三阶段分配任务

### [P2-NEW] `ANALYZER_PLAN.md` 提到目录 `meta/` 但实际不存在
- 位置：`src/analyzer/ANALYZER_PLAN.md:81-83`、`src/analyzer/ANALYZER_PLAN.md:233`
- 现象：文档列出 `meta/factor_config_v1.json`、`meta/pool_config_v1.json`、`meta/snapshot_manifest.csv`，但 `ls /home/admin/AUTO-STOCK/meta/` 不存在
- 后果：文档与现实不一致，新人按文档走会找不到文件
- 建议：要么真创建 meta/，要么从文档删除

### [P2-NEW] `future_return_generator.py` 路径硬编码
- 位置：`src/analyzer/future_return_generator.py:22`
- 现象：`AUTO_STOCK_ROOT = "/home/admin/AUTO-STOCK"` ——硬编码绝对路径
- 后果：项目搬迁（clone 到别的机器）即崩
- 建议：改为 `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`

### [P2-NEW] `data/industry/` 缺 801010 行业 CSV
- 位置：`/home/admin/AUTO-STOCK/data/industry/change_801010_20d.csv`
- 现象：上次审查发现 SW_CODES 共 131 条，本地只有 130 个 CSV ——少了 `801010`（农林牧渔）
- 验证：`ls data/industry/ | grep change_ | head -3` → 801011 起跳，没有 801010
- 后果：所有农林牧渔板块个股的 20d 行业涨跌幅为 None → hy_diff_factor 拿不到对比 → 评分误差
- 建议：用 `python -m src.datafactory.build_industry_data --changes` 重新跑全量

### [P3-NEW] `data/calendar/trade_days.csv` 仅覆盖至 2026-12-31
- 位置：`/home/admin/AUTO-STOCK/data/calendar/trade_days.csv`
- 现象：tail 显示 2026-12-31，2027+ 未覆盖
- 后果：上次 F8 的根因"长期不更新"只解决了一半（重建了，但没续期）
- 建议：`init_trade_calendar` 增加"是否覆盖未来 6 个月"判断，自动 append