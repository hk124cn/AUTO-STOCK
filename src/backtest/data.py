"""
回测数据层 — Point-in-Time 数据访问

提供回测所需的日期、价格、评分、收益率等数据，
确保所有查询严格遵守时间线，避免前视偏差。
"""

import os
import re
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import pandas as pd
import numpy as np

# 路径配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PRICE_DIR = DATA_DIR / "price"
SCORE_DIR = BASE_DIR / "result" / "daily_score"
HISTORY_FILE = BASE_DIR / "result" / "score_price_history.csv"
CALENDAR_FILE = DATA_DIR / "calendar" / "trade_days.csv"


# ============================================================
# 交易日历
# ============================================================

def load_trade_days() -> pd.DatetimeIndex:
    """加载交易日历，返回 DatetimeIndex"""
    df = pd.read_csv(CALENDAR_FILE)
    col = df.columns[0]  # 通常是 'trade_date'
    return pd.to_datetime(df[col])


def get_trade_days_between(start: str, end: str) -> List[str]:
    """获取两个日期之间的交易日列表（YYYYMMDD 格式）"""
    all_days = load_trade_days()
    start_dt = pd.to_datetime(start, format='%Y%m%d')
    end_dt = pd.to_datetime(end, format='%Y%m%d')
    mask = (all_days >= start_dt) & (all_days <= end_dt)
    return [d.strftime('%Y%m%d') for d in all_days[mask]]


def get_next_trade_day(date: str, offset: int = 1) -> Optional[str]:
    """获取 date 之后第 offset 个交易日"""
    all_days = load_trade_days()
    dt = pd.to_datetime(date, format='%Y%m%d')
    idx = all_days.searchsorted(dt)
    target_idx = idx + offset
    if 0 <= target_idx < len(all_days):
        return all_days[target_idx].strftime('%Y%m%d')
    return None


# ============================================================
# 可用回测日期
# ============================================================

def get_available_score_dates() -> List[str]:
    """从 batch_result 文件名提取已有评分日期，排序返回"""
    pattern = str(SCORE_DIR / "batch_result_*.csv")
    files = glob.glob(pattern)
    dates = []
    for f in files:
        m = re.search(r'batch_result_(\d{8})', f)
        if m:
            dates.append(m.group(1))
    return sorted(dates)


# ============================================================
# 评分数据
# ============================================================

def load_batch_scores(date: str) -> Optional[pd.DataFrame]:
    """加载指定日期的批量评分结果

    Returns:
        DataFrame with columns: code, name, total_score, 各因子分
        code 为 zfill(6) 字符串
    """
    path = SCORE_DIR / f"batch_result_{date}.csv"
    if not path.exists():
        return None

    df = pd.read_csv(path, dtype={'code': str})
    df['code'] = df['code'].astype(str).str.zfill(6)
    return df


def load_all_scores() -> pd.DataFrame:
    """加载所有日期的评分数据，返回大表

    Returns:
        DataFrame: date, code, name, total_score, 各因子分
    """
    dates = get_available_score_dates()
    frames = []
    for d in dates:
        df = load_batch_scores(d)
        if df is not None:
            df['date'] = d
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    return result


# ============================================================
# 价格数据
# ============================================================

def load_price_df(code: str) -> Optional[pd.DataFrame]:
    """加载个股价格数据，按日期排序

    Returns:
        DataFrame: 日期(datetime), 收盘, 成交额, 开盘, 最高, 最低
    """
    code = str(code).zfill(6)
    path = PRICE_DIR / f"{code}.csv"
    if not path.exists():
        return None

    df = pd.read_csv(path)
    if df.empty:
        return None

    df['日期'] = pd.to_datetime(df['日期'].astype(str), format='%Y%m%d')
    df = df.sort_values('日期').reset_index(drop=True)
    return df


