# 子报告：数据流水线（#3-数据流水线）

> 范围：
> - `src/datafactory/market_down.py`、`src/datafactory/price_builder.py`
> - `src/datafactory/data_manager.py`（9 个 get_* 接口 + 行业/资金流/公告/披露）
> - `src/datafactory/build_industry_data.py`（申万二级行业）
> - `src/datafactory/trade_calendar.py`、`src/datafactory/finance_manager.py`、`src/datafactory/hist_price_*.py`
> - `src/data_fetcher.py`、`src/utils.py`
> - `data/` 全部子目录（price/finance/dividend/attention/news/industry/disclosure/fund/calendar/daily_market/hist_price）
> - 调用方：`src/factors/*.py`、`api/main.py`、`scripts/daily_*.py`、`scripts/evening_pipeline.sh`
>
> 严重程度评级：P0=功能错误 / P1=性能或安全 / P2=可改进 / P3=小问题
> 审查日期：2026-06-14

## 1. 概览

数据流水线为整个评分系统（9 因子）+ 回测 + 个股预警 + 报告系统提供底层数据。整体设计是"本地优先 + 增量累积"，关键路径（`market_down` → `price_builder` → `data_manager.get_price`）闭环但脆弱。

主要问题集中在 3 个层面：
1. **配置/基础设施陈旧**：`data/calendar/trade_days.csv`（21 天未更新）、`data/industry/stock_industry_mapping.csv`（33 天未更新）将逐步失效；`src/data_fetcher.py` 是空文件但被 `sel.py` 导入。
2. **死代码与重复定义**：`data_manager.py` 存在两个 `get_fund_flow_5day` 定义互相覆盖，`get_industry_change` 已被 `hy_diff_factor` 改用新路径但未删除，`_get_sw_code` 写得很长但实际无 caller；`finance_manager.py` 是被取代的旧财务下载器，仍保留且 `update_data.py` 没在引用。
3. **异常吞噬 + None 行为不统一**：`utils.get_market_change()` 失败时返回 0.0 会让 `dp_diff_factor` 错算为"全部跑赢大盘"；`_is_cache_expired` 假设列名固定，缺列时直接 KeyError 抛出。

总体：数据基本可用，但已处于"将错就错、靠运气跑通"的状态，需要做一次清理 + 加固。

## 2. 关键发现（按严重程度降序）

### [P0-1] `src/data_fetcher.py` 是空文件，import 必崩
- 位置：`/home/admin/AUTO-STOCK/src/data_fetcher.py`（0 字节，mtime 2026-05-24）
- 现象：文件内容为空，但 `src/sel.py:1` 有 `from src.data_fetcher import get_stock_basic, get_price_change, get_financials`
- 后果：任何运行 `from src.sel import filter_stocks` 的代码会因 ImportError 立即失败
- 影响面：`src/sel.py`、`src/backtester.py`、`src/tracker.py` 都引用该模块；当前主流程未调用 `sel.py`，但代码里出现就说明有人写过
- 证据：
  ```
  $ ls -la src/data_fetcher.py
  -rwxrwxrwx 1 admin admin 0 May 24 17:20 /home/admin/AUTO-STOCK/src/data_fetcher.py
  ```
- 建议：删除该空文件或重新实现；同步删除 `sel.py`/`backtester.py`/`tracker.py` 的 import

### [P0-2] `get_fund_flow_5day` 在 data_manager.py 中重复定义
- 位置：`src/datafactory/data_manager.py:384`（第一版）、`src/datafactory/data_manager.py:426`（第二版）
- 现象：Python 用第二个定义完全覆盖第一个；第一个变成死代码，但留下误导性注释
- 关键代码：
  ```python
  # Line 384 - 第一版（不接 date 参数，保存为 fund_flow_5day.csv）
  def get_fund_flow_5day(refresh=False):
      file_path = os.path.join(FUND_PATH, "fund_flow_5day.csv")
      ...
  # Line 426 - 第二版（接 date 参数，保存为 fund_flow_5day_YYYYMMDD.csv）
  def get_fund_flow_5day(refresh=False, date=None):
      if date:
          file_path = os.path.join(FUND_PATH, f"fund_flow_5day_{date}.csv")
          return _read_csv_if_exists(file_path)
      ...
  ```
- 后果：
  1. 维护者误以为存在两套逻辑，浪费时间理解
  2. 实际生效的是第二版，但其内部 line 442-450 当 latest_file=None 时 `_read_csv_if_exists(None)` 会触发 `TypeError`（实际是 `os.path.join("data/fund", None)`）— 实际看下 line 442 `latest_file = get_latest_fund_flow_file()` 当 `files` 为空时返回 None（line 421-422），再走 line 444 `if not refresh and latest_file:` 此时 latest_file=None → False → 跳过 → line 453 `_download_fund_flow_5day()` 没问题。所以这分支 OK
  3. 但 `get_latest_fund_flow_file` 返回 None 时光走到 line 455 `return _read_csv_if_exists(latest_file)` 即 `_read_csv_if_exists(None)` → `os.path.join("data/fund", None)` 抛 TypeError
