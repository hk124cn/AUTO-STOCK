#!/usr/bin/env python3
"""
查看启动信号策略回测结果

用法：
  python scripts/view_launch_results.py                # 查看所有年份
  python scripts/view_launch_results.py --year 2022    # 查看指定年份
  python scripts/view_launch_results.py --compare      # 查看对比
"""

import argparse
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd


def load_grid_results(year, sort_by_finance=False):
    """加载网格搜索结果"""
    base_dir = Path(__file__).parent.parent / "result" / "backtest" / str(year)
    if sort_by_finance:
        csv_path = base_dir / f"{year}_每日_200_启动信号" / "grid_results_finance.csv"
    else:
        csv_path = base_dir / f"{year}_每日_200_启动信号" / "grid_results.csv"

    if not csv_path.exists():
        return None

    return pd.read_csv(csv_path)


def print_year_summary(year):
    """打印指定年份的汇总"""
    print(f"\n{'='*70}")
    print(f"        📊 {year}年 启动信号策略回测结果")
    print(f"{'='*70}")

    # 按总评分排序
    df_total = load_grid_results(year, sort_by_finance=False)
    if df_total is not None:
        best = df_total.iloc[0]
        print(f"\n【按总评分排序（动量优先）】")
        print(f"  最优策略: 止盈{best['take_profit']:.0f}% 止损{best['stop_loss']:.0f}% 冷却{best['cooldown_days']:.0f}天")
        print(f"  总收益: {best['total_return']:+.2f}%")
        print(f"  夏普比率: {best['sharpe']:.3f}")
        print(f"  胜率: {best['win_rate']:.1f}%")
        print(f"  交易笔数: {best['trades']:.0f}")

    # 按财报评分排序
    df_finance = load_grid_results(year, sort_by_finance=True)
    if df_finance is not None:
        best = df_finance.iloc[0]
        print(f"\n【按财报评分排序（价值优先）】")
        print(f"  最优策略: 止盈{best['take_profit']:.0f}% 止损{best['stop_loss']:.0f}% 冷却{best['cooldown_days']:.0f}天")
        print(f"  总收益: {best['total_return']:+.2f}%")
        print(f"  夏普比率: {best['sharpe']:.3f}")
        print(f"  胜率: {best['win_rate']:.1f}%")
        print(f"  交易笔数: {best['trades']:.0f}")


def print_compare():
    """打印五年对比"""
    print(f"\n{'='*70}")
    print(f"        📊 启动信号策略五年对比（2022-2026）")
    print(f"{'='*70}")

    years = [2022, 2023, 2024, 2025, 2026]
    markets = ['熊市', '恢复', '牛市', '牛市', '震荡']

    # 按总评分排序
    print(f"\n【按总评分排序（动量优先）】")
    print(f"{'年份':<8}{'市场':<8}{'止盈':<8}{'止损':<8}{'冷却':<8}{'总收益':<12}{'夏普':<8}")
    print("-" * 60)

    total_capital = 100
    for year, market in zip(years, markets):
        df = load_grid_results(year, sort_by_finance=False)
        if df is not None:
            best = df.iloc[0]
            total_capital = total_capital * (1 + best['total_return']/100)
            print(f"{year:<8}{market:<8}{best['take_profit']:.0f}%{'':<4}{best['stop_loss']:.0f}%{'':<4}"
                  f"{best['cooldown_days']:.0f}天{'':<4}{best['total_return']:+.2f}%{'':<4}{best['sharpe']:.3f}")

    print(f"\n  五年累计: {total_capital:.2f}万 (总收益 +{total_capital-100:.2f}%)")

    # 按财报评分排序
    print(f"\n【按财报评分排序（价值优先）】")
    print(f"{'年份':<8}{'市场':<8}{'止盈':<8}{'止损':<8}{'冷却':<8}{'总收益':<12}{'夏普':<8}")
    print("-" * 60)

    total_capital = 100
    for year, market in zip(years, markets):
        df = load_grid_results(year, sort_by_finance=True)
        if df is not None:
            best = df.iloc[0]
            total_capital = total_capital * (1 + best['total_return']/100)
            print(f"{year:<8}{market:<8}{best['take_profit']:.0f}%{'':<4}{best['stop_loss']:.0f}%{'':<4}"
                  f"{best['cooldown_days']:.0f}天{'':<4}{best['total_return']:+.2f}%{'':<4}{best['sharpe']:.3f}")

    print(f"\n  五年累计: {total_capital:.2f}万 (总收益 +{total_capital-100:.2f}%)")


def main():
    parser = argparse.ArgumentParser(description="查看启动信号策略回测结果")
    parser.add_argument("--year", type=int, help="查看指定年份")
    parser.add_argument("--compare", action="store_true", help="查看四年对比")
    args = parser.parse_args()

    if args.compare:
        print_compare()
    elif args.year:
        print_year_summary(args.year)
    else:
        for year in [2022, 2023, 2024, 2025]:
            print_year_summary(year)
        print_compare()


if __name__ == "__main__":
    main()
