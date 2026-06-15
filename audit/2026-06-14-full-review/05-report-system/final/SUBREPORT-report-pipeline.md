# 子报告：报告与流水线 (#5 报告系统)

> 范围：
> - `scripts/daily_report.py`（含 `.bak` / `.fix` 旧版对比）
> - `scripts/evening_pipeline.sh`
> - `scripts/daily_data_fetch.py` / `daily_download.py` / `daily_fund_flow.py` / `daily_industry_change.py`
> - `scripts/calc_signals.py`
> - `scripts/precompute_scores.py` / `scripts/launch_analysis.py`
> - `scripts/daily_report_cron.sh`（旧版 cron 包装）
> - `reports/` 产物（html / md / individual）
>
> 严重程度评级：P0=功能错误/P1=性能或可维护性/P2=可改进/P3=小问题
> 审查日期：2026-06-14

## 1. 概览

本子模块串联三件事：数据拉取（每日 16:00）、评分与信号（每日 19:00）、HTML/Markdown 报告（19:00 之后）。整体可运行，2026-06-11 当晚流水线在 2770 秒内走完 4 步并产出 `reports/daily_report_20260611.html`，可被前端 `auto-claw.top/reports` 正常访问。

但 **CLAUDE.md 描述与实现存在多处不一致**：① 节假日跳过逻辑因格式不匹配实质失效；② `signals_latest.csv` 实际不是软链接而是覆盖式普通文件（与 CLAUDE.md "signals_latest 是软链接" 矛盾）；③ CLAUDE.md 提到的"行业分析"板块在 daily_report.py 中并不存在，仅有 8 个板块中的"特别关注股票"间接涵盖个股，未做行业聚合；④ 流水线文档承诺的"任一步失败会停在该步"仅对核心 4 步有效，`sim_trader.py` 失败被静默吞掉且仅 `echo` 警告。

代码质量上，`daily_report.py`（1069 行）有大量重复代码块、3 个未使用的 import、硬编码绝对路径，且把所有股票 JSON 序列化到 HTML（400+KB），可维护性和性能均有改进空间。

## 2. 关键发现（按严重程度降序）

### [P0] 节假日跳过逻辑因 grep 模式不匹配而失效
- 位置：`scripts/evening_pipeline.sh:37`
- 现象：
  ```bash
  if ! grep -q "^${TARGET_DATE}" "$TRADE_CALENDAR" 2>/dev/null; then
      echo "ℹ️  ${TARGET_DATE} 不是交易日（节假日），跳过流水线"
      exit 0
  fi
  ```
  但 `data/calendar/trade_days.csv` 实际格式为 `YYYY-MM-DD`（例如 `2026-06-14`），而 `TARGET_DATE` 是 `YYYYMMDD`（例如 `20260614`）。`grep "^20260614"` 永远不会匹配 `2026-06-14`。
- 后果：流水线的"交易日检查"形同虚设。周日/节假日 cron 也会跑，遇到 `data/daily_market/${TARGET_DATE}.csv` 不存在时由 step 0 兜底报错 `exit 1`，但 cron 会按计划每天 19:00 启动并写入失败日志。
- 证据：
  - `data/calendar/trade_days.csv` 前 3 行：`trade_date\n1990-12-19\n1990-12-20`
  - 同样问题在 `daily_download.py:37` 使用 `is_trade_day()` 但该函数依赖同目录文件无格式问题
- 建议：将日历写入紧凑格式 `YYYYMMDD`，或在 evening_pipeline.sh 中把 `TARGET_DATE` 转为 `YYYY-MM-DD`：
  ```bash
  DATE_HUMAN=$(date -d "${TARGET_DATE}" +%Y-%m-%d 2>/dev/null || echo "$TARGET_DATE")
  if ! grep -q "^${DATE_HUMAN}" "$TRADE_CALENDAR"; then ...
  ```

