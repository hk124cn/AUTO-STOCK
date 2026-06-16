#!/usr/bin/env python3
"""
每日信号计算脚本

从 score_price_history.csv 计算买入信号，输出到 result/signals/

买入信号条件：前7天平均分 >= 30分

用法：
  python scripts/calc_signals.py                # 计算最新日期的信号
  python scripts/calc_signals.py --date 20260611  # 指定日期
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 让直接 `python scripts/calc_signals.py` 也能找到 src 包
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent
SCORE_HISTORY = ROOT_DIR / "result" / "score_price_history.csv"
SIGNALS_BASE_DIR = ROOT_DIR / "result" / "signals"  # signals/{strategy.output_subdir}/

# 策略注册表（v1/v2 在 src/backtest/strategies.py 注册；具体参数见 Strategy 数据类）
from src.backtest.strategies import (
    get_strategy, list_strategies, get_active_config, update_active_config,
    switch_signal_version, DEFAULT_STRATEGY_VERSION, SIGNAL_VERSIONS,
)

# 默认股票池（自选股 200 只）
DEFAULT_POOL = ROOT_DIR / "stock_self_selected.csv"


def load_pool_codes(pool_path: Path = None) -> set:
    """加载股票池，返回 code 集合"""
    p = pool_path or DEFAULT_POOL
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, dtype={'code': str})
        return set(df['code'].astype(str).str.zfill(6))
    except Exception as e:
        print(f"警告: 加载股票池 {p} 失败: {e}")
        return None


def normalize_date_value(val) -> str:
    """将日期值统一为 YYYYMMDD 字符串（处理浮点数如 20160104.0）"""
    if pd.isna(val):
        return ''
    if isinstance(val, (int, np.integer)):
        return str(int(val))
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    s = str(val).strip()
    # 处理 20160104.0 / 2016-01-04
    if s.endswith('.0'):
        s = s[:-2]
    s = s.replace('-', '').replace('/', '')
    return s


def load_score_history() -> pd.DataFrame:
    """加载评分-价格历史表"""
    if not SCORE_HISTORY.exists():
        print(f"错误: {SCORE_HISTORY} 不存在")
        sys.exit(1)

    df = pd.read_csv(SCORE_HISTORY, dtype={'code': str})

    # 日期归一化（修复 2.1）
    df['date'] = df['date'].apply(normalize_date_value)

    # 去重 (修复 2.2)
    df = df.drop_duplicates(subset=['code', 'date'], keep='last')

    df['total_score'] = pd.to_numeric(df['total_score'], errors='coerce')
    df['close_price'] = pd.to_numeric(df['close_price'], errors='coerce')
    if 'finance_score' in df.columns:
        df['finance_score'] = pd.to_numeric(df['finance_score'], errors='coerce')
    else:
        df['finance_score'] = 0.0
    return df


def get_trade_dates(df: pd.DataFrame) -> list:
    return sorted(df['date'].unique())


def calc_moving_avg(df: pd.DataFrame, target_date: str, strategy=None,
                    threshold: float = 30.0,
                    min_periods: int = None, pool_codes: set = None) -> pd.DataFrame:
    """
    计算指定日期的前 N 天平均分

    Args:
        strategy: 信号版本 Strategy 实例（决定 lookback_days/first_break_only）
        threshold: 买入阈值（来自交易策略 DB）
        min_periods: 最少需要的天数，低于此值跳过该股票
        pool_codes: 股票池 code 集合，None 表示全市场
    """
    if strategy is None:
        strategy = get_strategy(DEFAULT_STRATEGY_VERSION)
    lookback = strategy.lookback_days

    if min_periods is None:
        min_periods = lookback  # 默认需要满 lookback 天

    trade_dates = get_trade_dates(df)

    if target_date not in trade_dates:
        valid_dates = [d for d in trade_dates if d <= target_date]
        if not valid_dates:
            print(f"错误: 没有早于 {target_date} 的交易数据")
            return pd.DataFrame()
        target_date = valid_dates[-1]
        print(f"使用最近交易日: {target_date}")

    target_idx = trade_dates.index(target_date)
    if target_idx < min_periods - 1:
        print(f"警告: 数据不足 {min_periods} 天，跳过信号计算")
        return pd.DataFrame()

    window_dates = trade_dates[target_idx - lookback + 1:target_idx + 1]
    window_df = df[df['date'].isin(window_dates)]

    # v2 首次突破需要昨日的窗口
    if strategy.first_break_only and target_idx >= lookback:
        prev_window_dates = trade_dates[target_idx - lookback:target_idx]
        prev_window_df = df[df['date'].isin(prev_window_dates)]
    else:
        prev_window_df = None

    # 股票池过滤
    if pool_codes is not None:
        before_count = window_df['code'].nunique()
        window_df = window_df[window_df['code'].isin(pool_codes)]
        after_count = window_df['code'].nunique()
        print(f"股票池过滤: {before_count} → {after_count} 只")

    result_rows = []
    for code, group in window_df.groupby('code'):
        scores = group['total_score'].dropna().values
        if len(scores) < min_periods:
            continue

        # v2: 首次突破过滤——昨日 7 日均分 < 阈值且今日 ≥ 阈值
        if strategy.first_break_only:
            if prev_window_df is None:
                continue  # 没有昨日数据 → 不视作突破
            prev_group = prev_window_df[prev_window_df['code'] == code]
            if prev_group.empty:
                continue
            prev_scores = prev_group['total_score'].dropna().values
            if len(prev_scores) < min_periods:
                continue
            prev_avg = float(np.mean(prev_scores))
        else:
            prev_avg = None

        target_row = group[group['date'] == target_date]
        if target_row.empty:
            continue

        avg_score = np.mean(scores)
        current_score = target_row.iloc[0]['total_score']
        close_price = target_row.iloc[0]['close_price']
        name = target_row.iloc[0]['name']
        finance_score = target_row.iloc[0].get('finance_score', 0)
        if pd.isna(finance_score):
            finance_score = 0

        result_rows.append({
            'date': target_date,  # 新增 date 列（修复前端显示 -）
            'code': code,
            'name': name,
            'close_price': close_price,
            'current_score': round(current_score, 2) if not np.isnan(current_score) else 0,
            'avg7_score': round(avg_score, 2),
            'prev_avg7_score': round(prev_avg, 2) if prev_avg is not None else None,
            'finance_score': round(float(finance_score), 2),
            'signal': (
                'BUY' if (avg_score >= threshold and
                          (prev_avg is None or prev_avg < threshold))
                else ''
            ),
        })

    result_df = pd.DataFrame(result_rows)
    if not result_df.empty:
        sort_col = 'finance_score' if strategy and strategy.first_break_only else 'avg7_score'
        result_df = result_df.sort_values(sort_col, ascending=False)

    return result_df


def apply_cooldown(signals_df: pd.DataFrame, target_date: str,
                    signals_dir: Path, cooldown_days: int = 1) -> pd.DataFrame:
    """
    应用冷却期 - 同一股票距离上次卖出小于 cooldown_days 则跳过买入。

    冷却期按卖出日计算（从 portfolio.db trades 表读取 SELL 记录），
    同时也检查历史信号中的 BUY 日期作为兜底。

    Args:
        cooldown_days: 冷却天数（来自交易策略 DB）
    """

    if signals_df.empty or cooldown_days <= 0:
        return signals_df

    target_dt = datetime.strptime(target_date, '%Y%m%d')
    cutoff = (target_dt - timedelta(days=cooldown_days + 5)).strftime('%Y%m%d')

    # 收集需要冷却的股票：最后卖出日期
    last_sell = {}  # code -> last sell date

    # 来源1：从 portfolio.db trades 表读取 SELL 记录
    try:
        from src.portfolio.database import PortfolioDB
        db = PortfolioDB()
        sim_account = db.get_account_by_mode('SIM')
        if sim_account:
            trades = db.get_trades(sim_account['id'], limit=500)
            for t in trades:
                if t.get('type') == 'SELL':
                    code = str(t.get('code', ''))
                    trade_date = str(t.get('trade_date', '')).replace('-', '')[:8]
                    if code and trade_date >= cutoff:
                        if code not in last_sell or trade_date > last_sell[code]:
                            last_sell[code] = trade_date
    except Exception:
        pass  # 数据库不可用，跳过

    # 来源2：从历史信号文件读取 BUY 日期（兜底）
    if signals_dir.exists():
        for f in signals_dir.glob('signals_*.csv'):
            if f.stem in ('signals_latest', 'signals_latest.csv.tmp'):
                continue
            date_str = f.stem.replace('signals_', '')
            if date_str == target_date or date_str < cutoff:
                continue
            try:
                old = pd.read_csv(f, dtype={'code': str})
                for _, row in old.iterrows():
                    if row.get('signal') == 'BUY':
                        code = str(row.get('code', ''))
                        if code and (code not in last_sell or date_str > last_sell[code]):
                            last_sell[code] = date_str
            except Exception:
                continue

    if not last_sell:
        return signals_df

    def is_in_cooldown(code):
        if code not in last_sell:
            return False
        last_date = datetime.strptime(last_sell[code], '%Y%m%d')
        return (target_dt - last_date).days < cooldown_days

    before_count = len(signals_df)
    signals_df = signals_df[~signals_df['code'].apply(is_in_cooldown)]
    after_count = len(signals_df)
    if before_count != after_count:
        print(f"  冷却期过滤: {before_count} → {after_count} (过滤 {before_count - after_count} 只)")

    return signals_df


def save_signals(signals_df: pd.DataFrame, target_date: str, strategy=None):
    """保存信号到文件（按 strategy.output_subdir 分目录）"""
    if strategy is None:
        strategy = get_strategy(DEFAULT_STRATEGY_VERSION)

    signals_dir = SIGNALS_BASE_DIR / strategy.output_subdir
    signals_dir.mkdir(parents=True, exist_ok=True)

    output_file = signals_dir / f"signals_{target_date}.csv"
    signals_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"信号已保存: {output_file}")

    # 修复 2.3：使用原子替换而非软链接
    latest_file = signals_dir / "signals_latest.csv"
    tmp_file = signals_dir / "signals_latest.csv.tmp"
    signals_df.to_csv(tmp_file, index=False, encoding='utf-8-sig')
    os.replace(tmp_file, latest_file)
    print(f"最新信号: {latest_file}")

    return output_file


def load_kline(code: str) -> Optional[pd.DataFrame]:
    """加载个股 K 线（开盘/最高/最低/收盘/成交额）"""
    kline_dir = ROOT_DIR / "data" / "price"
    f = kline_dir / f"{code}.csv"
    if not f.exists():
        return None
    try:
        return pd.read_csv(f, dtype={'日期': str})
    except Exception:
        return None


def check_kline_stop(code: str, cost: float, buy_date: str,
                     take_profit: float, stop_loss: float,
                     end_date: str = None) -> dict:
    """
    扫描 K 线检查是否触达止盈/止损（从 sim_trader 迁移）。

    逻辑：遍历 [买入日, end_date]，每天先检查 high ≥ 止盈价，再检查 low ≤ 止损价。
    卖出价 = 目标价（不取最高/最低）。

    Returns:
        {'triggered': bool, 'type': 'take_profit'|'stop_loss'|'both'|None,
         'trigger_date': str, 'sell_price': float}
    """
    from datetime import datetime as _dt
    target_tp = cost * (1 + take_profit)
    target_sl = cost * (1 - stop_loss)

    df = load_kline(code)
    if df is None or df.empty:
        return {'triggered': False, 'type': None, 'sell_price': 0, 'trigger_date': ''}

    df['_date'] = df['日期'].astype(str).str.replace('-', '').str.replace('.0', '', regex=False)
    end_date = end_date or _dt.now().strftime('%Y%m%d')
    df = df[(df['_date'] >= buy_date) & (df['_date'] <= end_date)]
    if df.empty:
        return {'triggered': False, 'type': None, 'sell_price': 0, 'trigger_date': ''}

    for _, row in df.iterrows():
        high = pd.to_numeric(row.get('最高'), errors='coerce')
        low = pd.to_numeric(row.get('最低'), errors='coerce')
        if pd.isna(high) or pd.isna(low):
            continue

        tp_hit = high >= target_tp
        sl_hit = low <= target_sl

        if tp_hit and sl_hit:
            return {'triggered': True, 'type': 'both', 'trigger_date': str(row['_date']),
                    'sell_price': target_sl}  # 同日双触达，保守取止损
        if tp_hit:
            return {'triggered': True, 'type': 'take_profit', 'trigger_date': str(row['_date']),
                    'sell_price': target_tp}
        if sl_hit:
            return {'triggered': True, 'type': 'stop_loss', 'trigger_date': str(row['_date']),
                    'sell_price': target_sl}

    return {'triggered': False, 'type': None, 'sell_price': 0, 'trigger_date': ''}


def generate_sell_signals(df: pd.DataFrame, target_date: str) -> pd.DataFrame:
    """
    检查持仓数据库，对触达止盈/止损的持仓生成 SELL 信号。

    读取 portfolio.db 的 SIM 账户持仓，用 K 线最高/最低价判断止盈止损。
    用 K 线扫描（与 sim_trader 一致），而非仅收盘价。
    """
    try:
        from src.portfolio.database import PortfolioDB
        db = PortfolioDB()
    except Exception:
        return pd.DataFrame()

    # 获取 SIM 账户
    sim_account = db.get_account_by_mode('SIM')
    if not sim_account:
        return pd.DataFrame()

    account_id = sim_account['id']

    # 获取策略参数
    strategy_info = db.get_strategy(sim_account.get('strategy_id')) if sim_account.get('strategy_id') else db.get_default_strategy()
    if not strategy_info:
        return pd.DataFrame()

    take_profit = strategy_info.get('take_profit', 0.20)
    stop_loss = strategy_info.get('stop_loss', 0.08)

    # 获取持仓
    positions = db.get_positions(account_id)
    if not positions:
        return pd.DataFrame()

    sell_rows = []
    for pos in positions:
        code = pos.get('code', '')
        if not code:
            continue

        buy_price = pos.get('avg_cost', 0)
        if buy_price <= 0:
            buy_price = pos.get('buy_price', 0)
        if buy_price <= 0:
            continue

        buy_date = str(pos.get('buy_date', '')).replace('-', '')
        if not buy_date:
            continue

        # 用 K 线扫描止盈止损
        check = check_kline_stop(code, buy_price, buy_date,
                                 take_profit, stop_loss, end_date=target_date)

        if not check['triggered']:
            continue

        # 获取收盘价用于展示
        code_data = df[(df['code'] == code) & (df['date'] == target_date)]
        close_price = float(code_data.iloc[0]['close_price']) if not code_data.empty else 0

        # 构建卖出原因
        tp_pct = take_profit * 100
        sl_pct = stop_loss * 100
        if check['type'] == 'take_profit':
            reason = f"止盈触达 {check['trigger_date']}（+{tp_pct:.0f}%）"
        elif check['type'] == 'stop_loss':
            reason = f"止损触达 {check['trigger_date']}（-{sl_pct:.0f}%）"
        else:  # both
            reason = f"同日双触达（保守止损）{check['trigger_date']}"

        sell_rows.append({
            'date': target_date,
            'code': code,
            'name': pos.get('name', ''),
            'close_price': close_price,
            'current_score': '',
            'avg7_score': '',
            'prev_avg7_score': None,
            'finance_score': '',
            'signal': 'SELL',
            'sell_reason': reason,
            'sell_price': check['sell_price'],
            'sell_type': check['type'],
        })

    if not sell_rows:
        return pd.DataFrame()

    return pd.DataFrame(sell_rows)


def main():
    parser = argparse.ArgumentParser(description='计算每日买入信号')
    parser.add_argument('--date', type=str, default=None,
                        help='目标日期 (YYYYMMDD)，默认为最新交易日')
    parser.add_argument('--strategy-version', type=str, default=DEFAULT_STRATEGY_VERSION,
                        choices=list(SIGNAL_VERSIONS.keys()),
                        help=f'信号版本（默认 {DEFAULT_STRATEGY_VERSION}，可选: {list(SIGNAL_VERSIONS.keys())}）')
    parser.add_argument('--no-cooldown', action='store_true', help='禁用冷却期过滤')
    parser.add_argument('--pool', type=str, default=str(DEFAULT_POOL),
                        help=f'股票池 CSV 文件路径（默认 {DEFAULT_POOL.name}）')
    parser.add_argument('--all-stocks', action='store_true',
                        help='使用全市场股票（忽略 --pool）')
    args = parser.parse_args()

    # 切换信号版本（更新配置层）
    switch_signal_version(args.strategy_version)
    config = get_active_config()

    print("加载评分历史数据...")
    df = load_score_history()
    print(f"共 {len(df)} 条记录，{df['code'].nunique()} 只股票")

    # 加载股票池
    pool_codes = None
    if not args.all_stocks:
        pool_path = Path(args.pool) if args.pool else DEFAULT_POOL
        pool_codes = load_pool_codes(pool_path)
        if pool_codes:
            print(f"股票池: {pool_path.name}（{len(pool_codes)} 只自选股）")
        else:
            print(f"⚠️  股票池 {pool_path} 不存在，使用全市场")

    if args.date:
        target_date = args.date.replace('-', '').replace('/', '')
    else:
        target_date = df['date'].max()

    print(f"\n信号版本: {config['id']} - {config['name']}")
    print(f"  {config['description']}")
    print(f"交易策略: 阈值≥{config['threshold']}, 止盈{config['take_profit']*100:.0f}%, "
          f"止损{config['stop_loss']*100:.0f}%, 冷却{config['cooldown_days']}天")
    print(f"计算日期: {target_date}")
    print(f"输出目录: result/signals/{config['output_subdir']}/")

    # 构建信号版本对象（兼容 calc_moving_avg 的 strategy 参数）
    class _Strategy:
        pass
    strategy = _Strategy()
    strategy.lookback_days = config['lookback_days']
    strategy.first_break_only = config['first_break_only']
    strategy.output_subdir = config['output_subdir']

    signals_df = calc_moving_avg(df, target_date, strategy=strategy,
                                 threshold=config['threshold'], pool_codes=pool_codes)

    if signals_df.empty:
        print("没有找到有效的信号数据")
        return

    # 强制让 CSV 内 date 字段 == 文件名日期（避免 calc_moving_avg 兜底到旧日期时文件名与内容打架）
    signals_df['date'] = target_date

    if not args.no_cooldown:
        signals_dir = SIGNALS_BASE_DIR / config['output_subdir']
        before = len(signals_df)
        signals_df = apply_cooldown(signals_df, target_date, signals_dir,
                                    cooldown_days=config['cooldown_days'])
        after = len(signals_df)
        if before != after:
            print(f"冷却过滤: {before} → {after} (过滤 {before - after} 只)")

    # === 生成 SELL 信号（检查持仓的止盈/止损）===
    sell_signals = generate_sell_signals(df, target_date)
    if not sell_signals.empty:
        # 合并 BUY 和 SELL 信号（SELL 行覆盖同 code 的 BUY 行）
        signals_df = pd.concat([signals_df, sell_signals], ignore_index=True)
        signals_df = signals_df.drop_duplicates(subset=['code'], keep='last')

    buy_signals = signals_df[signals_df['signal'] == 'BUY']
    sell_signals = signals_df[signals_df['signal'] == 'SELL']
    print(f"\n=== 信号统计 ===")
    print(f"总股票数: {len(signals_df)}")
    print(f"买入信号: {len(buy_signals)} 只")
    print(f"卖出信号: {len(sell_signals)} 只")

    if not buy_signals.empty:
        print(f"\n=== 买入信号列表 (前20) ===")
        for i, row in buy_signals.head(20).iterrows():
            print(f"  {row['code']} {row['name']:8s}  "
                  f"当前:{row['current_score']:5.1f}  "
                  f"7日均:{row['avg7_score']:5.1f}  "
                  f"价格:{row['close_price']:.2f}")

    if not sell_signals.empty:
        print(f"\n=== 卖出信号 ===")
        for i, row in sell_signals.iterrows():
            print(f"  {row['code']} {row['name']:8s}  "
                  f"价格:{row['close_price']:.2f}  "
                  f"原因:{row.get('sell_reason', '')}")

    save_signals(signals_df, target_date, strategy=strategy)

    print(f"\n完成! {len(buy_signals)} 只买入 + {len(sell_signals)} 只卖出")


if __name__ == '__main__':
    main()
