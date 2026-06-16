#!/usr/bin/env python3
"""
信号策略回测入口

用法:
  # 2025年自选股信号策略（百分位阈值）
  python scripts/run_signal.py --start 20250102 --end 20251231 \
    --pool stock_self_selected.csv --buy-pctile 90 --sell-pctile 50

  # 指定输出目录
  python scripts/run_signal.py --start 20250102 --end 20251231 \
    --pool stock_self_selected.csv --buy-pctile 90 --sell-pctile 50 \
    --output result/backtest/2025_每日_200_信号
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(
        description="信号策略回测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/run_signal.py --start 20250102 --end 20251231 \\
    --pool stock_self_selected.csv --buy-pctile 90 --sell-pctile 50 \\
    --output result/backtest/2025_每日_200_信号
        """,
    )
    parser.add_argument("--start", default="", help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default="", help="结束日期 YYYYMMDD")
    parser.add_argument("--pool", default="stock_self_selected.csv", help="自选股CSV")
    parser.add_argument("--scores-dir", default="", help="预计算评分目录（空=实时计算）")
    parser.add_argument("--buy-pctile", type=float, default=90, help="买入百分位 (默认90)")
    parser.add_argument("--sell-pctile", type=float, default=50, help="卖出百分位 (默认50)")
    parser.add_argument("--sell-mode", default="pctile", choices=["pctile", "relative"], help="卖出模式: pctile=百分位, relative=相对下降")
    parser.add_argument("--sell-drop", type=float, default=20, help="relative模式: 评分下降%%卖出 (默认20)")
    parser.add_argument("--max-pos", type=int, default=10, help="最大同时持仓 (默认10)")
    parser.add_argument("--hold-days", type=int, default=1, help="最少持仓天数 (默认1)")
    parser.add_argument("--cost", type=float, default=0.15, help="交易成本%% (默认0.15)")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--trades", action="store_true", help="导出交易明细")

    args = parser.parse_args()

    # 如果没有预计算评分目录，先实时计算
    scores_dir = args.scores_dir
    if not scores_dir:
        # 实时计算模式：先为自选股计算所有交易日评分
        print("⚡ 实时计算模式：为自选股计算每日评分...")
        from src.backtest.scorer import HistoricalScorer, precompute_scores
        from src.backtest.data import load_stock_pool

        pool_df = load_stock_pool(args.pool)
        stock_codes = pool_df['code'].tolist() if not pool_df.empty else None

        # 输出到临时目录
        scores_dir = args.output or "result/backtest/_scores_cache"
        if not os.path.exists(scores_dir) or not any(Path(scores_dir).glob("scores_*.csv")):
            precompute_scores(
                start_date=args.start,
                end_date=args.end,
                stock_codes=stock_codes,
                rebalance_days=1,  # 每个交易日
                output_dir=scores_dir,
            )
        else:
            print(f"  使用已有评分缓存: {scores_dir}")

    from src.backtest.signal_engine import (
        SignalConfig,
        SignalEngine,
        export_signal_trades,
        print_signal_report,
    )

    config = SignalConfig(
        scores_dir=scores_dir,
        stock_pool=args.pool,
        start_date=args.start,
        end_date=args.end,
        buy_pctile=args.buy_pctile,
        sell_pctile=args.sell_pctile,
        max_positions=args.max_pos,
        cost_rate=args.cost / 100,
        hold_days=args.hold_days,
        sell_mode=args.sell_mode,
        sell_drop_pct=args.sell_drop,
    )

    engine = SignalEngine(config)
    result = engine.run()

    print_signal_report(result)

    if args.trades:
        output_dir = args.output or "result/backtest"
        trades_path = os.path.join(output_dir, "signal_trades.csv")
        export_signal_trades(result, trades_path)


if __name__ == "__main__":
    from pathlib import Path
    main()
