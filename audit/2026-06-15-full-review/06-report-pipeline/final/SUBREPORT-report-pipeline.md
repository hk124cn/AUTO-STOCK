# 子报告：报告与流水线 (#6)

> 范围：
> - `scripts/daily_report.py`（1068 行）
> - `scripts/evening_pipeline.sh`（55 行，本次新增关注）
> - `scripts/daily_data_fetch.py`（111 行）
> - `scripts/calc_signals.py`（463 行）
> - `scripts/precompute_scores.py`（64 行）
> - `scripts/launch_analysis.py`（443 行）
> - `scripts/stock_analysis.py`（602 行，modified — 仅 RESULT_DIR 路径变更）
> - `scripts/run_v2_backtest.py`（320 行，新文件）
> - `scripts/daily_future_return.sh`（10 行，新文件）
> - `scripts/sim_trader.py`（12.9KB，未被流水线调用）
> - `scripts/daily_report_cron.sh`（18 行，旧 wrapper）
> - `reports/` 产物（html/md/individual + index.html + stale daily_report_latest.md）
>
> 严重程度评级：P0=功能错误/P1=性能或可维护性/P2=可改进/P3=小问题
> 审查日期：2026-06-15

## 1. 概览

报告与流水线在 2026-05-18 之后做了大刀阔斧的"瘦身"和路径迁移（`src/result/` → `result/daily_score/`），核心数据流可工作。但本轮审查发现 **`evening_pipeline.sh` 在最近的 `d5eae82` 提交中严重缩水**：从原 4 步（score → kline_analyzer → calc_signals → daily_report + sim_trader 旁路）**缩水为 3 步（score → kline_analyzer → daily_report）**，同时把上次审查标记为 P0 的"节假日跳过逻辑"（`grep -q "^${TARGET_DATE}"` 整段）和"sim_trader 失败吞错"问题一起"解决"——不是修，而是直接删了调用。这导致 `result/signals/` 和 `sim_trader` 不再被 cron 自动更新，stock.auto-claw.top/signals 页面会持续展示陈旧信号。

**好消息**：`calc_signals.py` 本轮补上了 SELL 信号生成（`generate_sell_signals()`，line 277-364），读 portfolio.db 检查 SIM 持仓的止盈/止损并生成 SELL 信号；上次审查的 P0-4 "无 SELL 信号"已修复。`.bak`/`.fix` 旧文件已清理，src/result 旧目录已迁出。

**坏消息**：上次审查的另外两个 P0（行业分析板块缺失、daily_report.py 内嵌 1300+ 只股票 JSON → 400KB HTML）**完全没动**。CLAUDE.md line 113 仍然写"行业分析"但 `daily_report.py` grep `industry|行业分析|industry_aggreg` 全部 0 命中。daily_report.py 的 `str(today_data)` 注入仍是 418KB HTML 文件的根因。

新文件方面：`run_v2_backtest.py` 实现 v2 策略的网格搜索（与 `run_launch_backtest.py` 平行），参数网格 `止盈 × 止损 × 冷却期 = 5×4×3 = 60 种`，按总评分 + 财报评分两轮排序。`daily_future_return.sh` 是新加的 cron 任务（`0 18 * * 1-5`），调 `future_return_generator.py` 算 N 日后收益率标签。这两个新文件不在 evening_pipeline 流程内，但都是 cron 驱动的。

## 2. 关键发现（按严重程度降序）

### [P0] evening_pipeline.sh 缩水：calc_signals 步骤被移除，signals 不再被 cron 更新
- 位置：`scripts/evening_pipeline.sh`（全文 55 行）
- 现象：当前流水线只有 3 步
  ```bash
  step 1 "批量多因子评分"      → main.py
  step 2 "生成评分-价格历史表"  → src/analyzer/kline_analyzer.py
  step 3 "生成每日报告"        → scripts/daily_report.py
  ```
  与 CLAUDE.md 第 120 行 "串联执行：批量评分 → kline_analyzer → 每日报告" 字面一致；但与"数据存储"段（CLAUDE.md line 141）声明的 `result/signals/v1/`、`result/signals/v2/` 信号产出脱节——**流水线没有调 `scripts/calc_signals.py`**
