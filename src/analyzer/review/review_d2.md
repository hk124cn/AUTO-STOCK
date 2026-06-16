# 代码审查报告 - 分析层规划第二阶段

> 审查日期：2026-05-24
> 审查人：Claude Code
> 阶段：第二阶段（未来收益追踪）
> 审查文件：`src/analyzer/future_return_generator.py`

---

## 概述

第二阶段的核心目标是实现**未来收益标签生成器**（`future_return_generator.py`），读取每日评分结果并计算N天后(5d/10d/20d)的收益率。

---

## ✅ 第二阶段完成情况

| 任务 | 状态 | 备注 |
|------|------|------|
| 2.1 future_return_generator.py 脚本 | ✅ | 已完成并测试 |
| 2.2 设置每日定时任务 | ⚠️ | 计划18:00运行，已写shell脚本 |
| 2.3 回溯生成历史标签 | ⚠️ 部分完成 | 5d数据(5.12-5.15)已生成；10d/20d需等交易日到期，无法提前生成 |

---

## 📋 详细审查

### 1. future_return_generator.py 代码质量

#### 整体评价：⭐⭐⭐⭐☆ 良好

**优点：**

1. **边界情况处理完善**
   - 评分日期超出日历范围 → 返回 None 并记录警告
   - N天后日期未到（数据不完整）→ 跳过而非报错
   - 停牌股（价格不变）→ 单独识别并记录原因
   - 价格文件不存在 → 优雅降级

2. **日志记录清晰**
   ```python
   logger.info(f"✅ 生成 {output_file}: 成功 {success_count}, 失败 {fail_count}")
   ```
   区分 info/debug 级别，便于排查问题

3. **模块化设计**
   - `get_trade_calendar()` - 读取日历
   - `get_nth_trade_day()` - 计算N天后交易日
   - `get_price()` - 获取个股价格
   - `load_batch_result()` - 读取评分文件
   - `generate_future_returns()` - 生成单个文件

4. **数据字段完整**
   - 完全符合 `ANALYZER_PLAN.md` 定义的8个字段
   - `next_nd_return` 保留2位小数

**需改进：**

1. **重复导入**（第13-25行）
   ```python
   import os
   import sys
   import csv
   import logging
   from datetime import datetime
   from typing import Optional, Tuple

   # 重复了
   import os
   import sys
   import csv
   import logging
   from datetime import datetime
   from typing import Optional, Tuple
   ```

2. **价格读取的日期格式处理不一致**（第108行）
   ```python
   if row.get('日期') == date or row.get('日期') == int(date):
   ```
   - 一会儿比较字符串，一会儿比较整数
   - 建议统一为字符串比较或整数比较
   - 当 date='20260512' 时，`int(date)` = 20260512，但 CSV 中日期可能是 "2026-05-12" 格式

3. **缺少对 batch_result 列名的容错**
   ```python
   score = float(row.get('total_score', 0))
   ```
   - 如果 CSV 列名是中文（如"总分"）而非 `total_score`，会静默返回0
   - 建议添加列名映射或警告

4. **未处理复牌当天涨跌幅限制**
   - 股票停牌后复牌首日可能涨跌停，导致价格跳跃
   - 当前逻辑只判断"价格不变=停牌"，未处理"复牌首日涨跌停"

---

### 2. 数据生成情况

| 目录 | 文件数 | 状态 |
|------|--------|------|
| 5d | 4个 | ✅ 已有 `future_5d_20260512.csv` ~ `future_5d_20260515.csv` |
| 10d | 0个 | ⚠️ 仅有 .gitkeep |
| 20d | 0个 | ⚠️ 仅有 .gitkeep |

**问题**：10d 和 20d 数据尚未生成。
- 原因分析：`20260512` + 10个交易日 = `20260526`，今天（24日）还未到
- 但 `20260512` + 20个交易日已过，应已生成
- 可能是脚本未完整运行或中间出错

**建议**：手动运行脚本验证10d/20d生成逻辑：
```bash
python src/analyzer/future_return_generator.py
```

---

### 3. 文档更新情况

`ANALYZER_PLAN.md` 第二阶段状态已更新：