### [P0] 报告缺少"行业分析"板块（CLAUDE.md 提到但代码中未实现）
- 位置：`scripts/daily_report.py:309-540`（generate_report）、`scripts/daily_report.py:544-1035`（generate_html_report）
- 现象：CLAUDE.md 提到"行业分析、特别关注股票、收盘价、涨跌幅"是每日报告的核心内容，但 `daily_report.py` 仅产出 8 个板块：
  1. 大盘概览
  2. TOP 榜单（个股维度）
  3. 自选股专区（个股维度）
  4. 特别关注股票分析（个股维度）
  5. 今日 vs 昨日对比（个股维度）
  6. 5日评分走势（个股维度）
  7. 风险提示（个股维度）
  8. 投资建议（个股维度）
  
  其中**完全没有"行业维度"统计**。所有"行业"信息只以个股为单位分散在评分里（来自 `行业相对强弱` 因子）。
- 后果：用户无法从报告里看到"今日哪些行业评分整体偏高/偏低"。需要去 `data/industry/change_*.csv` 自行分析。
- 建议：在板块二和板块三之间新增"行业分析"：
  - 按申万二级聚合今日所有股票的总分取平均
  - 显示 Top-5 / Bottom-5 行业
  - 展示行业涨跌幅（来自 `data/industry/change_<swcode>_20d.csv`）

### [P0] calc_signals.py 只产出 BUY 信号，无 SELL 信号定义
- 位置：`scripts/calc_signals.py:150-151`
- 现象：
  ```python
  'signal': 'BUY' if avg_score >= BUY_THRESHOLD else '',
  ```
  `signal` 字段仅 `BUY` 或 `''`（空字符串），CLAUDE.md 同样只描述买入："前 7 天平均分 ≥ 30 分（买入信号）"。但卖出逻辑完全缺失：流水线、产品文档均无 SELL 阈值或规则。
- 后果：所有前端展示（`auto-claw.top/yujing/` 个股预警、`stock.auto-claw.top/signals` 信号监控）只能告诉用户"买什么"，无法给出"已持仓卖出时机"。
- 建议：在 CLAUDE.md 和 calc_signals.py 中明确定义 SELL 信号，例如：
  - 当前分 < 前 7 日均分 × 0.5（评分显著回落）
  - 或当前分 < 阈值（如 20 分）
  
  输出字段保留 `'signal': 'BUY' / 'SELL' / ''`。

### [P0] daily_report.py 内嵌整张 today_data JSON 到 HTML，导致单文件 400+KB
- 位置：`scripts/daily_report.py:956-957`
- 现象：
  ```python
  stock_data_js = str(today_data).replace("'score'", "'total_score'")
  h.append('<script>const stockData = ' + stock_data_js + ';')
  ```
  `today_data` 是 1300+ 只股票 × 9 因子字段的字典列表，被 `str()` 序列化为内嵌 JS 变量。
- 后果：
  - 实测 `reports/daily_report_20260611.html` 大小 **420539 字节**（约 410KB），每次跑流水线都被复制到 `reports/index.html`
  - 搜索引擎/前端爬取浪费带宽
  - 替换 `'score' → 'total_score'` 实际上 batch_result CSV 没用 `'score'` 字段名，所以 replace 是个 dead code
- 建议：把 `stockData` 改为按需从 `/api/...` 异步加载，或分页到后端；至少应改为 `JSON.stringify(json.load(csv))`。

### [P1] evening_pipeline.sh 的"4 步失败会停在该步"只对核心 4 步生效，sim_trader 失败被静默吞掉
- 位置：`scripts/evening_pipeline.sh:75-81`
- 现象：
  ```bash
  step 3.5 "模拟仓自动交易"
  if [ -f "scripts/sim_trader.py" ]; then
      python3 scripts/sim_trader.py --date "$TARGET_DATE" || echo "⚠️  模拟仓交易失败（不影响主流程）"
      echo "✅  模拟仓交易完成"
  fi
  ```
  `|| echo` 让 `set -e` 不触发，模拟仓失败不会终止流水线，但脚本仍打印 `✅  模拟仓交易完成` 误导用户。
- 后果：模拟仓失败被静默吞错；日志显示"完成"但实际未跑成。CLAUDE.md 说"任一步失败会停在该步"，但 sim_trader 实际是"任一步失败会被掩盖"。
- 证据：`set -euo pipefail` 在 line 7 生效，sim_trader 块因 `|| echo` 变成"必须成功"的反义
- 建议：要么把 sim_trader 列为独立的、有 `fail` 的真步骤，要么把 `|| echo` 改为 `|| fail "sim_trader"`。