- 后果：
  - cron 0 19 * * 1-5 跑完后，`result/signals/v1/signals_YYYYMMDD.csv` 和 `signals_latest.csv` 不再更新
  - stock.auto-claw.top/signals 页面（CLAUDE.md line 86 "信号监控"）持续展示陈旧信号
  - v2 "首次突破"信号（CLAUDE.md line 87）也受影响
  - 这与 2026-06-15 实盘策略决策（10万本金、v1+总评分、止盈20%/止损8%/冷却3天）形成矛盾：决策基于信号系统，但流水线已经不再算信号
- 证据：
  - `evening_pipeline.sh` 行 30-47 全部内容（grep step / fail / calc_signals 均为 0 命中）
  - 上次审查报告原文（`audit/2026-06-14-full-review/05-report-system/final/SUBREPORT-report-pipeline.md` line 25）记录的流水线版本包含 step 3 calc_signals
- 建议：在 step 2 之后插入
  ```bash
  step 3 "计算每日信号"
  python3 scripts/calc_signals.py --date "$TARGET_DATE" --strategy-version v1 || fail "calc_signals"
  python3 scripts/calc_signals.py --date "$TARGET_DATE" --strategy-version v2 || fail "calc_signals v2"
  ```
  或在 fail 模式下至少跑 v1（默认策略）

### [P0] 流水线丢失交易日历检查，周末 cron 仍会跑然后失败
- 位置：`scripts/evening_pipeline.sh` 全文
- 现象：上次审查标记为 P0 的 `grep -q "^${TARGET_DATE}"` 整段逻辑被删除。当前流水线对 `data/daily_market/${TARGET_DATE}.csv` 是否存在没有前置检查
- 后果：
  - cron `0 19 * * 1-5` 在周五跑完后，周六周日本应不跑（已经限周一-五），但周一节假日（如端午）cron 仍会启动
  - 周五晚跑完后（如 2026-06-12 周五），周六 cron 不跑但周日也不跑——周一 6/15 是端午节后第一个交易日，正常
  - 真正的风险是周一恰好是节假日（如元旦、春节、清明、劳动节），`data/daily_market/${date}.csv` 不存在，main.py 会失败，`set -euo pipefail` 触发 fail
  - 上次审查建议改为 `DATE_HUMAN=$(date -d "${TARGET_DATE}" +%Y-%m-%d)` + grep `^${DATE_HUMAN}` 完全被无视
- 证据：与上次审查相同的根因（trade_days.csv 是 `2026-06-15` 而 TARGET_DATE 是 `20260615`），只是检查被整段删除
- 建议：在 step 1 之前插入
  ```bash
  DATE_HUMAN=$(date -d "${TARGET_DATE}" +%Y-%m-%d 2>/dev/null || echo "$TARGET_DATE")
  if ! grep -q "^${DATE_HUMAN}" data/calendar/trade_days.csv 2>/dev/null; then
      echo "ℹ️  ${DATE_HUMAN} 非交易日，跳过"
      exit 0
  fi
  ```

### [P0] 行业分析板块缺失（CLAUDE.md line 113 文档承诺，daily_report.py 0 实现）
- 位置：`scripts/daily_report.py` 全文
- 现象：
  - `grep -n "行业分析\|行业聚合\|industry_aggreg\|industry_ana\|hy_diff" scripts/daily_report.py` 全部 0 命中
  - 当前 8 个板块仍然是个股维度（大盘概览 / TOP 榜单 / 自选股专区 / 特别关注股票分析 / 今日 vs 昨日 / 5日评分走势 / 风险提示 / 投资建议）
  - 行业仅作为 `行业相对强弱` 单因子在 `FACTOR_LIST` 显示，没有聚合到行业维度
- 后果：
  - 用户无法从每日报告看到"今日哪些申万二级行业整体评分偏高/偏低"
  - 与 CLAUDE.md line 113 "特别关注股票高亮、收盘价+涨跌幅显示、行业分析" 不符
  - `data/industry/stock_industry_mapping.csv`（5199 只股票）和 `data/industry/change_xxx_20d.csv`（131 个行业）数据已经齐全，但报告未利用