def get_close_at_date(code: str, date: str) -> Optional[float]:
    """获取个股在指定日期的收盘价（point-in-time）

    Args:
        code: 股票代码
        date: YYYYMMDD 格式

    Returns:
        收盘价或 None（停牌/无数据）
    """
    df = load_price_df(code)
    if df is None:
        return None

    target = pd.to_datetime(date, format='%Y%m%d')
    row = df[df['日期'] == target]
    if row.empty:
        return None

    price = row.iloc[0]['收盘']
    if pd.isna(price):
        return None
    return float(price)


def get_forward_return(code: str, signal_date: str, hold_days: int,
                        slippage: float = 0.001) -> Optional[float]:
    """计算从信号日的 T+1 开盘买入，持有 hold_days 个交易日后的收益率

    修复前视偏差：
    - 入场价：signal_date 的下一个交易日开盘价（T+1 open）
    - 出场价：T+1+hold_days 的收盘价
    - 滑点：买入加价 / 卖出减价 0.1%

    Args:
        code: 股票代码
        signal_date: 信号日 YYYYMMDD（T 日）
        hold_days: 持有交易日数
        slippage: 滑点率（默认 0.1%）

    Returns:
        收益率（小数）；None 表示数据不足
    """
    df = load_price_df(code)
    if df is None:
        return None

    signal_dt = pd.to_datetime(signal_date, format='%Y%m%d')
    # 找到 signal_date 的位置
    signal_idx = df[df['日期'] == signal_dt].index
    if len(signal_idx) == 0:
        return None

    signal_pos = signal_idx[0]
    entry_pos = signal_pos + 1  # T+1 开盘买入
    exit_pos = entry_pos + hold_days

    if exit_pos >= len(df):
        return None

    entry_price = float(df.iloc[entry_pos]['开盘'])  # T+1 开盘价
    exit_price = float(df.iloc[exit_pos]['收盘'])    # 出场用收盘价

    if pd.isna(entry_price) or pd.isna(exit_price) or entry_price <= 0:
        return None

    # 应用滑点：买入加价、卖出减价
    entry_price *= (1 + slippage)
    exit_price *= (1 - slippage)

    return (exit_price - entry_price) / entry_price


def get_returns_matrix(codes: List[str], signal_date: str, hold_days: int) -> Dict[str, float]:
    """批量计算多只股票从 signal_date 的 T+1 开盘买入的未来收益率

    Returns:
        {code: return_rate} 字典，跳过数据不足的股票
    """
    result = {}
    for code in codes:
        ret = get_forward_return(code, signal_date, hold_days)
        if ret is not None:
            result[code] = ret
    return result


# ============================================================
# 基准收益
# ============================================================

def get_benchmark_return(date: str, hold_days: int, benchmark_codes: List[str] = None) -> Optional[float]:
    """计算基准（等权组合）的收益率

    默认用 stock_pool 中所有股票等权
    """
    if benchmark_codes is None:
        # 用当天有评分的股票作为基准
        scores = load_batch_scores(date)
        if scores is None:
            return None
        benchmark_codes = scores['code'].tolist()

    returns = get_returns_matrix(benchmark_codes, date, hold_days)
    if not returns:
        return None

    return sum(returns.values()) / len(returns)


# ============================================================
# 行业数据（用于行业相对强弱因子回测）
# ============================================================

def get_industry_change_snapshot(sw_code: str, date: str, days: int = 20) -> Optional[float]:
    """获取指定日期的行业涨跌幅（从缓存文件）

    注意：当前只有最新值，无法精确回溯历史。
    对于回测，返回最近可用值。
    """
    industry_dir = DATA_DIR / "industry"
    path = industry_dir / f"change_{sw_code}_{days}d.csv"
    if not path.exists():
        return None

    try:
        df = pd.read_csv(path)
        if df.empty or 'change_pct' not in df.columns:
            return None
        # 取最新值（暂无历史快照）
        return float(df.iloc[-1]['change_pct'])
    except Exception:
        return None


# ============================================================
# 资金流向数据（有日期快照）
# ============================================================