### [P1] signals_latest.csv 是普通文件不是软链接（与 CLAUDE.md 文档矛盾）
- 位置：`scripts/calc_signals.py:215-220`
- 现象：
  ```python
  latest_file = SIGNALS_DIR / "signals_latest.csv"
  tmp_file = SIGNALS_DIR / "signals_latest.csv.tmp"
  signals_df.to_csv(tmp_file, index=False, encoding='utf-8-sig')
  os.replace(tmp_file, latest_file)
  ```
  CLAUDE.md 写："`signals_latest.csv` - 最新信号（软链接）"。但实际 `os.replace` 把临时文件**移动并重命名**为 `signals_latest.csv`（不是创建符号链接）。
- 证据：
  ```
  /home/admin/AUTO-STOCK/result/signals/signals_latest.csv: UTF-8 Unicode (with BOM) text
  file 类型：regular file, Links: 1
  ```
- 后果：行为差异：
  - 软链接模式：可同时访问 `signals_latest.csv` 和 `signals_YYYYMMDD.csv`，互不干扰
  - 覆盖式：每次跑 `signals_latest.csv` 都会被**整文件覆盖**，如果同时有人在读旧 latest（如 API 没缓存），会读到不完整内容；`os.replace` 在 POSIX 上是原子的，但 `to_csv` 之前有一段时间 tmp 是半成品
  - 实际原子性：to_csv 完成后才 `os.replace`，所以从外部读到的要么是旧 latest，要么是新 latest（中间状态不可见），这点其实安全。但语义和文档不一致
- 建议：二选一
  - 要么改回 `os.symlink(target, link)`（注意需要先 `link.unlink(missing_ok=True)`）
  - 要么更新 CLAUDE.md 明确"最新信号副本（普通文件，覆盖式）"
- 同源代码异味：`calc_signals.py:175-178` 用 `if f.stem in ('signals_latest', ...)` 排除 latest 文件——这是因为它现在是普通文件而不是软链接，需要手动排除以避免把它当作历史信号读。如果改回软链接，这段排除逻辑可以删除。

### [P1] daily_report.py 大量重复代码块（DRY 违反）
- 位置：
  - `scripts/daily_report.py:31-38` — CONFIG 块重复定义两次（RESULT_DIR / SELF_STOCK_FILE / FOCUS_STOCK_FILE）
  - `scripts/daily_report.py:137` 与 `:578` — `factor_names` 列表重复定义（全局 FACTOR_LIST + generate_html_report 内局部变量）
  - `scripts/daily_report.py:309-540`（generate_report）与 `544-1035`（generate_html_report）— 同样 8 个板块的逻辑几乎复制粘贴：自选股读取、特别关注、对比、5日走势、风险提示
  - `scripts/daily_report.py:42-94` — `get_stock_changepct` 与 `get_stock_price_info` 两个函数做几乎相同的事（都从本地 CSV 读收盘价算涨跌幅），区别仅在返回字段
- 后果：维护成本高，任何板块调整都要改两处（且容易只改一处）。文件 1069 行的主要来源就是这种重复。
- 建议：把 8 个板块的"数据计算"抽成纯函数（return dict），然后 `generate_report` 调一次计算 + Markdown 模板，`generate_html_report` 调一次计算 + HTML 模板。

### [P1] daily_report.py 多个未使用的 import（import 错误）
- 位置：`scripts/daily_report.py:11-12`
- 现象：
  ```python
  import requests
  import re
  ```
  全文 0 处使用（`grep -E "^\s*(requests|re)\." 0 命中`）。`from datetime import datetime, timedelta` 中 `timedelta` 也是未使用（line 13，行内 `from datetime import datetime, timedelta` 后只有 `datetime.now()` 用到 datetime）。
- 后果：
  - 早期 .bak/.fix 版本使用 `requests`（妙想API），迁到本地 CSV 后未清理 import
  - 表明 dead code，可能诱导维护者误以为有 API 调用