- 建议：在板块二（TOP 榜单）之后新增板块"行业分析"：
  ```python
  # 按 stock_industry_mapping 聚合今日所有股票的总分
  industry_scores = {}
  for r in today_data:
      sw_code = industry_map.get(r['code'])
      if sw_code:
          industry_scores.setdefault(sw_code, []).append(float(r['total_score']))
  industry_avg = {sw: sum(s)/len(s) for sw, s in industry_scores.items() if len(s) >= 3}
  top5 = sorted(industry_avg.items(), key=lambda x: x[1], reverse=True)[:5]
  bottom5 = sorted(industry_avg.items(), key=lambda x: x[1])[:5]
  ```

### [P0] daily_report.py 内嵌 1300+ 只股票 JSON 到 HTML（418KB 单文件）
- 位置：`scripts/daily_report.py:956-957`
- 现象：
  ```python
  stock_data_js = str(today_data).replace("'score'", "'total_score'")
  h.append('<script>const stockData = ' + stock_data_js + ';')
  ```
  `today_data` 是 1300+ 只股票 × 9 因子字段的字典列表，`str()` 序列化为 JS 变量内嵌到 HTML
- 后果：
  - 实测 `reports/daily_report_20260615.html` **418022 字节**（上次 420539，几乎未改善）
  - `replace("'score'", "'total_score'")` 是 dead code：`batch_result_*.csv` 里没有 `score` 字段名，只有 `total_score`
  - 每次跑流水线覆盖 `reports/index.html`（也 418KB），nginx 直送浪费带宽
- 建议：把 `stockData` 改为按需从 `/api/...` 异步加载，或在 daily_report.py 中只保留搜索需要的 `code`, `name`, `total_score` 三列（数据量降到 ~30KB）

### [P1] evening_pipeline.sh 调 main.py 通过 stdin 注入（脆弱）
- 位置：`scripts/evening_pipeline.sh:32`
- 现象：
  ```bash
  printf "2\nstock_pool.csv\n\n" | python3 main.py || fail "批量评分"
  ```
  `main.py` 通过 `input()` 读模式 (2)、股票池文件名 (stock_pool.csv)、结果名 (空 → 默认 batch_result_${today}.csv)
- 后果：
  - 多/少一个换行都会让 `in_fname` 取到错的值
  - 如果 `main.py` 改成"读取非空值才退出"，流水线立刻挂
  - daily_report.py 假设 `batch_result_${today}.csv` 存在（依赖默认输出名），一旦 main.py 改动命名规则，daily_report 静默失败
- 建议：把 `main.py` 重构为 argparse 入口，流水线直接 `python3 main.py --batch stock_pool.csv --output result/daily_score/batch_result_${TARGET_DATE}.csv`

### [P1] daily_report.py 硬编码绝对路径 `/home/admin/AUTO-STOCK/...`
- 位置：
  - `scripts/daily_report.py:16, 31-33, 35-38, 41, 586, 599, 1054`
  - `scripts/daily_report.py` 的所有 `RESULT_DIR`, `SELF_STOCK_FILE`, `FOCUS_STOCK_FILE`, `PRICE_DIR`, `TRADE_DAYS_FILE` 都是 `/home/admin/AUTO-STOCK/...`
- 现象：对比 `scripts/calc_signals.py:21-22` 用 `Path(__file__).resolve().parent.parent` 计算根目录
- 后果：CI/Docker/别机部署直接失败；无法通过 symlink 切换项目根
- 建议：与 `calc_signals.py` 一致
  ```python
  ROOT_DIR = Path(__file__).resolve().parent.parent
  RESULT_DIR = ROOT_DIR / "result" / "daily_score"
  ```

### [P1] daily_report.py 大量重复代码块（CONFIG 块写两次）
- 位置：
  - `scripts/daily_report.py:30-38` — `RESULT_DIR` / `SELF_STOCK_FILE` / `FOCUS_STOCK_FILE` 定义两次（line 31-33 + line 35-38 重复块，仅用 line 35-38）
  - `scripts/daily_report.py:137` 与 `:578` — `factor_names` 列表重复定义（全局 `FACTOR_LIST` + HTML 内局部 `factor_names`）
  - `scripts/daily_report.py:309-540`（generate_report）与 `544-1035`（generate_html_report）— 同样 8 个板块的逻辑几乎复制粘贴
  - `scripts/daily_report.py:42-94` — `get_stock_changepct` 与 `get_stock_price_info` 函数做几乎相同的事
