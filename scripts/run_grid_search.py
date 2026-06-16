#!/usr/bin/env python3
"""
信号策略参数网格搜索

用法:
  # 默认参数网格搜索（2025全年，200只自选股）
  python scripts/run_grid_search.py

  # 指定评分数据目录
  python scripts/run_grid_search.py --scores-dir result/backtest/2025_每日_200_信号

  # 导出结果CSV
  python scripts/run_grid_search.py --output result/backtest/2025_每日_200_信号/grid_results.csv
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="信号策略参数网格搜索")
    parser.add_argument("--scores-dir", default="result/backtest/2025_每日_200_信号", help="评分数据目录")
    parser.add_argument("--pool", default="stock_self_selected.csv", help="股票池")
    parser.add_argument("--start", default="", help="开始日期")
    parser.add_argument("--end", default="", help="结束日期")
    parser.add_argument("--output", default="", help="导出CSV路径")
    parser.add_argument("--top", type=int, default=20, help="显示前N个策略")
    args = parser.parse_args()

    from src.backtest.grid_search import (
        load_backtest_data,
        print_top_strategies,
        run_grid_search,
    )

    print("⏳ 加载数据...")
    data = load_backtest_data(args.scores_dir, args.pool)
    if data is None:
        print("❌ 数据加载失败")
        return

    print(f"  评分日期: {len(data['trade_dates'])} 天")
    print(f"  股票数: {len(data['name_map'])} 只")
    print()

    # 参数网格
    param_grid = {
        "buy_threshold": [25, 28, 30, 32, 35],
        "take_profit": [10, 15, 20, 25, 30],
        "stop_loss": [5, 8, 10, 15],
        "max_pos_pct": [20],
        "max_positions": [10],
        "cooldown_days": [0, 1, 3],
    }

    results = run_grid_search(
        data=data,
        param_grid=param_grid,
        start_date=args.start,
        end_date=args.end,
    )

    print_top_strategies(results, top_n=args.top)

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"✅ 结果已导出: {args.output}")


if __name__ == "__main__":
    main()