- 建议：删除 `import requests` 和 `import re`，把 `from datetime import datetime, timedelta` 改为 `from datetime import datetime`。

### [P1] 硬编码绝对路径，可移植性差
- 位置：
  - `scripts/daily_report.py:31, 32, 33, 36, 37, 38, 41, 586, 599` — 全部 `/home/admin/AUTO-STOCK/...`
  - `scripts/calc_signals.py:24, 25, 26` — `ROOT_DIR = Path(__file__).resolve().parent.parent`（正确，相对路径）
- 现象：daily_report.py 把 `RESULT_DIR`, `SELF_STOCK_FILE`, `FOCUS_STOCK_FILE`, `PRICE_DIR` 都写死成绝对路径，且全部重复两次。
- 后果：在别的机器、CI、Docker 里运行都会直接失败。
- 建议：与 calc_signals.py 一致用 `Path(__file__).resolve().parent.parent` 计算根目录，去掉所有 `/home/admin/AUTO-STOCK/...` 前缀。

### [P1] daily_report.py 时间戳无时区
- 位置：`scripts/daily_report.py:333, 1032`
- 现象：
  ```python
  lines.append(f"📅 日期: {today_date} (截至 {datetime.now().strftime('%Y-%m-%d %H:%M')})")
  ...
  f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
  ```
  `datetime.now()` 返回本地时间（服务器时区），无时区标记。
- 后果：服务器迁移到 UTC 或异地时，报告里的"生成时间"会无声改变含义。
- 建议：用 `datetime.now().astimezone()` 或显式标注时区（如 `+08:00`）。考虑到项目部署在阿里云，固定写 `Asia/Shanghai` 或 UTC+8 即可。

### [P1] main.py 通过 stdin 注入，易碎且与 README 文档不一致
- 位置：`main.py:95-109`、`scripts/evening_pipeline.sh:57`
- 现象：流水线用 `printf "2\nstock_pool.csv\n\n"` 喂给 `main.py`。`main.py` 走 `input()` 读模式、股票池文件名、结果名。第三个空行让 `in_fname == ''`，触发默认文件名 `batch_result_{today}.csv`（main.py:87-88）。
- 后果：
  - 这种 "通过 stdin 注入交互式菜单" 极度脆弱：
    - 多/少一个换行都会让 `in_fname` 取到错的值（不是日期）
    - 若 `main.py` 改成"读取非空值才退出"，会立刻挂
  - `daily_report.py` (line 1044) 实际上**假设 `batch_result_${today}.csv` 存在**（依赖默认输出名）。一旦 `main.py` 改动输出名规则，daily_report 静默失败。
- 建议：把 `main.py` 重构为 CLI 入口（`argparse`），流水线直接传 `--batch stock_pool.csv --output result/daily_score/batch_result_${TARGET_DATE}.csv`。

### [P1] daily_report.py 没有生成 daily_report_latest.html（CLAUDE.md/README 与实现不符）
- 位置：CLAUDE.md / `scripts/README_每日评分网页系统.md` 提到 `reports/daily_report_latest.html`，但流水线只产出 `daily_report_${date}.html` 并复制到 `reports/index.html`
- 证据：
  ```
  /home/admin/AUTO-STOCK/reports/index.html        (current latest, 复制自 daily_report_20260611.html)
  /home/admin/AUTO-STOCK/reports/daily_report_latest.html.bak   (旧 2026-05-18, 不再更新)
  /home/admin/AUTO-STOCK/reports/daily_report_latest.md        (旧 2026-05-15, 不再更新)
  ```
- 后果：与 README 文档不一致；阅读者以为有 latest 软链接会去找，发现不存在。
- 建议：要么产出 `daily_report_latest.html`（与 .md 配套），要么更新 README 改口。

### [P2] 日志分散，按脚本分目录而非统一入口
- 现象：
  - `evening_pipeline.sh` → `logs/evening_pipeline_${date}_${HHMMSS}.log`
  - `daily_download.py` → `logs/daily_download_${date}.log`
  - `daily_data_fetch.py` → `logs/daily_fetch_${date}.log`
  - `calc_signals.py` → 无独立日志文件（stdout 重定向到 evening_pipeline.log）