- 后果：维护成本高；文件 1068 行的主因
- 建议：把 8 个板块的"数据计算"抽成纯函数（return dict），Markdown/HTML 各自渲染

### [P1] daily_report.py 多个未使用的 import
- 位置：`scripts/daily_report.py:11-13`
- 现象：
  ```python
  import requests
  import re
  from datetime import datetime, timedelta  # timedelta 未用
  ```
  全文 0 处使用（`requests` 留作旧版妙想 API 残留；`re` 在 daily_report.py 完全未用；`timedelta` 仅 datetime 使用）
- 建议：删除 `import requests`, `import re`，把 `from datetime import datetime, timedelta` 改为 `from datetime import datetime`

### [P1] signals_latest.csv 是普通文件覆盖式（与 CLAUDE.md 文档矛盾）
- 位置：`scripts/calc_signals.py:267-272`
- 现象：
  ```python
  latest_file = signals_dir / "signals_latest.csv"
  tmp_file = signals_dir / "signals_latest.csv.tmp"
  signals_df.to_csv(tmp_file, index=False, encoding='utf-8-sig')
  os.replace(tmp_file, latest_file)
  ```
  `os.replace` 把临时文件移动重命名为 `signals_latest.csv`（覆盖式），CLAUDE.md 第 141 行写"`signals_latest.csv` - 最新信号" 但未声明类型
- 后果：
  - 实际原子性：`to_csv` 完成后才 `os.replace`，所以读到的是旧 latest 或新 latest（中间状态不可见），是安全的
  - 但语义模糊：是软链接还是普通文件？
  - `apply_cooldown` line 224 用 `if f.stem in ('signals_latest', 'signals_latest.csv.tmp')` 手动排除——表明作者知道这是普通文件而非符号链接
- 建议：在 CLAUDE.md 数据存储段明确"`signals_latest.csv` - 最新信号（普通文件覆盖式，原子替换）"，或改回软链接 `os.symlink(target, link)`（注意 `link.unlink(missing_ok=True)`）

### [P1] daily_report.py Markdown 报告 best/worst 无空保护
- 位置：`scripts/daily_report.py:430-431`
- 现象：
  ```python
  best = max(focus_today.items(), key=lambda x: float(x[1]['total_score']))
  worst = min(focus_today.items(), key=lambda x: float(x[1]['total_score']))
  ```
  如果 `focus_today` 为空，`max({}.items())` 会抛 `ValueError: max() arg is an empty sequence`
- 后果：所有关注股票都被排除时报告生成崩
- 证据：HTML 报告 line 856 已加 `if focus_avg_scores:` 保护（line 857/858），但 Markdown 报告 line 417 的 `if focus_avg:` 不能保证 `focus_today` 非空（间接保护）
- 建议：把 line 430-433 包在 `if focus_today:` 内

### [P1] run_v2_backtest.py 参数网格密 + 与 CLAUDE.md 实盘决策不完全对齐
- 位置：`scripts/run_v2_backtest.py:108-121`
- 现象：
  - 止盈 {5,10,15,20,30} × 止损 {3,5,8,10} × 冷却期 {0,1,3} = 60 种 × 2 排序 = 120 种
  - `buy_threshold=30`（固定）
  - 但 CLAUDE.md line 117（2026-06-15 实盘决策）记录"v1+总评分，止盈20%/止损8%/冷却3天"
  - run_v2_backtest.py 是 v2 不是 v1，与决策方向不同
- 后果：
  - 参数网格太密（120 种），跑全量耗时长
  - 60 种组合里很多（止盈 30%、止损 3%）是反逻辑，几乎不会出现最优
- 建议：
  - 既然用户已决策 v1+20%/8%/3天，回测脚本应聚焦 v1 复现 + 微调 ±5% 范围
  - 或新增 `run_v1_backtest.py` 对应 v1 策略，与 run_launch_backtest.py 互补

