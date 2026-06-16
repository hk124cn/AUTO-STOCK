#!/usr/bin/env python3
"""
启动信号回测脚本
用30分作为启动信号（前7天平均分），测试不同止盈/止损/冷却期组合

用法：
  python scripts/run_launch_backtest.py --year 2022
  python scripts/run_launch_backtest.py --year 2023 2024 2025
"""

import argparse
import os
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backtest.grid_search import load_backtest_data, run_grid_search, print_top_strategies
from src.backtest.signal_engine import SignalConfig, SignalEngine


def export_trades(result, output_path):
    """导出交易明细"""
    trades = result.trades
    if not trades:
        print("  没有交易记录")
        return

    rows = []
    for t in trades:
        rows.append({
            "股票代码": t.code,
            "股票名称": t.name,
            "买入日期": t.buy_date,
            "卖出日期": t.sell_date,
            "买入评分": round(t.buy_score, 2),
            "卖出评分": round(t.sell_score, 2),
            "买入价格": round(t.buy_price, 2),
            "卖出价格": round(t.sell_price, 2),
            "持有天数": t.hold_days,
            "收益率": round(t.return_rate, 2),
            "净收益率": round(t.net_return, 2),
            "卖出原因": t.reason,
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  交易明细已保存: {output_path}")
    print(f"  总交易笔数: {len(rows)}")


def main():
    parser = argparse.ArgumentParser(description="启动信号回测（30分阈值）")
    parser.add_argument("--year", type=int, nargs="+", required=True, help="回测年份")
    parser.add_argument("--pool", default="stock_self_selected.csv", help="股票池文件")
    args = parser.parse_args()

    for year in args.year:
        print()
        print("=" * 70)
        print(f"        📊 {year}年 启动信号回测（前7天平均分 ≥ 30分）")
        print("=" * 70)

        # 评分数据目录
        base_dir = Path(__file__).parent.parent / "result" / "backtest" / str(year)
        possible_dirs = [
            base_dir / f"{year}_每日_5534_score",
            base_dir / f"{year}_每日_200_score",
            base_dir / f"{year}_1385_score",
        ]
        scores_dir = None
        for d in possible_dirs:
            if d.exists():
                scores_dir = d
                break

        if scores_dir is None:
            print(f"❌ 找不到 {year} 年评分数据目录")
            continue

        print(f"📂 评分目录: {scores_dir.name}")
        print(f"📋 股票池: {args.pool}")

        # 加载数据
        print("⏳ 加载数据...")
        data = load_backtest_data(str(scores_dir), args.pool, year=year)
        if data is None:
            print("❌ 数据加载失败")
            continue

        print(f"  评分天数: {len(data['trade_dates'])}")
        print(f"  股票数量: {len(data['name_map'])}")

        # 参数网格：固定 buy_threshold=30，按财报评分排序
        param_grid = {
            "buy_threshold": [30],
            "take_profit": [5, 10, 15, 20, 30],
            "stop_loss": [3, 5, 8, 10],
            "max_pos_pct": [20],
            "max_positions": [10],
            "cooldown_days": [0, 1, 3],
            "sort_by_finance": [True],  # 按财报评分排序
        }

        total_combos = 5 * 4 * 3  # = 60
        print(f"📊 参数组合: {total_combos} 种")
        print()

        # 运行网格搜索
        results_df = run_grid_search(
            data=data,
            param_grid=param_grid,
            start_date=f"{year}0101",
            end_date=f"{year}1231",
            top_n=10,
        )

        # 打印最优策略
        print_top_strategies(results_df, top_n=10)

        # 保存结果
        output_dir = base_dir / f"{year}_每日_200_启动信号"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 运行最优策略，获取交易明细
        best = results_df.iloc[0]
        print(f"🔍 运行最优策略获取交易明细...")
        best_config = SignalConfig(
            scores_dir="",
            stock_pool="",
            start_date=f"{year}0101",
            end_date=f"{year}1231",
            buy_threshold=30,
            take_profit=best['take_profit'],
            stop_loss=best['stop_loss'],
            cooldown_days=int(best['cooldown_days']),
        )
        engine = SignalEngine(best_config)
        best_result = engine.run(
            all_scores=data['all_scores'],
            trade_dates=data['trade_dates'],
            price_cache=data['price_cache'],
            name_map=data['name_map'],
        )

        # 导出交易明细
        trades_path = output_dir / "trades.csv"
        export_trades(best_result, trades_path)

        # 保存 grid_results.csv
        csv_path = output_dir / "grid_results.csv"
        results_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"📁 结果已保存: {csv_path}")

        # 保存 README
        best = results_df.iloc[0]
        readme_path = output_dir / "README.md"
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {year}年 启动信号回测结果\n\n")
            f.write("## 策略说明\n\n")
            f.write("- **买入条件**: 前7天平均分 ≥ 30分（启动信号）\n")
            f.write("- **卖出条件**: 止盈 或 止损 触发\n")
            f.write("- **仓位管理**: 单只最多20%，最多10只\n")
            f.write("- **手续费**: 0.15%\n\n")
            f.write("## 参数网格\n\n")
            f.write("| 参数 | 范围 |\n")
            f.write("|------|------|\n")
            f.write("| 买入阈值 | 30（固定） |\n")
            f.write("| 止盈 | 5%, 10%, 15%, 20%, 30% |\n")
            f.write("| 止损 | 3%, 5%, 8%, 10% |\n")
            f.write("| 冷却期 | 0, 1, 3 天 |\n\n")
            f.write(f"## 最优策略\n\n")
            f.write(f"| 指标 | 值 |\n")
            f.write(f"|------|-----|\n")
            f.write(f"| 止盈 | {best['take_profit']:.0f}% |\n")
            f.write(f"| 止损 | {best['stop_loss']:.0f}% |\n")
            f.write(f"| 冷却期 | {best['cooldown_days']:.0f} 天 |\n")
            f.write(f"| 总收益 | {best['total_return']:+.2f}% |\n")
            f.write(f"| 年化收益 | {best['annual_return']:+.2f}% |\n")
            f.write(f"| 夏普比率 | {best['sharpe']:.3f} |\n")
            f.write(f"| 最大回撤 | {best['max_dd']:.2f}% |\n")
            f.write(f"| 胜率 | {best['win_rate']:.1f}% |\n")
            f.write(f"| 交易笔数 | {best['trades']:.0f} |\n")
            f.write(f"| 平均持仓 | {best['avg_hold']:.1f} 天 |\n")
            f.write(f"| 平均收益 | {best['avg_ret']:+.2f}% |\n\n")
            f.write("## Top 10 策略\n\n")
            f.write("| 排名 | 止盈 | 止损 | 冷却 | 总收益 | 夏普 | 胜率 |\n")
            f.write("|------|------|------|------|--------|------|------|\n")
            for i, row in results_df.head(10).iterrows():
                f.write(f"| {i+1} | {row['take_profit']:.0f}% | {row['stop_loss']:.0f}% | "
                       f"{row['cooldown_days']:.0f}天 | {row['total_return']:+.2f}% | "
                       f"{row['sharpe']:.3f} | {row['win_rate']:.1f}% |\n")

        print(f"📝 报告已保存: {readme_path}")
        print()


if __name__ == "__main__":
    main()