- 后果：排障时要查多个文件；按日期分散但日志文件名格式不统一（pipeline 加时间戳，download 不加）。
- 建议：要么所有脚本统一写到 `logs/${date}/...`，要么把 daily_data_fetch 与 evening_pipeline 合成一个日志。

### [P2] calc_signals.py apply_cooldown cutoff 命名误导
- 位置：`scripts/calc_signals.py:169`
- 现象：`cutoff = (target_dt - timedelta(days=cooldown_days * 2)).strftime('%Y%m%d')`，变量名"cutoff"实际是过滤范围起点（更早于它的历史信号文件被忽略）。代码也只读了 `2 * cooldown_days` 范围内的历史，**cooldown_days 本身控制冷却期长度**，但 cutoff 范围又是它的 2 倍，逻辑链混乱。
- 后果：读者难以理解"为什么 cooldown 是 1 天，但 cutoff 又是 2 天前"。
- 建议：把变量名改为 `history_window_start`，并在函数 docstring 里说清楚："cooldown_days 控制信号间隔，history_window 是 cooldown × 2 用来确保读够最近一次信号"。

### [P2] daily_report.py 对 best/worst 不在评分池时的处理不一致
- 位置：`scripts/daily_report.py:430-433` 与 `:857-863`
- 现象：
  ```python
  best = max(focus_today.items(), key=lambda x: float(x[1]['total_score']))
  worst = min(focus_today.items(), key=lambda x: float(x[1]['total_score']))
  ```
  如果 `focus_today` 为空（所有关注股票都不在评分池），`max({}.items(), ...)` 会抛 `ValueError: max() arg is an empty sequence`。
- 后果：所有关注股票都被排除时（例如当天只有 5 只自选股、没有 focus），报告生成直接崩。
- 证据：`if focus_avg_scores:` 在 line 856 检查了，但 line 430 在 generate_report 函数里**没有同样的保护**。
- 建议：两处都用 `if focus_today:` 包住 best/worst 计算。

### [P2] daily_report.py 中 str(today_data) 注入的搜索功能无法处理中文股票名
- 位置：`scripts/daily_report.py:964`
- 现象：
  ```javascript
  const matches = stockData.filter(s => s.code.includes(input) || s.name.toLowerCase().includes(input));
  ```
  输入框 placeholder 是中文 "输入代码或名称搜索 (如: 000858 或 茅台)"，但搜索逻辑只把 `input.toLowerCase()` 后 `includes` 中文。`"茅台".toLowerCase() = "茅台"`，而 batch_result 中 name 列也是中文，所以匹配工作；但**用户搜"茅台"时大小写、Unicode 标准化、空格处理未考虑**。
- 后果：搜索"平安"可能命中"中国平安"也可能命中"平安银行"，逻辑没问题；但模糊程度不可控。
- 建议：保持现状即可，标记为 P2 仅供未来优化。

### [P2] daily_industry_change.py 每次跑会拉 131 次接口（5+ 分钟）
- 位置：`scripts/daily_industry_change.py:130-141`
- 现象：`for idx, item in enumerate(SW_CODES): ... time.sleep(REQUEST_DELAY)` 配 `REQUEST_DELAY = 2.0`，131 × 2 秒 ≈ 262 秒 ≈ 4.5 分钟。
- 后果：流水线 step 0 前的数据拉取耗时长（每日 16:00 跑，加上其他步骤可能要 30+ 分钟）。
- 建议：用 `asyncio + aiohttp` 或 `concurrent.futures.ThreadPoolExecutor` 并发，把 5 分钟压到 1 分钟。

### [P2] daily_fund_flow.py 不分页/无并发
- 位置：`scripts/daily_fund_flow.py:38`
- 现象：`ak.stock_fund_flow_individual(symbol='5日排行')` 单次请求全市场资金流向。如果数据量 5000+ 条，请求 1-3 秒可接受；但若失败，retry 3 次共 9 秒等待。
- 建议：现状可接受，标记 P2。

