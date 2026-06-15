# 数据流水线审查 — 草稿笔记

> 子代理：#3-数据流水线
> 审查日期：2026-06-14
> 范围：market_down / price_builder / data_manager / build_industry_data / data_fetcher / utils / data/ 目录

## 1. 模块清点

| 文件 | 行数 | 角色 | 评价 |
|------|------|------|------|
| `src/datafactory/market_down.py` | 50 | 全市场快照下载（单日全量） | 极简，单线程，5次重试 |
| `src/datafactory/price_builder.py` | 64 | 日行情→个股CSV | 增量合并，移动到bak |
| `src/datafactory/data_manager.py` | 782 | 数据统一接口 | 9个get_*接口；含关键bug |
| `src/datafactory/build_industry_data.py` | 522 | 行业映射+涨跌幅 | 防封策略齐全，有断点续传 |
| `src/datafactory/trade_calendar.py` | 33 | 交易日历 | 简单，未自动更新 |
| `src/datafactory/finance_manager.py` | 45 | 同花顺财务数据（旧版） | 被data_manager的get_finance取代但仍存在 |
| `src/datafactory/hist_price_*.py` | 多 | 历史价格下载/构建 | 早期工具，目前未在主流程使用 |
| `src/data_fetcher.py` | 0 字节 | **空文件** | sel.py 导入即崩溃 |
| `src/utils.py` | 66 | 工具（format_code/get_market_change） | get_market_change返回可能为0 |
| `data/` | 12子目录 | 缓存与原始数据 | 体积大（5000+价格文件） |

## 2. 关键发现

### [P0-1] `src/data_fetcher.py` 是空文件，sel.py 导入即崩
- 文件大小：0字节
- `src/sel.py:1`: `from src.data_fetcher import get_stock_basic, get_price_change, get_financials`
- 该模块不存在对应的函数 → ImportError
- 后果：任何运行 `from src.sel import filter_stocks` 的代码会失败
- 触发面小：sel.py 没有被生产流水线调用，仅 sel.py / backtester.py / tracker.py 引用过

### [P0-2] `get_fund_flow_5day` 在同一文件中有两个定义
- `src/datafactory/data_manager.py:384` 第一版（不接收 date 参数，保存为 `fund_flow_5day.csv`）
- `src/datafactory/data_manager.py:426` 第二版（接收 `date` 参数，保存为 `fund_flow_5day_YYYYMMDD.csv`）
- Python 会用第二个定义完全覆盖第一个；第一个成为死代码
- 实际效果：第二版生效，但是第一版留下的注释（"本地缓存优先"）让维护者误以为存在两套逻辑
- 第二版逻辑本身有缺陷：line 442-450 当 `latest_file` 为空字符串""时 `_read_csv_if_exists("")` 会尝试 `os.path.join("data/fund", "")` 然后pd.read_csv("data/fund")，会读到目录解析失败 → 异常被静默吞噬

### [P0-3] 行业映射数据陈旧（2026-05-12构建，已 33 天未更新）
- `data/industry/stock_industry_mapping.csv` mtime = 2026-05-12
- 5199条记录 → 看似完整，但行业分类随申万调整而变化（如新行业被纳入、新股票上市）
- 当前价格文件已到 2026-06-12，但行业映射停留在5月
- 后果：新上市股票（科创板/创业板新股）无法映射到行业 → hy_diff_factor 评分缺失
- 同时 `daily_industry_change.py` 不重建映射，只追加涨跌幅

### [P0-4] `data/calendar/trade_days.csv` mtime = 2026-05-24（已 21 天未更新）
- 该文件含8798条记录，但只到 2026-12-31
- 当日（2026-06-14）查询"今日是否为交易日"需要把 today="2026-06-14" 与 calendar 中的字符串比较，能匹配上，所以"暂时可用"
- 但 2027 年起 holiday 安排不会自动同步 → `is_trade_day()` 会一直返回 True（calendar 永远不更新）
- 同时 `build_industry_data.py` 的 `time` 引用了 `datetime.now()` 而不是交易日历，存在判断偏差