### [P1] daily_report.py datetime.now() 无时区
- 位置：`scripts/daily_report.py:333, 1032`
- 现象：
  ```python
  lines.append(f"📅 日期: {today_date} (截至 {datetime.now().strftime('%Y-%m-%d %H:%M')})")
  ...
  f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
  ```
- 后果：服务器迁移到 UTC 或异地时，报告"生成时间"含义会无声改变
- 建议：用 `datetime.now().astimezone()` 或显式 `+08:00` 标注

### [P1] reports/index.html 是覆盖式副本，与 daily_report_latest.md 不一致
- 位置：`reports/index.html`, `reports/daily_report_latest.md`
- 现象：
  - `index.html` 由 evening_pipeline.sh:44 `cp ... reports/index.html` 覆盖式更新（最新 2026-06-15 19:37）
  - `daily_report_latest.md` **stale 2026-05-15 23:44**（整整一个月没更新！）
  - `daily_report_latest.html` 文件**根本不存在**（README 提到但代码不产出）
- 后果：用户从 auto-claw.top/reports 看 index.html 是新鲜的，但 README 提到 latest.html 不存在；latest.md 是陈旧数据
- 建议：要么产 daily_report_latest.html/.md（两个都覆盖式），要么删 stale 文件 + 改 README

### [P2] daily_report.py 搜索功能 unicode/空格不严谨
- 位置：`scripts/daily_report.py:964`
- 现象：`stockData.filter(s => s.code.includes(input) || s.name.toLowerCase().includes(input))`
- 后果：搜"平安"会同时命中"中国平安"和"平安银行"；中英文混搜、大小写、空格未规范化
- 建议：现状可接受，仅供未来优化

### [P2] dp_diff_factor 未纳入 FACTOR_LIST（CLAUDE.md 说 9 因子）
- 位置：`scripts/daily_report.py:137` vs `src/factors/dp_diff_factor.py`（存在但未纳入）
- 现象：CLAUDE.md line 50-58 写"已实现的因子（共9个，总分100分）"包含 dp_diff_factor；`daily_report.py` 的 `FACTOR_LIST` 也是 9 个但名字不一致（"今年相对大盘强弱" vs "dp_diff"）
- 后果：用户看 daily_report 看不到 dp_diff 因子分数
- 建议：澄清 dp_diff_factor 是否要纳入；如要，更新 daily_report.py FACTOR_LIST 和字段映射

### [P2] 日志分散，按脚本分目录
- 现象：`logs/` 下分 `daily_download_${date}.log` / `daily_fetch_${date}.log` / `evening_pipeline_${date}.log` / `future_return_${date}.log` 等
- 后果：排障要查多个文件；命名格式不统一
- 建议：所有 daily_* 脚本统一写到 `logs/${date}/...` 子目录

### [P3] daily_report_cron.sh 是旧版 wrapper，未删除
- 位置：`scripts/daily_report_cron.sh`（18 行）
- 现象：仅 18 行，无交易日检查、无 fail 处理，被 `evening_pipeline.sh` 取代但保留
- 建议：删除或归档

### [P3] reports/individual/generated_at.json 用日期判断，无交易日过滤
- 位置：`scripts/stock_analysis.py:565-568, 596-597`
- 现象：`cache[code] == today` 用 `YYYY-MM-DD` 比较；非交易日搜股会重生成报告
- 建议：用 `data/calendar/trade_days.csv` 过滤

### [P3] daily_data_fetch.py cron 时间变更（17:00，原 16:00）
- 现象：从 `0 16 * * 1-5` 改为 `0 17 * * 1-5`（晚 1 小时）
- 评论：合理改善（akshare 16:00 数据可能不全），标记 P3 仅供记录

## 3. 改进建议（非问题，但有更好做法）

