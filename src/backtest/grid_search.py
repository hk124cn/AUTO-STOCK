"""
参数网格搜索 — 批量测试信号策略参数组合

对多种买入阈值、止盈、止损、仓位、冷却期组合进行回测，
按夏普比率排序，输出最优策略。
"""

import itertools
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from src.backtest.data import load_price_df, load_stock_pool
from src.backtest.signal_engine import SignalConfig, SignalEngine, SignalResult


def load_backtest_data(scores_dir: str, stock_pool: str, year: int = None):
    """预加载所有评分和价格数据

    Args:
        scores_dir: 评分数据目录
        stock_pool: 股票池文件路径
        year: 年份（可选，用于只加载当年价格数据，提高效率）
    """
    pool_df = load_stock_pool(stock_pool)
    if pool_df.empty:
        return None
    codes = pool_df['code'].astype(str).str.zfill(6).tolist()
    name_map = dict(zip(pool_df['code'], pool_df['name']))
    watch_codes = set(codes)

    # 加载评分
    score_files = sorted(Path(scores_dir).glob("scores_*.csv"))
    all_scores = {}
    for f in score_files:
        date_str = f.stem.replace("scores_", "")
        df = pd.read_csv(f, dtype={"code": str})
        df["code"] = df["code"].astype(str).str.zfill(6)
        df = df[df["code"].isin(watch_codes)]
        all_scores[date_str] = df

    trade_dates = sorted(all_scores.keys())

    # 加载价格（预构建 {code: {date_str: price}} 字典，避免重复查DataFrame）
    # 如果指定了年份，只加载当年数据，提高效率
    price_dict = {}
    for idx, code in enumerate(codes):
        if (idx + 1) % 50 == 0:
            print(f"  加载价格数据: {idx+1}/{len(codes)}")
        pdf = load_price_df(code)
        if pdf is not None and not pdf.empty:
            pdf_copy = pdf.copy()
            # 如果指定了年份，只保留当年数据
            if year:
                year_str = str(year)
                pdf_copy = pdf_copy[pdf_copy['日期'].dt.strftime('%Y%m%d').str.startswith(year_str)]
            if not pdf_copy.empty:
                pdf_copy['date_str'] = pdf_copy['日期'].dt.strftime('%Y%m%d')
                price_dict[code] = dict(zip(pdf_copy['date_str'], pdf_copy['收盘'].astype(float)))
    price_cache = price_dict  # 现在是 dict of dict

    return {
        "all_scores": all_scores,
        "trade_dates": trade_dates,
        "price_cache": price_cache,
        "name_map": name_map,
    }


def run_grid_search(
    data: dict,
    param_grid: dict = None,
    start_date: str = "",
    end_date: str = "",
    top_n: int = 10,
) -> pd.DataFrame:
    """运行网格搜索

    Args:
        data: load_backtest_data() 的返回值
        param_grid: 参数网格，None则用默认
        start_date: 回测开始日期
        end_date: 回测结束日期
        top_n: 返回前N个最优策略

    Returns:
        DataFrame: 参数组合及其回测指标，按夏普排序
    """
    if param_grid is None:
        param_grid = {
            "buy_threshold": [30],  # 固定30分启动信号
            "take_profit": [5, 10, 15, 20, 30],
            "stop_loss": [3, 5, 8, 10],
            "max_pos_pct": [20],
            "max_positions": [10],
            "cooldown_days": [0, 1, 3],
        }

    # 生成所有组合
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = list(itertools.product(*values))
    total = len(combos)
    print(f"📊 网格搜索: {total} 种参数组合")

    results = []
    t0 = time.time()

    for idx, combo in enumerate(combos):
        params = dict(zip(keys, combo))

        config = SignalConfig(
            scores_dir="",
            stock_pool="",
            start_date=start_date,
            end_date=end_date,
            buy_threshold=params["buy_threshold"],
            take_profit=params["take_profit"],
            stop_loss=params["stop_loss"],
            max_pos_pct=params.get("max_pos_pct", 20),
            max_positions=params.get("max_positions", 10),
            cooldown_days=params.get("cooldown_days", 1),
            sort_by_finance=params.get("sort_by_finance", False),
            # v2 保守策略参数（缺省即保持 v1 行为）
            first_break_only=params.get("first_break_only", False),
            max_pos_pct_basis=params.get("max_pos_pct_basis", "total_assets"),
            build_days=params.get("build_days", 1),
        )

        engine = SignalEngine(config)
        result = engine.run(
            all_scores=data["all_scores"],
            trade_dates=data["trade_dates"],
            price_cache=data["price_cache"],
            name_map=data["name_map"],
        )

        row = {**params}
        row["total_return"] = round(result.total_return, 2)
        row["annual_return"] = round(result.annual_return, 2)
        row["sharpe"] = round(result.sharpe_ratio, 3)
        row["max_dd"] = round(result.max_drawdown, 2)
        row["win_rate"] = round(result.win_rate, 1)
        row["trades"] = result.total_trades
        row["avg_hold"] = round(result.avg_hold_days, 1)
        row["avg_ret"] = round(result.avg_return, 2)
        results.append(row)

        if (idx + 1) % 50 == 0 or idx + 1 == total:
            elapsed = time.time() - t0
            eta = elapsed / (idx + 1) * (total - idx - 1)
            print(f"  [{idx+1}/{total}] 已完成, 耗时{elapsed:.0f}s, 预计剩余{eta:.0f}s")

    df = pd.DataFrame(results)
    df = df.sort_values("sharpe", ascending=False).reset_index(drop=True)
    return df


def print_top_strategies(df: pd.DataFrame, top_n: int = 10):
    """打印最优策略"""
    print()
    print("=" * 100)
    print("                        🏆 参数搜索结果（按夏普比率排序）")
    print("=" * 100)

    cols = ["buy_threshold", "take_profit", "stop_loss", "cooldown_days",
            "total_return", "annual_return", "sharpe", "max_dd",
            "win_rate", "trades", "avg_hold", "avg_ret"]

    print(f"  {'排名':>4} {'买入≥':>6} {'止盈%':>6} {'止损%':>6} {'冷却':>4} "
          f"{'总收益%':>8} {'年化%':>8} {'夏普':>6} {'回撤%':>8} "
          f"{'胜率%':>6} {'笔数':>5} {'均持仓':>6} {'均收益%':>8}")
    print("  " + "-" * 96)

    for i, row in df.head(top_n).iterrows():
        print(f"  {i+1:>4} {row['buy_threshold']:>6.0f} {row['take_profit']:>6.0f} "
              f"{row['stop_loss']:>6.0f} {row['cooldown_days']:>4.0f} "
              f"{row['total_return']:>+8.2f} {row['annual_return']:>+8.2f} "
              f"{row['sharpe']:>6.2f} {row['max_dd']:>8.2f} "
              f"{row['win_rate']:>6.1f} {row['trades']:>5.0f} "
              f"{row['avg_hold']:>6.1f} {row['avg_ret']:>+8.2f}")

    print()