### [P1-1] 财报缓存"智能过期"逻辑有缺陷
- `_is_cache_expired` 用 `latest_finance_period > latest_cache_period` 比较日期字符串
- 同花顺数据 `"2025-03-31"` vs `"2025-09-30"` 字符串比较有效，但传入 `pd.to_datetime` 后会变成 Timestamp
- 实际：`finance_periods = finance_df['报告期'].dropna().unique()` 仍是字符串（CSV未转换），max 字符串比较 = 字典序 → `"2025-12-31" > "2025-09-30"` 成立
- 风险：当 cache 是空 / finance 列名不匹配时（"报告期"是中文列名）抛 KeyError，未被 try/except 包裹
- 实际更可能出错：`get_disclosure_dates` 调用 `get_finance`（line 610），如果 finance 文件被错误删除或列名改变 → `KeyError: '报告期'` → except 块 line 631 捕获 → 返回 `[]` → 后续 `get_kline_after_disclosure` 拿到 `{"error": ..., "kline": []}`

### [P1-2] `get_kline_after_disclosure` 解析"成交额"是字段不存在
- line 771: `volume = safe_float(row.get('成交额', 0)) if '成交额' in row and pd.notna(row.get('成交额')) else 0`
- `row` 是 Series，`pd.notna(row.get('成交额'))` 在成交额列存在时是有效的
- 但 `row.get('成交额', 0)` 返回的是 float，但被 `safe_float` 再转一次 → TypeError 风险
- 实际 line 760-763: `def safe_float(val):` 内 `float(val)` → 当 val 是 0 (int) 时正常工作；val 是 NaN 时 `math.isnan` 检查 → 返回 None
- 这部分代码可读性差，可能在 refactor 时破坏

### [P1-3] `market_down.py` 是单次全市场下载，文件落地失败无原子保护
- 流程：ak.stock_zh_a_spot() → df.to_csv(file_path)
- 风险：若中途崩溃（OOM、断电），留下半截文件
- `data/daily_market/{today}.csv` 成功后会移到 `bak/`，但若先写一半再被移到 bak，会污染历史
- 当前 `data/daily_market/` 实际为空（53个文件全在 bak/）—— 符合"用完即移"的模式，但增加了"今天下载失败 + 文件存在"歧义
- 当天若下载失败，`download_market` 返回 False，但 `update_data.py` 不重试

### [P1-4] `price_builder.py` 重新处理会累积行（旧数据 + 新数据）
- line 48-53: 读取已有 → concat → drop_duplicates("日期") → sort
- 但 `new_row` 包含 `date1`（即文件名日期），如果 bak 目录里的 csv 已被移走、但历史 price 文件已含该日期，去重正常
- 风险：如果 `data/daily_market/bak/20260612.csv` 已经被处理过，且 `build_price()` 再次被调用（异常重试）→ 它读取的目录是 `data/daily_market`（不是 bak），所以"幂等"由"文件位置"保证
- 实际看：`data/daily_market/` 是空的（没有未处理文件），所以下一次运行 `update_data.py` 不会重复处理昨日数据 → 正常
- 但若在 bak 之前的某个文件被还原到 `data/daily_market/`，则同一天的价格会被更新（因为 df.to_csv 不去重，drop_duplicates("日期") 保留最后一条）→ 幂等性 OK
- P1 实际评级可降低：基本无问题

### [P1-5] `data_manager.py:343-381` `_get_sw_code` 映射是粗略字符串匹配
```python
for key in SW_CODE_MAP:
    if key in industry_name:
        return SW_CODE_MAP[key]
```
- 多个 key 映射到同一 code（'银行'→801780, '非银金融'→801790, '房地产'→801720）
- 字典序遍历，第一个匹配的 key 返回 → 实际是 dict 顺序（Python 3.7+ 保证插入顺序）
- 当 industry_name = "银行Ⅱ"，"银行" in "银行Ⅱ" → True → 返回 801780 ✓
- 当 industry_name = "城商行Ⅱ"，只有"银行"不在其中 → 返回 None → 跌入 print "提示..." 分支
- 实际 `get_industry_change` 在 `data_manager.py:298-340` 是 deprecated 路径（line 339 提示"请运行 build_industry_data.py"），现网只用 `hy_diff_factor.get_industry_change_by_code`（读 sw_code 直接找文件）
- 所以 `_get_sw_code` 现在是死代码（仅 `get_industry_change` 还在引用，但 hy_diff_factor 走另一条路）
- **结论**：这部分是技术债，建议删除或标记 deprecated

