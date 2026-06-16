#!/usr/bin/env python3
"""
预计算评分数据 — 生成共通评分数据集

一次性计算指定时间段内所有交易日的全部股票评分，
保存到共享目录，供各种回测策略直接读取。

用法:
  # 预计算2025全年1385只股票的每日评分
  python scripts/precompute_scores.py --start 20250102 --end 20251231 \
    --pool stock_pool.csv --output result/backtest/scores_2025_1385

  # 预计算200只自选股的每日评分（如果已有1385只的评分，可从中筛选，不需要重算）
  python scripts/precompute_scores.py --start 20250102 --end 20251231 \
    --pool stock_self_selected.csv --output result/backtest/scores_2025_200
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="预计算评分数据")
    parser.add_argument("--start", required=True, help="开始日期 YYYYMMDD")
    parser.add_argument("--end", required=True, help="结束日期 YYYYMMDD")
    parser.add_argument("--pool", default="", help="股票池CSV路径")
    parser.add_argument("--output", required=True, help="输出目录")
    args = parser.parse_args()

    from src.backtest.scorer import HistoricalScorer, precompute_scores
    from src.backtest.data import load_stock_pool

    # 加载股票列表
    stock_codes = None
    if args.pool:
        pool_df = load_stock_pool(args.pool)
        if not pool_df.empty:
            stock_codes = pool_df['code'].tolist()
            print(f"📋 股票池: {len(stock_codes)} 只")

    # 预计算（每天的评分）
    scores_df = precompute_scores(
        start_date=args.start,
        end_date=args.end,
        stock_codes=stock_codes,
        rebalance_days=1,  # 每个交易日都算
        output_dir=args.output,
    )

    if not scores_df.empty:
        n_dates = scores_df['date'].nunique()
        n_stocks = scores_df['code'].nunique()
        print(f"\n📊 共通评分数据集已生成:")
        print(f"   目录: {args.output}")
        print(f"   日期数: {n_dates}")
        print(f"   股票数: {n_stocks}")
        print(f"   总记录: {len(scores_df)}")


if __name__ == "__main__":
    main()