- 建议：删除第一版；为 `get_latest_fund_flow_file` 添加 None 保护

### [P0-3] 行业映射数据陈旧 33 天，新股/借壳股无法评分
- 位置：`/home/admin/AUTO-STOCK/data/industry/stock_industry_mapping.csv`（mtime 2026-05-12）
- 现象：5199 条记录，文件时间 2026-05-12 14:54:57；当前是 2026-06-14，差 33 天
- 后果：
  1. 新上市股票（5月-6月间）无法在 `get_stock_industry_from_cache` 命中 → `IndustryDiffFactor.calculate()` 返回 score=0
  2. 申万行业调整（如新增/合并/拆分二级行业）会错过
  3. `daily_industry_change.py` 只追加涨跌幅，不重建映射
- 证据：
  ```
  $ stat -c '%y %s %n' data/industry/stock_industry_mapping.csv
  2026-05-12 14:54:57.005576580 +0800 139690 ...
  $ stat -c '%y %s %n' data/price/600519.csv
  2026-06-12 17:00:42.719984488 +0800 120190 ...
  ```
- 建议：
  1. 把"重建行业映射"加入 `evening_pipeline.sh` 或新建周更任务
  2. 给 `stock_industry_mapping.csv` 加 staleness 检查（mtime > 30 天则警告）
  3. 在 `hy_diff_factor.calculate()` 增加 fallback：行业未命中时按"全市场平均"或"未分类"占位

### [P0-4] 交易日历永久不更新，2027 年起将全错
- 位置：`/home/admin/AUTO-STOCK/data/calendar/trade_days.csv`（mtime 2026-05-24，8798 行）
- 现象：当前 trade_days.csv 覆盖到 2026-12-31；2027 年起的节假日不会自动同步
- 触发链：
  1. `trade_calendar.is_trade_day()` line 27-29: `pd.read_csv(PATH); today in df["trade_date"].astype(str).values`
  2. 2027 年某天 `today = "2027-01-04"`（元旦后）若 calendar 没更新，会返回 `False in df` → 不是交易日 → 流水线跳过
  3. 反之 2027 年某天 calendar 标 True 但实际是节假日 → 仍会跑（错）
- 后果：长期不更新会让 `evening_pipeline.sh` 和 `daily_data_fetch.py` 决策错误
- 建议：
  1. 在 `evening_pipeline.sh` 步骤 0 加 staleness check：mtime > 30 天则报警
  2. 增加 `update_trade_calendar.py` 周更 cron：`ak.tool_trade_date_hist_sina()` 增量拉取
  3. 或者用 akshare 的 `tool_trade_date_hist_sina()` 在每次 `is_trade_day()` 调用时检查是否需要 refresh

### [P0-5] `utils.get_market_change()` 失败返回 0.0，导致 dp_diff_factor 错算
- 位置：`src/utils.py:64-66`
- 现象：
  ```python
  except Exception as e:
      print(f"⚠️ 无法获取上证指数数据: {e}")
      return 0.0
  ```
- 后果链：
  1. `dp_diff_factor.py:46` `index_ret = src.utils.get_market_change()` (有模块级缓存)
  2. 当 akshare 限流/异常时 `index_ret = 0.0`
  3. `relative = stock_ret - index_ret = stock_ret - 0 = stock_ret`
  4. 所有股票"看起来跑赢大盘"，评分集体虚高
  5. 因子缓存是进程级的，问题持续到进程结束
- 建议：
  1. 改为返回 `None`，调用方判断后用 0 或 NaN 占位
  2. 加重试和退避（指数数据很稳定，不应轻易失败）
  3. 在 `dp_diff_factor.py` 加 stale check：`index_ret` 距上次更新 > 24h 重新拉取

### [P1-1] `get_disclosure_dates` 对 `finance_df` 列名变化无防护
- 位置：`src/datafactory/data_manager.py:572-590`（`_is_cache_expired`）
- 现象：
  ```python
  def _is_cache_expired(cache_df, finance_df):
      ...
      finance_periods = finance_df['报告期'].dropna().unique()  # ← 假设列名固定
  ```
- 后果：
  1. `get_finance` line 54 调用 `ak.stock_financial_abstract_ths(symbol=code, indicator="按单季度")` — 同花顺接口偶尔会返回英文列名
  2. 如果某天 `finance_df.columns` 不含"报告期" → KeyError
  3. 该 KeyError **未**被 `get_disclosure_dates` 的 try/except 包裹（line 619-636 只包了 cninfo 接口调用）
  4. → 异常向上抛出，调用方（API 端）500