def load_fund_flow(date: str) -> Optional[pd.DataFrame]:
    """加载指定日期的资金流向快照"""
    fund_dir = DATA_DIR / "fund"
    path = fund_dir / f"fund_flow_5day_{date}.csv"
    if not path.exists():
        return None

    df = pd.read_csv(path, dtype={'股票代码': str})
    if '股票代码' in df.columns:
        df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
    return df


def get_fund_flow_for_stock(code: str, date: str) -> Optional[pd.Series]:
    """获取指定日期某只股票的资金流向数据"""
    df = load_fund_flow(date)
    if df is None or '股票代码' not in df.columns:
        return None

    code = str(code).zfill(6)
    match = df[df['股票代码'] == code]
    if match.empty:
        return None
    return match.iloc[0]


# ============================================================
# 价格历史因子计算（point-in-time）
# ============================================================

def get_5day_return_at(code: str, date: str) -> Optional[float]:
    """计算截至 date 的5日收益率"""
    df = load_price_df(code)
    if df is None:
        return None

    target = pd.to_datetime(date, format='%Y%m%d')
    mask = df['日期'] <= target
    recent = df[mask].tail(6)

    if len(recent) < 6:
        return None

    start_price = float(recent.iloc[0]['收盘'])
    end_price = float(recent.iloc[-1]['收盘'])

    if pd.isna(start_price) or pd.isna(end_price) or start_price <= 0:
        return None

    return (end_price / start_price - 1) * 100


def get_daily_change_at(code: str, date: str) -> Optional[float]:
    """计算 date 当日的涨跌幅（百分比）"""
    df = load_price_df(code)
    if df is None:
        return None

    target = pd.to_datetime(date, format='%Y%m%d')
    idx = df[df['日期'] == target].index
    if len(idx) == 0:
        return None

    pos = idx[0]
    if pos < 1:
        return None

    today_close = float(df.iloc[pos]['收盘'])
    prev_close = float(df.iloc[pos - 1]['收盘'])

    if pd.isna(today_close) or pd.isna(prev_close) or prev_close <= 0:
        return None

    return (today_close - prev_close) / prev_close * 100


def get_ytd_return_at(code: str, date: str) -> Optional[float]:
    """计算截至 date 的年初至今收益率"""
    df = load_price_df(code)
    if df is None:
        return None

    target = pd.to_datetime(date, format='%Y%m%d')
    year_start = pd.Timestamp(year=target.year, month=1, day=1)

    before = df[(df['日期'] >= year_start) & (df['日期'] <= target)]
    if before.empty:
        return None

    year_end_prev = df[df['日期'] < year_start]
    if year_end_prev.empty:
        return None

    start_price = float(year_end_prev.iloc[-1]['收盘'])
    end_price = float(before.iloc[-1]['收盘'])

    if pd.isna(start_price) or pd.isna(end_price) or start_price <= 0:
        return None

    return (end_price / start_price) * 100


def get_20day_return_at(code: str, date: str) -> Optional[float]:
    """计算截至 date 的20日收益率"""
    df = load_price_df(code)
    if df is None:
        return None

    target = pd.to_datetime(date, format='%Y%m%d')
    mask = df['日期'] <= target
    recent = df[mask].tail(21)

    if len(recent) < 2:
        return None

    start_price = float(recent.iloc[0]['收盘'])
    end_price = float(recent.iloc[-1]['收盘'])

    if pd.isna(start_price) or pd.isna(end_price) or start_price <= 0:
        return None

    return (end_price / start_price - 1) * 100


# ============================================================
# 股票池
# ============================================================

def load_stock_pool(pool_file: str = "stock_pool.csv") -> pd.DataFrame:
    """加载股票池"""
    path = BASE_DIR / pool_file
    if not path.exists():
        print(f"股票池文件不存在: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path, dtype={'code': str})
    df['code'] = df['code'].astype(str).str.zfill(6)
    return df
