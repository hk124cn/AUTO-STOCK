# 更新日志

## [1.1.0] - 2026-06-16

### 新增
- 信号监控页面新增"财报"分数列（满分20分的财务因子子分数）
- v2 策略默认按财报分数排序（v1 仍按7日均分排序）
- `score_price_history.csv` 新增 `finance_score` 列
- 信号数据新增 `finance_score` 字段
- `scripts/stock_analysis.py` 个股深度分析报告

### 修复
- Signals.vue 变量前向引用导致页面白屏
- `main.py` 输出路径统一到 `result/daily_score/`
- `api/main.py` 3个报告接口路径修复（reports/search, today, top）
- `scripts/stock_analysis.py` 数据源修复（src/result → result/daily_score）
- 6.15 评分数据恢复（原文件是 6.12 的复制品）

### 变更
- 数据目录统一：所有评分数据读写均使用 `result/daily_score/`
- 旧 `src/result/` 目录移至 `.trash/`

---

## [1.0.0] - 2026-06-12

### 新增
- 信号监控功能（v1/v2 策略版本）
- 持仓管理功能（模拟/实盘账户）
- 个股分析功能
- 收益统计功能
- 策略管理（v1 每日触发 / v2 首次突破）

### 修复
- 无

### 变更
- 无

---

## [0.1.0] - 2026-06-12

### 新增
- 启动信号分析（2022-2026年）
- 预警系统扩展（信号标记）
- 定时任务修改（信号计算）
- 备份脚本修改（完整备份）

### 修复
- 无

### 变更
- evening_pipeline.sh 添加信号计算步骤
- r2_backup.py 备份整个AUTO-STOCK目录
- CLAUDE.md 添加新系统说明