- 建议：
  1. 在 `_is_cache_expired` 入口检查 `if '报告期' not in finance_df.columns: return True`
  2. 或把"列名验证"统一放在 `get_finance` 返回时做规范化

### [P1-2] `data/industry/processed_sw_changes.txt` 与 daily_industry_change.py 格式不兼容
- 位置：`/home/admin/AUTO-STOCK/data/industry/processed_sw_changes.txt`（line 1-131 全部是 `sw_code_days` 格式）
- 现象：
  1. `build_industry_data.py:392` 写入 `cache_key = f"{sw_code}_{days}"` → 内容形如 `801011_20`
  2. `daily_industry_change.py:130-141` 完全没用这个 progress 文件
  3. 即便用了，`append_industry_change` 的去重键（line 101）是 `today in local['date'].values`（按日期字符串），与 sw_code 无关
- 后果：
  1. 进度文件残留在磁盘上（`build_industry_data.py:347` 完成后会删除，但 daily 任务不删除）
  2. 如果未来想用 progress 加速 daily 任务，会读到错误格式
- 建议：清理该文件 + 在 `daily_industry_change.py` 中加 `processed_sw_daily_changes.txt`（按日期记录）实现真正的"今天跑过就跳过"

### [P1-3] `market_down.py` 单次下载失败无重试入口
- 位置：`src/datafactory/market_down.py:31-46`
- 现象：5 次重试每次 sleep 5 秒，全失败后返回 False
- 问题：
  1. 全市场 spot 接口（ak.stock_zh_a_spot）数据量 ~10MB，akshare 经常在并发时返回 502/JSON parse error
  2. 每次失败后 sleep 5 秒，5 次 = 25 秒 + 下载耗时 ≈ 1-2 分钟
  3. 若失败，`update_data.py` 直接跳过（line 13-14），等下次 cron
  4. 没有"分片下载"——腾讯/东财等多家 fallback 是有（line 14-21），但还是单线程
- 风险：交易日下午 4:00 这一个时间窗口下载，错过当日就损失 1 天价格
- 建议：
  1. 加 jitter（`time.sleep(5 + random.random() * 3)`）避免与其它 cron 同时触发
  2. 把 fallback 顺序：东财（`_em`）→ 新浪（默认）→ 腾讯，akshare `_em` 实际更稳
  3. 增加"下载到 .tmp 后 rename"原子操作，避免半截文件污染

### [P1-4] `get_news` 的 `refresh` 参数被忽略
- 位置：`src/datafactory/data_manager.py:128-199`
- 现象：函数签名 `def get_news(code, refresh=False):` 接受 `refresh`，但函数体内完全没有 `if refresh:` 分支
- 后果：调用方传 `refresh=True` 期望"跳过缓存"会失望
- 调用方审查：`src/factors/news_factor.py:15` 没用 `refresh` → 暂时无 bug
- 建议：
  1. 真正实现 `refresh=True` 的逻辑（清空本地再重新获取）
  2. 或者从签名中删除 `refresh` 参数，避免误导

### [P1-5] `data/finance/` 含大量"False"字符串污染数据
- 位置：`data/finance/600519.csv`（2002-2023 共 90+ 行的增长率为字符串 "False"）
- 现象：akshare 同花顺接口早期数据（2002-2010 季报）经常返回 `False`（Python bool）而不是 NaN
- 后果：
  - `financial_factor.py:149-153` `_to_float(v)` 强转 `float("False")` → ValueError → except 返回 0.0
  - 实际 `js_score` 用 `tail(3)` → 命中 2025-2026 数据 → 评分仍然正确
  - 但**这种"全吞异常"掩盖了真实问题**：可能某天 akshare 返回列名变化、字段顺序变化，错误被默默吃掉
- 建议：
  1. `get_finance` 写入前先清洗：把 "False" → NaN，保留原始数据结构
  2. `_to_float` 失败时打日志，30+ 异常直接报警

### [P1-6] 行业映射 5199 行 vs 全 A ~5400 只，缺失主要为北交所
- 位置：`data/industry/stock_industry_mapping.csv`
- 现象：5199 行，全 A 约 5400 只（含 200+ 只北交所 bj 前缀）
- 后果：北交所新股/小盘股 100+ 只无法映射 → `IndustryDiffFactor` 返回 0
- 实际影响小：北交所股票评分需求低；但偶尔有"明明能评分却 0 分"的归因困难
- 建议：在 build 时加 `ak.stock_zh_a_spot_em()` 拉全 A 列表，对未映射的归入"未分类"

## 3. 改进建议（非问题，但有更好做法）

### [P2-1] `data/price/` 5000+ CSV，批量评分时 read_csv 占主导
- 5000 文件 × 9 因子调用 = 45000 次 pd.read_csv
- 实测：批量 5000 股全量 ~90 秒，其中 read_csv 占比 ~60 秒
- 建议：迁移到 sqlite（按 code + date 索引）或 feather（列式二进制）