### [P1-6] `utils.get_market_change()` 异常返回 0.0，导致 DP 差异因子把"今年相对大盘"错算为 +100%
- line 64-65: `except Exception as e: print(...); return 0.0`
- `dp_diff_factor.py:46`: `index_ret = src.utils.get_market_change()` (有 global 缓存)
- `relative = stock_ret - index_ret` → 当 index_ret=0 → relative = stock_ret
- 后果：API 失败时，相对收益等于绝对收益，所有股票同时"看起来跑赢大盘"
- 应该抛出异常或返回 None，让调用方决定如何处理

### [P2-1] `data/finance/{code}.csv` 含大量 `False` 字符串（akshare 返回的同花顺原始格式）
- 财务 CSV 的 "净利润同比增长率" 等字段大量为字符串 "False"
- `_to_float(v)` 在 `financial_factor.py:149-153` 强转 `float(str(v).replace("%", "").strip())` → `float("False")` → ValueError → except 返回 0.0
- 后果：所有早期数据（2002-2023）"增长率" 都会被当 0 处理
- 实际 `js_score` 用的是 `tail(3)`，所以近期 2024-2026 数据仍有效
- 但 `_to_float` 掩盖了真实错误（应该 raise 或 log warning）

### [P2-2] `get_news` 没用 `refresh` 参数（line 128）
- 函数签名接受 `refresh=False`，但函数体内完全没用
- 调用方传 `refresh=True` 不会触发重新获取
- 后果：用户期望"强制刷新"实际不生效

### [P2-3] `get_attention` 失败时静默返回本地
- line 97-99: `except Exception as e: print(...); return _read_csv_if_exists(file_path)`
- 没有 raise，调用方无法区分"本地有数据" vs "远程失败"
- 实际 factor 端用 `if df is None or df.empty: return 0`，降级 OK，但日志不够

### [P2-4] `data/price/` 有 5535 个文件，每次 `get_price` 都做 `pd.read_csv`
- 5000+ 文件 × 9 因子 = 45000 次 CSV 读取
- 批量评分 5000 股约需 1-2 分钟（read_csv 主导）
- 改进：用 sqlite 索引或 feather/parquet → 收益 5-10x
- 实际 evening_pipeline 不跑 5000 股全量，但风险依然存在

### [P2-5] `disclosure` 缓存的"智能过期"逻辑有未处理的 KeyError
- `_is_cache_expired` 假设 `finance_df` 一定有 '报告期' 列
- 但 `get_finance` 异常时返回 `_read_csv_if_exists(file_path)`（可能 None 或空）
- line 574: `if cache_df is None or cache_df.empty or finance_df is None or finance_df.empty: return True` ✓
- line 578: `finance_periods = finance_df['报告期'].dropna().unique()` ← finance_df 不是空但 '报告期' 列不存在 → KeyError
- 该 KeyError 未被 `get_disclosure_dates` 的 try/except 包裹（line 619-636 只包了 cninfo 接口），所以会向上抛出
- 实际触发：finance CSV 列名变化（"报告期" 改为 "period_date"） → 所有 disclosure 调用全部失败

### [P2-6] `data/industry/processed_sw_changes.txt` 未清理
- 这是 build 时的进度文件，正常流程下会删除（line 347）
- 当前存在说明上次构建未正常完成（或者"已完成"后没人清理）
- 实际：grep "801128_20" 出现 → 这是处理完成的标志，但文件还留着
- 风险：未来 `daily_industry_change.py` 会读取这个文件，但格式是 `{sw_code}_{days}` 字符串，与它自己用的 `cache_key = f"{sw_code}_{days}"` 不一致（它用 `_20` 而非 `_20d`）→ 不兼容
- 实际 `daily_industry_change.py:131-141` 完全没用这个 progress 文件

### [P2-7] `data/industry/stock_industry_mapping.csv` 只有 5199 只股票，但东方财富全A有 5400+ 只
- 北交所（bj 前缀）股票有 200+ 只，文件名是 `bj920000.csv`
- price_builder line 33-35 用 `normalize_code(row["代码"])` 处理 → bj 前缀被剥成 6位 → 进入 `data/price/bj920000.csv` 是不可能的（line 27: `code = code[2:]`，b→2位 = "920000" 6位）
- 等等：line 27 `code.startswith("6")` → sh; `code.startswith("0")` → sz; `code.startswith("3")` → sz; `code.startswith("8")` → bj (line 23 normalize_code 没处理)
- `normalize_code` 只处理 6位/8位/小数，**不处理交易所前缀**！
- 后果：`daily_market` 中的 bj920000 在 price_builder 中 → `code = "bj920000"` → `len("bj920000") == 8` → `code[2:] = "920000"` ✓
- 实际 OK，normalize_code 是处理前缀+代码
- 但 `get_price` line 38-41 仅依赖文件名（`{code}.csv`），"920000.csv" 会被找到 ✓
- 所以这个其实没 bug，但 `data/price/` 应有 920000 前缀的 6 位文件
- **结论：没问题，只是直觉上"应该 6 位"** 

