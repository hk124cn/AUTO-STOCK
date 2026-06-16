# 文档目录

## 项目文档

- [CLAUDE.md](../CLAUDE.md) - 项目主文档
- [README.md](../README.md) - 项目说明
- [HANDOVER.md](../HANDOVER.md) - 交接文档

## 子系统文档

### 股票操作系统
- [README.md](stock-system/README.md) - 系统说明
- [FEATURES.md](stock-system/FEATURES.md) - 功能说明
- [API.md](stock-system/API.md) - API文档
- [TESTING.md](stock-system/TESTING.md) - 测试用例
- [CHANGELOG.md](stock-system/CHANGELOG.md) - 更新日志
- [DEPLOYMENT.md](stock-system/DEPLOYMENT.md) - 部署说明

### 回测系统
- [回测结果](../result/backtest/) - 回测结果归档

### 预警系统
- [信号功能说明](../web/stock-alert/SIGNAL_FEATURE.md) - 信号功能说明

## 数据文档

- [评分数据](../result/score_price_history.csv) - 评分-价格历史大表
- [回测结果](../result/backtest/) - 回测结果归档

## 脚本文档

- [晚间流水线](../scripts/evening_pipeline.sh) - 每日晚间流水线
- [信号计算](../scripts/calc_signals.py) - 每日信号计算（v1/v2 策略）
- [个股分析](../scripts/stock_analysis.py) - 个股深度分析报告

## 维护说明

### 文档更新原则
1. 代码更新时，同步更新文档
2. 文档纳入git版本控制
3. 每月审查一次文档完整性

### 文档责任人
- `CLAUDE.md`：项目负责人
- `docs/stock-system/`：新系统开发人员
- `docs/backtest/`：回测系统开发人员