### [P2] dp_diff_factor.py 未被任何报告板块使用
- 位置：`src/factors/dp_diff_factor.py`（存在）vs `scripts/daily_report.py:137`（FACTOR_LIST 不包含）
- 现象：CLAUDE.md 写"共 9 个因子，总分 100 分"，但 `daily_report.py` 的 FACTOR_LIST 实际包含 9 个字符串（`关注度, 单日涨跌幅, 股息率, 今年相对大盘强弱, 财报, 5日涨跌幅, 行业相对强弱, 新闻, 资金流向`），与 `dp_diff_factor.py` 的因子名不一致。
- 后果：`dp_diff_factor` 分数如果计算出来，daily_report 不会展示，9 因子描述对不上。
- 建议：澄清 `dp_diff_factor` 是否要纳入；如要，更新 daily_report.py FACTOR_LIST。

### [P3] daily_report.py.bak 与 .fix 文件残留
- 位置：`/home/admin/AUTO-STOCK/scripts/daily_report.py.bak` (45367 字节, May 15)、`/home/admin/AUTO-STOCK/scripts/daily_report.py.fix` (45367 字节, May 18)
- 现象：两个旧版本文件大小完全相同（diff 后几乎一致），使用妙想 API（`mx_apikey`）而非本地 CSV。最新 `daily_report.py` 已经在 2026-05-18 后迁移到本地 CSV。两个 .bak/.fix 未删除。
- 建议：清理（移到 `archive/` 或删除）。

### [P3] daily_report_cron.sh 是旧版 cron 包装，未在用
- 位置：`scripts/daily_report_cron.sh`
- 现象：仅 18 行，无交易日检查、无 fail 处理、无备份机制，被 `evening_pipeline.sh` 取代但保留。
- 建议：删除或归档。

## 3. 改进建议（非问题，但有更好做法）

1. **daily_report.py 应输出 daily_report_latest.html**：与 README 一致，便于前端不必依赖 index.html 复制。
2. **calc_signals 输出 SELL 信号**：参见 P0 描述的 SELL 信号定义。
3. **daily_report.py 改用 argparse 入口**：支持 `--date`、`--pool`、`--no-html`、`--no-md`，便于测试和重跑。
4. **evening_pipeline.sh 增加 CI-friendly 退出码**：例如把"假日跳过"的 exit 0 改为 exit 64，让 cron 报警能识别"非失败但未执行"。
5. **增加"行业分析"板块**：见 P0 描述。
6. **sim_trader 失败后单独写日志文件**：避免被吞错时无法追溯。
7. **统一日志格式**：所有 daily_* 脚本的 logger 使用相同的 `(asctime) (levelname) (message)` 格式。

## 4. 需要核实的不确定项

1. **CLAUDE.md "9 因子" 是否包含 dp_diff_factor**：CLAUDE.md 写 "9 因子"，但 FACTOR_LIST 里只有 9 个名字，且 dp_diff_factor 出现但未被纳入。需要查 `src/core/scoring_engine.py` 确认加权逻辑。
2. **"行业分析"是 CLAUDE.md 笔误还是漏实现**：可能在更早版本中存在，被删除。需查 git log。
3. **daily_report_latest.html 是否真的被前端引用**：可能是 CLAUDE.md 的过时描述。
4. **sim_trader 是否重要**：从 `|| echo` 模式看，作者主观认为不重要，但被列入 step 3.5 又像是重要步骤。
5. **stocks_data JSON 内嵌的搜索功能**：实际有多少用户用？若无人用，可以移除内嵌 JSON 大幅瘦身 HTML。

## 5. 评分（1-5，5 = 优）

- **正确性：3**（主要功能可工作，但节假日跳过逻辑失效、缺失行业分析、SELL 信号未定义、与 CLAUDE.md 描述不一致）
- **可维护性：2**（大量重复代码块、硬编码路径、未清理 import、.bak/.fix 残留）
- **性能：3**（流水线 46 分钟可接受；HTML 400KB 偏大但不算瓶颈；行业接口串行慢）
- **文档：2**（CLAUDE.md 与代码多处不一致，README 提到 latest.html 但未生成；sim_trader 失败被静默）
- **总评：3**（能用，但有 P0 级别 bug 必须修；改进潜力大）