1. **流水线分阶段恢复**：把 step 3 (calc_signals) + step 3.5 (sim_trader) 加回 evening_pipeline.sh，否则信号系统处于"半残"状态
2. **daily_report.py 重构**：把 8 板块逻辑抽成纯函数，Markdown 和 HTML 共用数据计算，分文件输出
3. **CLAUDE.md 与代码同步**：CLAUDE.md line 113 提到"行业分析"但代码无 — 应要么补实现，要么删文档
4. **daily_report.py 改用 argparse**：支持 `--date`、`--pool`、`--no-html`、`--no-md`，便于测试和重跑
5. **统一 cron 时段**：daily_data_fetch 17:00 → future_return 18:00 → evening_pipeline 19:00，节奏清晰
6. **sim_trader.py 重新纳入流水线**：上次审查已建议，sim_trader.py 仍存在且代码健康（12.9KB），但 evening_pipeline 不再调它

## 4. 需要核实的不确定项

1. **run_v2_backtest.py 实际产出**：`result/backtest/v2_首次突破_资金固定_2天建仓/` 目录是否存在最新结果（未 grep）
2. **sim_trader.py 是否真的不被调**：可能 api/main.py 或别处调用，需 grep
3. **daily_future_return.sh 标签产出**：`result/future_returns/` 是否更新（未查）
4. **CLAUDE.md line 113 "行业分析"是文档期望还是历史**：可能是 v1 实现过被删除
5. **stock_analysis.py 修改原因**：RESULT_DIR 路径从 `src/result` → `result/daily_score`，与 src 目录清理一致，但 stock_analysis.py 仍硬编码绝对路径
6. **daily_report_latest.md 是否会定期更新**：文件 mtime 2026-05-15，可能被某个旧 cron 写入，现已停止
7. **sim_trader.py 与 calc_signals.py SELL 逻辑的关系**：两者都生成 SELL 信号，但 sim_trader 是持仓管理 + 写数据库，calc_signals 仅生成信号 CSV，可能并存

## 5. 评分（1-5，5 = 优）

- **正确性：2**（流水线丢失 calc_signals 步骤导致 signals 过期；节假日跳过丢失；sim_trader 不再被自动调用；行业分析缺失；daily_report 仍 418KB）
- **可维护性：2**（daily_report.py 1068 行重复严重；硬编码路径；未用 import；P1 best/worst 仍无空保护）
- **性能：3**（流水线 3 步 ~5-15 分钟可接受；daily_report.py 400KB HTML 偏大；calc_signals 仍有信号计算缓存）
- **文档：3**（CLAUDE.md line 113 行业分析未实现；README_每日评分网页系统.md 8 板块描述对得上；sim_trader 仍 12KB 但无 docstring 说明为何不调）
- **总评：2**（本轮最大问题是流水线缩水，signals 系统处于半残；其余与上次审查一致无改善）

---

## 附：与上次审查 P0/P1 修复对照表

| 上次 P0 | 现状 | 评价 |
|--------|------|------|
| P0-1 节假日 grep 模式不匹配 | **整段被删除**（既未修也未保留） | 恶化 |
| P0-2 行业分析板块缺失 | 仍未实现 | 未修 |
| P0-3 calc_signals 只产 BUY | **已修复**（line 277-364 新增 SELL） | 修复 |
| P0-4 daily_report.py 400KB JSON | 仍 418KB（基本未改善） | 未修 |
| P0 sim_trader 失败吞错（P1） | sim_trader 不再被流水线调用，问题"消失" | 伪修复（功能丢失） |

| 上次 P1 | 现状 | 评价 |
|--------|------|------|
| 硬编码绝对路径 | 仍 8 处硬编码 `/home/admin/AUTO-STOCK/...` | 未修 |
| daily_report.py 重复代码块 | CONFIG/factor_names 仍重复定义 | 未修 |
| 未使用 import | `requests`, `re`, `timedelta` 仍在 | 未修 |
| signals_latest 软链接 vs 普通文件 | 仍为普通文件覆盖式，文档未对齐 | 未修 |
| daily_report.py 时间戳无时区 | 仍 `datetime.now()` 无 tz | 未修 |
| main.py 通过 stdin 注入 | 仍 `printf "2\nstock_pool.csv\n\n"` | 未修 |
| daily_report_latest.html 缺失 | daily_report_latest.md stale 2026-05-15，.html 不存在 | 未修 |
| daily_report.py best/worst 空保护 | HTML 已修，Markdown line 430 未修 | 部分修 |