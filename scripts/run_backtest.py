#!/usr/bin/env python3
"""
回测命令行入口

用法:
  # 使用已有评分回测（2026年9因子数据）
  python scripts/run_backtest.py --start 20260512 --end 20260608

  # 实时计算因子回测（2025全年）
  python scripts/run_backtest.py --live --start 20250102 --end 20251231 \
    --output result/backtest/2025_5日_1385_top

  # 单因子分析
  python scripts/run_backtest.py --mode factor --live --start 20250102 --end 20251231

  # 生成HTML报告和交易明细
  python scripts/run_backtest.py --live --start 20250102 --end 20251231 \
    --output result/backtest/2025_5日_1385_top --html --trades
"""

import argparse
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_backtest(args):
    """执行标准回测"""
    from src.backtest.engine import BacktestConfig, BacktestEngine
    from src.backtest.report import (
        export_trades_csv,
        generate_html_report,
        print_report,
    )

    # 确定模式
    bt_mode = "live" if args.live else "scored"

    # 输出目录
    output_dir = args.output or ""

    config = BacktestConfig(
        mode=bt_mode,
        start_date=args.start or "",
        end_date=args.end or "",
        stock_pool=args.pool or "",
        top_n=args.top_n,
        rebalance_days=args.hold_days,
        hold_days=args.hold_days,
        cost_rate=args.cost / 100,
        output_dir=output_dir,
    )

    engine = BacktestEngine(config)
    result = engine.run()

    # 终端报告
    print_report(result)

    # 确定输出路径前缀
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        prefix = output_dir
    else:
        prefix = "result"

    # 导出交易明细
    if args.trades:
        trades_path = os.path.join(prefix, "backtest_trades.csv")
        export_trades_csv(result, trades_path)

    # HTML报告
    if args.html:
        html_path = os.path.join(prefix, "backtest_report.html")
        generate_html_report(result, output_path=html_path)

    return result


def run_factor_analysis(args):
    """执行单因子分析"""
    from src.backtest.engine import run_factor_analysis

    analysis = run_factor_analysis(
        start_date=args.start or "",
        end_date=args.end or "",
        stock_pool=args.pool or "",
        hold_days=args.hold_days,
    )

    if not analysis:
        print("❌ 因子分析无结果（数据不足）")
        return

    print()
    print("=" * 70)
    print("                    🔍 单因子分析报告")
    print("=" * 70)
    print(f"  持仓天数: {args.hold_days}")
    print()

    # 按 IC_IR 排序
    sorted_factors = sorted(
        analysis.items(), key=lambda x: abs(x[1]['ic_ir']), reverse=True
    )

    print(f"  {'因子':<16} {'IC均值':>8} {'IC_IR':>8} {'单调性':>8} {'有效?':>6} {'期数':>6}")
    print(f"  {'─'*16} {'─'*8} {'─'*8} {'─'*8} {'─'*6} {'─'*6}")

    for name, stats in sorted_factors:
        ic_ir = stats['ic_ir']
        is_effective = "✅" if abs(ic_ir) > 0.5 else ("⚠️" if abs(ic_ir) > 0.3 else "❌")
        print(
            f"  {name:<16} {stats['ic_mean']:>8.4f} {ic_ir:>8.4f} "
            f"{stats['monotonicity']:>8.4f} {is_effective:>6} {stats['periods']:>6d}"
        )

        # 分位收益
        if stats['quintile_returns']:
            q_str = "    Q1~Q5: " + " → ".join(
                f"{r*100:.2f}%" for r in stats['quintile_returns']
            )
            print(q_str)

    print()

    # 判断标准说明
    print("  📌 判断标准:")
    print("     IC_IR > 0.5: ✅ 有效因子")
    print("     IC_IR > 0.3: ⚠️ 有一定预测力")
    print("     IC_IR ≤ 0.3: ❌ 预测力不足")
    print("     单调性 > 0.6: 分位收益呈单调递增")
    print()


def run_interactive():
    """交互模式"""
    print()
    print("=" * 50)
    print("        📈 回测系统 - 交互模式")
    print("=" * 50)
    print()
    print("选择模式:")
    print("  1. 标准回测（评分排序做多）")
    print("  2. 单因子分析")
    print()

    mode = input("请输入编号 (1/2): ").strip()

    start = input("开始日期 (YYYYMMDD, 回车=自动): ").strip()
    end = input("结束日期 (YYYYMMDD, 回车=自动): ").strip()
    top_n = input("Top-N 选股数量 (回车=20): ").strip()
    hold_days = input("持仓天数 (回车=5): ").strip()
    pool = input("股票池CSV路径 (回车=全部): ").strip()
    html = input("是否生成HTML报告? (y/N): ").strip().lower()
    live = input("是否实时计算因子? (y/N, 选y可回测任意历史): ").strip().lower()
    output = input("输出目录 (回车=默认): ").strip()

    # 构建参数对象
    class Args:
        pass

    args = Args()
    args.start = start
    args.end = end
    args.top_n = int(top_n) if top_n else 20
    args.hold_days = int(hold_days) if hold_days else 5
    args.pool = pool
    args.cost = 0.15
    args.html = html == 'y'
    args.trades = True
    args.live = live == 'y'
    args.output = output

    if mode == "2":
        run_factor_analysis(args)
    else:
        run_backtest(args)


def main():
    parser = argparse.ArgumentParser(
        description="回测系统 — 验证因子有效性",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用已有评分回测（2026年9因子数据）
  python scripts/run_backtest.py --start 20260512 --end 20260608

  # 实时计算因子回测（2025全年，输出到指定目录）
  python scripts/run_backtest.py --live --start 20250102 --end 20251231 \\
    --output result/backtest/2025_5日_1385_top --html --trades

  # 单因子分析
  python scripts/run_backtest.py --mode factor --live --start 20250102 --end 20251231

  # 交互模式
  python scripts/run_backtest.py --interactive
        """,
    )

    parser.add_argument("--mode", choices=["backtest", "factor"], default="backtest",
                        help="运行模式: backtest=标准回测, factor=因子分析")
    parser.add_argument("--live", action="store_true",
                        help="实时计算因子模式（可回测任意历史时间段）")
    parser.add_argument("--start", default="", help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default="", help="结束日期 YYYYMMDD")
    parser.add_argument("--top-n", type=int, default=20, help="选股数量 (默认20)")
    parser.add_argument("--hold-days", type=int, default=5, help="持仓天数 (默认5)")
    parser.add_argument("--pool", default="", help="股票池CSV路径")
    parser.add_argument("--cost", type=float, default=0.15, help="交易成本百分比 (默认0.15)")
    parser.add_argument("--output", default="", help="输出目录 (默认=result/)")
    parser.add_argument("--html", action="store_true", help="生成HTML报告")
    parser.add_argument("--trades", action="store_true", help="导出交易明细CSV")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")

    args = parser.parse_args()

    if args.interactive:
        run_interactive()
    elif args.mode == "factor":
        run_factor_analysis(args)
    else:
        run_backtest(args)


if __name__ == "__main__":
    main()