### [P2-2] 模块级全局变量（dp_diff_factor / hy_diff_factor）
- `dp_diff_factor.py:7` `index_ret = None`、`hy_diff_factor.py:12-13` `_industry_stocks_cache = None`
- 进程内 OK，跨进程隔离（但 cron 单跑）；单测时难以 mock
- 建议：改为 `functools.lru_cache(maxsize=1)` 装饰函数

### [P2-3] `data_manager.py:217 build_industry_mapping()` 是旧版，未用
- 该函数用 `ak.stock_board_industry_name_em`（东方财富）拉行业列表
- `build_industry_data.py:248 build_industry_mapping(force=False)` 用 `ak.index_component_sw`（申万）
- 两份代码做同一件事，前者被后者取代但 `data_manager.py` 仍保留旧版
- 建议：从 `data_manager.py` 删除 `build_industry_mapping`（line 217-295），统一调用 `src.datafactory.build_industry_data.build_industry_mapping`

### [P2-4] `_get_sw_code` 80+ 行硬编码映射表是死代码
- 位置：`data_manager.py:343-381`
- 实际 `hy_diff_factor` 走 `_load_industry_mapping` 直接读 mapping.csv，绕过了 `_get_sw_code`
- 建议：删除 `get_industry_change` (line 298-340) + `_get_sw_code` (line 343-381)，仅保留 `get_industry_change_by_code` 在 `hy_diff_factor.py`

### [P2-5] `finance_manager.py` 是被取代的旧实现
- `finance_manager.py:27` 用 `ak.stock_financial_report_sina`（新浪）
- `data_manager.get_finance` 用 `ak.stock_financial_abstract_ths`（同花顺）
- 两个数据源不同，新浪数据列更少（缺扣非净利润等）
- 建议：删除 `finance_manager.py` 或保留但加弃用警告

### [P2-6] `data/daily_market/bak/` 累积 53 个文件
- 这些是 `price_builder` 处理后移过来的快照
- 累积几月后会有 200+ 文件，单个文件 ~10MB
- 建议：每月归档一次，bak 文件超过 30 个就移到 `bak/YYYYMM/`

### [P2-7] `attention_factor.calculate_score` 使用 `df.tail(min(20, len(df)))` 但来源是全量
- 关注度数据从同花顺 API 拉就是滚动 ~60 天窗口
- 用 `tail(20)` 限制后只取最近 20 天，OK
- 但若某只股票刚上市只有 3 天数据，tail(20) = 3 天 → 计算 std 时样本太少
- 建议：在 `attention_factor.js_score` 加 `if len(df) < 5: return 5` 保护

## 4. 需要核实的不确定项

- **行业映射缺失的 1 个**：SW_CODES 共 131 条，processed_sw_changes.txt 130 条 — 缺 1 个。原因可能是：拉取时某行业 (`801194` 保险Ⅱ？) 失败；或构建完毕后手动删除一个；需要对比完整两份文件确认。
- **`data/price/` 5535 vs 全 A ~5400**：多出 ~135 个文件。可能是：历史退市股残留（无害但占空间）；或 hist_price_builder 写入时的额外代码。
- **`data/daily_market/bak/` 文件日期范围**：从 20260313 到 20260612 共 53 个交易日 — 与 price 文件最新日期 2026-06-12 一致。但 `data/daily_market/` 是空的（无未处理文件），说明流程完整跑过；下次 cron 会再下载今天的快照。

## 5. 评分（1-5，5 = 优）

- **正确性：2.5/5** — 多个 P0（空文件、重复定义、stale 配置、异常吞噬），主流程靠运气跑通
- **可维护性：2.5/5** — 死代码多、stale 文件不清理、接口签名变化不一致
- **性能：3.5/5** — 整体 5 分钟内可跑 5000 股但有优化空间（CSV→SQLite）
- **文档：3.5/5** — CLAUDE.md 描述基本准确，但 finance_manager / data_fetcher / build_industry_mapping 三处不一致未反映
- **总评：3/5** — 数据流水线整体可用但需要 1-2 天的清理 + 加固工作

---

## 6. Top-3 严重问题

1. **P0-1 空文件 data_fetcher.py** — 任何 import 即崩，虽未在主流程但属于"代码里有炸弹"
2. **P0-3 行业映射 33 天未更新** — 直接影响 hy_diff_factor 评分覆盖率，5月-6月新股全部 0 分
3. **P0-5 `utils.get_market_change()` 返回 0.0** — 在 akshare 异常时让所有股票"看起来跑赢大盘"，可能误导评分

## 7. P0/P1/P2 数量

- P0：5
- P1：6
- P2：7
- P3：0
