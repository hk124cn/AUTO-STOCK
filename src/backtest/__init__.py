# 回测系统
# 策略类型:
#   - top_n: Top-N 选股策略（等权买入评分最高的N只股票）
#   - signal: 信号触发策略（评分达到阈值触发买卖信号）
#
# 策略版本注册（2026-06-15 起）:
from .strategies import (
    get_strategy,
    list_strategies,
    get_active_config,
    update_active_config,
    switch_signal_version,
    DEFAULT_STRATEGY_VERSION,
    SIGNAL_VERSIONS,
)

__all__ = [
    "get_strategy",
    "list_strategies",
    "get_active_config",
    "update_active_config",
    "switch_signal_version",
    "DEFAULT_STRATEGY_VERSION",
    "SIGNAL_VERSIONS",
]
