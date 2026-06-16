#!/usr/bin/env python3
"""
v2 保守策略回测（首次突破 + 资金固定 + 2 天建仓）

与 run_launch_backtest.py 完全平行，但固定 v2 参数：
  - first_break_only = True（前 7 日均分今日首次跨过 30 才买）
  - max_pos_pct_basis = 'capital'（单只上限按剩余资金算，不再按总资产浮动）
  - build_days = 2（候选股分 2 天吃完 20% 单只上限）

用法：
  python scripts/run_v2_backtest.py --year 2022 2023 2024 2025 2026
"""

import argparse
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from src.backtest.grid_search import load_backtest_data, run_grid_search, print_top_strategies
from src.backtest.signal_engine import SignalConfig, SignalEngine
from src.backtest.strategies import get_strategy

# 从注册表取 v2 策略（避免硬编码 v2 参数，加 v3 复制此脚本改一行即可）
V2 = get_strategy('v2')
V2_PARAMS = {
    "first_break_only": V2.first_break_only,
    "max_pos_pct_basis": V2.max_pos_pct_basis,
    "build_days": V2.build_days,
}


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
    parser = argparse.ArgumentParser(description="v2 保守策略回测")
    parser.add_argument("--year", type=int, nargs="+", required=True, help="回测年份")
    parser.add_argument("--pool", default="stock_self_selected.csv", help="股票池文件")
    args = parser.parse_args()

    for year in args.year:
        print()
        print("=" * 70)
        print(f"        📊 {year}年 v2 保守策略回测（首次突破 + 资金固定 + 2天建仓）")
        print("=" * 70)

        # 评分数据目录（v1 用过的，直接复用）
        base_dir = Path(__file__).parent.parent / "result" / "backtest" / str(year)
        possible_dirs = [
            base_dir / f"{year}_每日_5534_score",   # 2022 用
            base_dir / f"{year}_每日_200_score",    # 2023 用
            base_dir / f"{year}_1385_score",        # 2024/2025/2026 用
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
        print(f"🔧 v2 参数: first_break_only=True, max_pos_pct_basis=capital, build_days=2")

        # 加载数据
        print("⏳ 加载数据...")
        data = load_backtest_data(str(scores_dir), args.pool, year=year)
        if data is None:
            print("❌ 数据加载失败")
            continue

        print(f"  评分天数: {len(data['trade_dates'])}")
        print(f"  股票数量: {len(data['name_map'])}")

        # 参数网格：固定 buy_threshold=30 + v2 参数 + 止盈/止损/冷却期
        param_grid = {
            "buy_threshold": [30],
            "take_profit": [5, 10, 15, 20, 30],
            "stop_loss": [3, 5, 8, 10],
            "max_pos_pct": [20],
            "max_positions": [10],
            "cooldown_days": [0, 1, 3],
            "sort_by_finance": [False],  # 第一轮：按总评分排序
            # v2 固定
            "first_break_only": [V2_PARAMS["first_break_only"]],
            "max_pos_pct_basis": [V2_PARAMS["max_pos_pct_basis"]],
            "build_days": [V2_PARAMS["build_days"]],
        }

        total_combos = 5 * 4 * 3  # = 60
        print(f"📊 参数组合: {total_combos} 种（按总评分排序）")
        print()

        # 运行网格搜索（按总评分排序）
        results_total = run_grid_search(
            data=data,
            param_grid=param_grid,
            start_date=f"{year}0101",
            end_date=f"{year}1231",
            top_n=10,
        )

        # 第二轮：按财报评分排序
        print()
        print(f"📊 参数组合: {total_combos} 种（按财报评分排序）")
        param_grid["sort_by_finance"] = [True]
        results_finance = run_grid_search(
            data=data,
            param_grid=param_grid,
            start_date=f"{year}0101",
            end_date=f"{year}1231",
            top_n=10,
        )

        # 打印最优策略（按总评分）
        print()
        print_top_strategies(results_total, top_n=5)

        # 输出目录
        output_dir = (
            Path(__file__).parent.parent
            / "result" / "backtest"
            / "v2_首次突破_资金固定_2天建仓"
            / str(year)
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # 跑最优策略获取交易明细（按总评分）
        best_total = results_total.iloc[0]
        print(f"🔍 运行最优策略（按总评分）获取交易明细...")
        best_config = SignalConfig(
            scores_dir="",
            stock_pool="",
            start_date=f"{year}0101",
            end_date=f"{year}1231",
            buy_threshold=30,
            take_profit=best_total["take_profit"],
            stop_loss=best_total["stop_loss"],
            cooldown_days=int(best_total["cooldown_days"]),
            sort_by_finance=False,
            first_break_only=V2_PARAMS["first_break_only"],
            max_pos_pct_basis=V2_PARAMS["max_pos_pct_basis"],
            build_days=V2_PARAMS["build_days"],
        )
        engine = SignalEngine(best_config)
        result_total = engine.run(
            all_scores=data["all_scores"],
            trade_dates=data["trade_dates"],
            price_cache=data["price_cache"],
            name_map=data["name_map"],
        )
        trades_path = output_dir / "trades.csv"
        export_trades(result_total, trades_path)

        # 跑最优策略（按财报评分）
        best_finance = results_finance.iloc[0]
        print(f"🔍 运行最优策略（按财报评分）获取交易明细...")
        best_config_f = SignalConfig(
            scores_dir="",
            stock_pool="",
            start_date=f"{year}0101",
            end_date=f"{year}1231",
            buy_threshold=30,
            take_profit=best_finance["take_profit"],
            stop_loss=best_finance["stop_loss"],
            cooldown_days=int(best_finance["cooldown_days"]),
            sort_by_finance=True,
            first_break_only=V2_PARAMS["first_break_only"],
            max_pos_pct_basis=V2_PARAMS["max_pos_pct_basis"],
            build_days=V2_PARAMS["build_days"],
        )
        engine_f = SignalEngine(best_config_f)
        result_finance = engine_f.run(
            all_scores=data["all_scores"],
            trade_dates=data["trade_dates"],
            price_cache=data["price_cache"],
            name_map=data["name_map"],
        )
        trades_path_f = output_dir / "trades_finance.csv"
        export_trades(result_finance, trades_path_f)

        # 保存 grid_results.csv（v2 参数固定，写在 header 注释里）
        # 给 v1/v2 对比用，加一列标识
        results_total["strategy_version"] = "v2"
        results_finance["strategy_version"] = "v2"
        results_total.to_csv(output_dir / "grid_results.csv", index=False, encoding="utf-8-sig")
        results_finance.to_csv(output_dir / "grid_results_finance.csv", index=False, encoding="utf-8-sig")
        print(f"📁 网格结果已保存: {output_dir}/grid_results*.csv")

        # 保存 README
        readme_path = output_dir / "README.md"
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {year}年 v2 保守策略回测结果\n\n")
            f.write("## 策略说明（v2）\n\n")
            f.write("- **买入条件**: 前 7 日均分今日**首次**跨过 30 分（标准突破：昨 < 30 ≤ 今）\n")
            f.write("- **卖出条件**: 止盈 或 止损 触发\n")
            f.write("- **仓位管理**: 单只最多 20%（**按剩余资金计**，不再按总资产浮动）\n")
            f.write("- **建仓节奏**: 候选股分 **2 天** 吃完 20% 上限（避免一次性打满的滑点假设）\n")
            f.write("- **单只上限**: 最多 10 只\n")
            f.write("- **冷却期**: 同 v1\n")
            f.write("- **手续费**: 0.15%\n\n")
            f.write("## 与 v1 的核心差异\n\n")
            f.write("| 维度 | v1 | v2 |\n")
            f.write("|------|----|----|\n")
            f.write("| 买入信号 | 前 7 日均分 ≥ 30（每天判） | 前 7 日均分首次跨 30 |\n")
            f.write("| 单只上限基数 | `total_assets × 20%`（浮动） | `capital × 20%`（固定） |\n")
            f.write("| 建仓节奏 | 一次性打满 | 分 2 天建仓 |\n\n")
            f.write("## 参数网格\n\n")
            f.write("| 参数 | 范围 |\n")
            f.write("|------|------|\n")
            f.write("| 买入阈值 | 30（固定） |\n")
            f.write("| 止盈 | 5%, 10%, 15%, 20%, 30% |\n")
            f.write("| 止损 | 3%, 5%, 8%, 10% |\n")
            f.write("| 冷却期 | 0, 1, 3 天 |\n")
            f.write("| 首次突破 | True（v2 固定） |\n")
            f.write("| 资金基数 | capital（v2 固定） |\n")
            f.write("| 建仓天数 | 2（v2 固定） |\n\n")
            f.write("**总组合数**: 5 × 4 × 3 = 60 种 × 2 排序 = 120 种\n\n")
            f.write("## 按总评分排序（动量优先）\n\n")
            f.write("### 最优策略\n\n")
            f.write("| 指标 | 值 |\n")
            f.write("|------|-----|\n")
            f.write(f"| 止盈 | {best_total['take_profit']:.0f}% |\n")
            f.write(f"| 止损 | {best_total['stop_loss']:.0f}% |\n")
            f.write(f"| 冷却期 | {best_total['cooldown_days']:.0f} 天 |\n")
            f.write(f"| 总收益 | {best_total['total_return']:+.2f}% |\n")
            f.write(f"| 年化收益 | {best_total['annual_return']:+.2f}% |\n")
            f.write(f"| 夏普比率 | {best_total['sharpe']:.3f} |\n")
            f.write(f"| 最大回撤 | {best_total['max_dd']:.2f}% |\n")
            f.write(f"| 胜率 | {best_total['win_rate']:.1f}% |\n")
            f.write(f"| 交易笔数 | {best_total['trades']:.0f} |\n")
            f.write(f"| 平均持仓 | {best_total['avg_hold']:.1f} 天 |\n")
            f.write(f"| 平均收益 | {best_total['avg_ret']:+.2f}% |\n\n")
            f.write("### Top 5 策略\n\n")
            f.write("| 排名 | 止盈 | 止损 | 冷却 | 总收益 | 夏普 | 胜率 |\n")
            f.write("|------|------|------|------|--------|------|------|\n")
            for i, row in results_total.head(5).iterrows():
                f.write(
                    f"| {i+1} | {row['take_profit']:.0f}% | {row['stop_loss']:.0f}% | "
                    f"{row['cooldown_days']:.0f}天 | {row['total_return']:+.2f}% | "
                    f"{row['sharpe']:.3f} | {row['win_rate']:.1f}% |\n"
                )
            f.write("\n## 按财报评分排序（价值优先）\n\n")
            f.write("### 最优策略\n\n")
            f.write("| 指标 | 值 |\n")
            f.write("|------|-----|\n")
            f.write(f"| 止盈 | {best_finance['take_profit']:.0f}% |\n")
            f.write(f"| 止损 | {best_finance['stop_loss']:.0f}% |\n")
            f.write(f"| 冷却期 | {best_finance['cooldown_days']:.0f} 天 |\n")
            f.write(f"| 总收益 | {best_finance['total_return']:+.2f}% |\n")
            f.write(f"| 年化收益 | {best_finance['annual_return']:+.2f}% |\n")
            f.write(f"| 夏普比率 | {best_finance['sharpe']:.3f} |\n")
            f.write(f"| 最大回撤 | {best_finance['max_dd']:.2f}% |\n")
            f.write(f"| 胜率 | {best_finance['win_rate']:.1f}% |\n")
            f.write(f"| 交易笔数 | {best_finance['trades']:.0f} |\n")
            f.write(f"| 平均持仓 | {best_finance['avg_hold']:.1f} 天 |\n")
            f.write(f"| 平均收益 | {best_finance['avg_ret']:+.2f}% |\n\n")
            f.write("### Top 5 策略\n\n")
            f.write("| 排名 | 止盈 | 止损 | 冷却 | 总收益 | 夏普 | 胜率 |\n")
            f.write("|------|------|------|------|--------|------|------|\n")
            for i, row in results_finance.head(5).iterrows():
                f.write(
                    f"| {i+1} | {row['take_profit']:.0f}% | {row['stop_loss']:.0f}% | "
                    f"{row['cooldown_days']:.0f}天 | {row['total_return']:+.2f}% | "
                    f"{row['sharpe']:.3f} | {row['win_rate']:.1f}% |\n"
                )
            f.write("\n## 两种排序对比\n\n")
            f.write("| 排序方式 | 止盈 | 止损 | 冷却 | 总收益 | 夏普 | 胜率 |\n")
            f.write("|----------|------|------|------|--------|------|------|\n")
            f.write(
                f"| 按总评分 | {best_total['take_profit']:.0f}% | "
                f"{best_total['stop_loss']:.0f}% | {best_total['cooldown_days']:.0f}天 | "
                f"{best_total['total_return']:+.2f}% | {best_total['sharpe']:.3f} | "
                f"{best_total['win_rate']:.1f}% |\n"
            )
            f.write(
                f"| 按财报评分 | {best_finance['take_profit']:.0f}% | "
                f"{best_finance['stop_loss']:.0f}% | {best_finance['cooldown_days']:.0f}天 | "
                f"{best_finance['total_return']:+.2f}% | {best_finance['sharpe']:.3f} | "
                f"{best_finance['win_rate']:.1f}% |\n\n"
            )

        print(f"📝 README 已保存: {readme_path}")
        print()


if __name__ == "__main__":
    main()