| 任务 | 状态 | 备注 |
|------|------|------|
| 2.1 future_return_generator.py 脚本 | ✅ 完成 | ✅ 完成并测试 |
| 2.2 设置每日定时任务 | ⚠️ 待添加cron | 18:00运行，已写shell脚本 |
| 2.3 回溯生成历史标签 | ✅ 完成 | 已生成5d历史数据(5.12-5.15) |

**问题**：任务2.3标记✅完成，但实际只有5d数据。建议更准确地描述为"部分完成"或"进行中"。

---

## ⚠️ 潜在问题

### 1. 10d/20d 数据暂时无法生成（预期行为）
- `20260512` + 10个交易日 = `20260526`，今天（5/24）还未到
- `20260512` + 20个交易日 = `20260611`，同样未到
- **这是正常的**，脚本已有正确的判断逻辑（第164-167行）：
  ```python
  if nd_date > today:
      logger.info(f"无法计算 {score_date} 的 {n_days}d 收益：{nd_date} 还未到")
      return 0, 0
  ```
- **不是bug，是数据时间窗口限制**。等日期到达后重新运行脚本即可生成。

### 2. 日期格式不一致风险
`get_price()` 中混合使用字符串和整数比较，可能导致某些日期的价格读取失败：
```python
if row.get('日期') == date or row.get('日期') == int(date):
```
建议统一处理。

### 3. 复牌股票处理
停牌股复牌后，如果首日涨跌停，价格会大幅变动。当前逻辑可能误判为"正常交易"。

---

## 💡 建议

### 高优先级

1. **修复重复导入**
   删除第20-25行的重复导入语句。

2. **统一日期格式处理**
   ```python
   # 建议改为：
   date_str = date  # YYYYMMDD
   date_int = int(date)  # 用于比较整数格式

   for row in reader:
       row_date = row.get('日期', '')
       # 处理 "2026-05-12" 和 "20260512" 两种格式
       row_date_clean = row_date.replace('-', '')
       if row_date_clean == date_str:
           price = row.get('收盘')
           ...
   ```

3. **验证10d/20d生成**
   ```bash
   python src/analyzer/future_return_generator.py
   ```
   检查日志输出，确认是否成功生成10d/20d数据。

### 中优先级

4. **添加列名容错**
   ```python
   # 尝试多种可能的列名
   for col in ['total_score', '总分', 'score']:
       score = row.get(col)
       if score is not None:
           score = float(score)
           break
   ```

5. **记录失败原因到文件**
   当前失败原因只记录到日志，建议同时输出到 CSV 的 `fail_reason` 列，便于后续分析：
   ```python
   records.append({
       ...
       'fail_reason': fail_reasons.get(code, '')
   })
   ```

6. **更新文档任务状态**
   任务2.3描述为"已生成5d历史数据(5.12-5.15)"，建议更新为"5d已完成，10d/20d待生成"或等完全完成后再标记✅。

---

## 📊 总结评价

| 维度 | 评价 | 说明 |
|------|------|------|
| 代码质量 | ⭐⭐⭐⭐☆ | 结构清晰，边界处理完善，有重复导入小问题 |
| 功能完成度 | ⭐⭐⭐⭐☆ | 5d数据完整，10d/20d待验证 |
| 文档更新 | ⭐⭐⭐⭐☆ | 状态已更新，有轻微不一致 |
| 鲁棒性 | ⭐⭐⭐☆☆ | 日期格式处理需优化，复牌处理缺失 |

**总体评价**：

`future_return_generator.py` 实现了核心功能，代码结构清晰、边界情况处理完善。**10d/20d数据暂时为空是预期行为**（数据时间窗口未到），不是bug。脚本已有正确的前瞻性检查逻辑。

**主要待改进问题**：
1. 日期格式混合比较（可能读取失败）
2. 重复导入语句

**下一步**：
- 等5/26后验证10d数据生成
- 等6/11后验证20d数据生成
- 修复代码问题（重复导入、日期格式）

---

## 📎 附录：相关文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/analyzer/future_return_generator.py` | ✅ | 核心脚本，289行 |
| `result/future_returns/5d/future_5d_*.csv` | ✅ | 4个文件，5533条记录 |
| `result/future_returns/10d/` | ⏳ | 暂时为空，5/26后生成 |
| `result/future_returns/20d/` | ⏳ | 暂时为空，6/11后生成 |
| `logs/future_return_*.log` | ⚠️ | 日志文件待检查 |