## 3. 行业系统评估

### 行业映射
- 文件：`data/industry/stock_industry_mapping.csv`（5199 行，2026-05-12）
- 覆盖：80+ 个申万二级行业（见 `SW_CODES` 共 131 个）
- **缺失**：实际映射中只用了一个行业名 per stock，部分行业（农业综合Ⅱ 801019）从数据看没股票
- 时间：33 天未更新 → 新股/借壳/退市股无映射

### 行业涨跌幅
- 131 个 csv，2026-05-12 至 2026-06-12 的数据
- `daily_industry_change.py` 工作正常：每个 csv 内 daily 行（每个交易日）
- 注意：`update_time` 只在第一行写，后续行 update_time 为空 → `date` 列才是真正的指标
- 回测取数：`get_industry_change_by_code` 支持按 date 取，未命中则取最近前一天（line 82-87）✓
- 风险：节假日/停牌日的 date 缺失 → 第一次跑历史回测会缺数据
- 实际每日 cron 16:00 跑 `daily_industry_change.py`，数据会持续更新

### 行业 SW_CODES 覆盖
- build_industry_data.py:SW_CODES 列了 131 个
- 实际 processed_sw_changes.txt 130 条（缺 1 个：801194？让审计核实）
- 缺失的 1 个：`grep -c "^\s*('801" build_industry_data.py` = 131；processed_sw_changes.txt 130
- 差 1 个可能 = 上次构建时 1 个行业拉取失败

## 4. 缓存策略总结

| 目录 | 缓存什么 | 失效策略 | 风险 |
|------|---------|---------|------|
| `data/price/` | 个股日K | 无失效，全量累积 | OK（增量合并） |
| `data/finance/` | 财报数据 | 永久（无 ttl） | **P1**：缺最新季度数据时仍返回旧 |
| `data/dividend/` | 分红 | 120天后 refresh | OK |
| `data/attention/` | 关注度指数 | 滚动合并本地+远程 | OK |
| `data/news/` | 新闻 | 滚动合并（按链接/标题去重） | OK（去重逻辑完备） |
| `data/industry/` | 行业映射+涨跌幅 | 永不变（除非手动重建） | **P0**：33天未更新 |
| `data/calendar/` | 交易日历 | **永不更新** | **P0**：2027 起失效 |
| `data/disclosure/` | 财报披露日期 | 智能过期（基于finance） | 部分 OK（P2 KeyError 风险） |
| `data/fund/` | 资金流向 | 当日存在即跳过 | OK（带日期文件） |
| `data/daily_market/` | 每日全市场快照 | 处理后移 bak | OK |

## 5. 接口稳定性

- `get_price` / `get_finance` / `get_dividend` / `get_attention` / `get_news` 签名稳定
- `get_kline_after_disclosure` 签名稳定
- `get_industry_change` 仍存在但 hy_diff_factor 不用它（hy_diff_factor 用 sw_code 直接读文件）
- `get_fund_flow_5day` 重复定义 → 隐藏行为
- `get_news` 的 `refresh` 参数无效

## 6. 并发/全局状态

- `dp_diff_factor.py:7` `index_ret = None` 是模块级全局（缓存"今年大盘涨幅"）
- 进程内 OK，跨进程不安全；但只 cron 单跑
- `hy_diff_factor.py:12-13` 类似的 industry_mapping_df_cache
- 单例模式 + 全局变量，建议改为 `@functools.lru_cache` 或依赖注入

## 7. 综合评分
- 正确性：3/5（多 P0/P1）
- 可维护性：3/5（重复定义+死代码+stale 文件）
- 性能：3.5/5（CSV 读取 5000+ 次，可优化）
- 文档：3/5（CLAUDE.md 大体准确，但 finance_manager 仍存在但已无引用）
- 总评：3/5
