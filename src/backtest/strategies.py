"""
策略注册表 + 运行时配置层

注册表定义信号版本默认值，运行时配置层存储前端选择的交易策略。
calc_signals / sim_trader 只读 get_active_config()，一个数据源。

用法:
    from src.backtest.strategies import (
        get_strategy, list_strategies, get_active_config, update_active_config,
        DEFAULT_STRATEGY_VERSION
    )

    # 获取当前配置（信号版本 + 交易策略合并后）
    config = get_active_config()
    print(config['threshold'], config['first_break_only'])

    # 前端选择交易策略后更新
    update_active_config({'threshold': 40, 'take_profit': 0.15, ...})
"""

from typing import Dict, List


# === 信号版本注册表 ===
# 每个版本定义信号逻辑的默认值，交易策略参数可被前端覆盖
SIGNAL_VERSIONS: Dict[str, dict] = {
    "v1": {
        "id": "v1",
        "name": "每日触发",
        "description": "7日均分每天判，达阈值即买入",
        "lookback_days": 7,
        "first_break_only": False,
        "output_subdir": "v1",
    },
    "v2": {
        "id": "v2",
        "name": "首次突破",
        "description": "7日均分首次跨阈值才买（昨<阈值≤今）",
        "lookback_days": 7,
        "first_break_only": True,
        "output_subdir": "v2",
    },
}

# 默认交易策略参数（DB strategies 表的默认值）
DEFAULT_TRADING_PARAMS = {
    "threshold": 30.0,       # 买入阈值
    "take_profit": 0.20,     # 止盈比例
    "stop_loss": 0.08,       # 止损比例
    "cooldown_days": 1,      # 冷却天数
    "max_position_pct": 0.20,  # 单只上限比例
    "max_positions": 5,      # 最大持仓数
}

# 默认信号版本
DEFAULT_STRATEGY_VERSION = "v1"

# === 运行时配置（进程级，前端选择后更新） ===
# 初始化为 v1 默认值 + 默认交易策略
_active_config: dict = {
    **SIGNAL_VERSIONS["v1"],
    **DEFAULT_TRADING_PARAMS,
}


def get_strategy(version: str) -> dict:
    """按版本号取信号版本定义，找不到抛 ValueError"""
    if version not in SIGNAL_VERSIONS:
        available = list(SIGNAL_VERSIONS.keys())
        raise ValueError(f"未知信号版本: {version!r}，可选: {available}")
    return SIGNAL_VERSIONS[version]


def list_strategies() -> List[dict]:
    """按注册顺序返回所有信号版本（前端下拉渲染用）"""
    return list(SIGNAL_VERSIONS.values())


def get_active_config() -> dict:
    """获取当前活跃配置（信号版本 + 交易策略合并后）

    Returns:
        {
            'id': 'v1', 'name': '每日触发',
            'lookback_days': 7, 'first_break_only': False, 'output_subdir': 'v1',
            'threshold': 30.0, 'take_profit': 0.20, 'stop_loss': 0.08,
            'cooldown_days': 1, 'max_position_pct': 0.20, 'max_positions': 5,
        }
    """
    return dict(_active_config)


def update_active_config(params: dict) -> dict:
    """更新运行时配置（前端选择交易策略后调用）

    Args:
        params: 要更新的字段，如 {'threshold': 40, 'take_profit': 0.15}

    Returns:
        更新后的完整配置
    """
    global _active_config
    _active_config.update(params)
    return get_active_config()


def switch_signal_version(version: str) -> dict:
    """切换信号版本（更新信号相关字段，保留交易策略参数）

    Args:
        version: 'v1' / 'v2'

    Returns:
        更新后的完整配置
    """
    global _active_config
    ver = get_strategy(version)
    # 只更新信号版本字段，保留交易策略字段
    _active_config.update({
        'id': ver['id'],
        'name': ver['name'],
        'description': ver['description'],
        'lookback_days': ver['lookback_days'],
        'first_break_only': ver['first_break_only'],
        'output_subdir': ver['output_subdir'],
    })
    return get_active_config()
