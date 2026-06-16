#!/usr/bin/env python3
"""
模拟仓自动交易脚本

职责：读取 calc_signals 生成的信号 CSV，执行买卖交易，更新 portfolio.db。
- 买入：读 BUY 信号，按策略参数执行
- 卖出：读 SELL 信号（由 calc_signals 基于 K 线扫描生成），执行平仓
- 止盈止损的计算逻辑在 calc_signals.py，本脚本只负责执行

用法：
  python scripts/sim_trader.py --date 20260611
  python scripts/sim_trader.py --date 20260611 --dry-run    # 只打印不执行
  python scripts/sim_trader.py --date 20260611 --mode REAL --dry-run  # 检查实盘触达
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.portfolio import TradingManager  # noqa


# ============== 主流程 ==============

def get_latest_price(code: str, score_history: pd.DataFrame, target_date: str) -> float:
    """从 score_price_history 获取收盘价"""
    df = score_history[(score_history['code'] == code) & (score_history['date'] == target_date)]
    if df.empty:
        return None
    return float(df.iloc[0]['close_price'])



def run_auto_trade(date: str, dry_run: bool = False, mode: str = 'SIM',
                   strategy_version: str = 'v1'):
    print(f"=== 模拟仓自动交易 - {date} (mode={mode}, strategy={strategy_version}) ===")

    from src.backtest.strategies import get_strategy
    strategy = get_strategy(strategy_version)

    # 1. 加载信号（按版本分目录）
    sig_file = ROOT / "result" / "signals" / strategy.output_subdir / f"signals_{date}.csv"
    if not sig_file.exists():
        print(f"❌ {sig_file} 不存在，请先运行 calc_signals.py --strategy-version {strategy_version}")
        return
    signals = pd.read_csv(sig_file, dtype={'code': str})

    # 2. 加载最新价格
    sh_path = ROOT / "result" / "score_price_history.csv"
    if not sh_path.exists():
        print(f"❌ {sh_path} 不存在")
        return
    score_history = pd.read_csv(sh_path, dtype={'code': str})

    # 3. 初始化
    from src.backtest.strategies import get_active_config, switch_signal_version
    switch_signal_version(strategy_version)
    config = get_active_config()

    tm = TradingManager(mode=mode)
    account = tm.get_account()

    print(f"账户: 初始 ¥{account['initial_capital']:.0f}, "
          f"当前 ¥{account['current_capital']:.0f}")
    print(f"信号版本: {config['id']} - {config['name']}")
    print(f"交易策略: 阈值≥{config['threshold']}, "
          f"单股上限{config['max_position_pct']*100:.0f}%, "
          f"最多{config['max_positions']}只")

    # 4. 读取 SELL 信号执行卖出（SELL 由 calc_signals 基于 K 线生成）
    sell_signals = signals[signals['signal'] == 'SELL'].copy()
    positions = tm.get_positions()
    held_codes = {p['code'] for p in positions}

    if not sell_signals.empty:
        sell_in_hold = sell_signals[sell_signals['code'].isin(held_codes)]
        if not sell_in_hold.empty:
            print(f"\n=== 卖出信号: {len(sell_in_hold)} 只 ===")
            for _, row in sell_in_hold.iterrows():
                code = row['code']
                pos = next((p for p in positions if p['code'] == code), None)
                if not pos:
                    continue

                sell_price = float(row.get('sell_price', 0)) or float(row.get('close_price', 0))
                reason = str(row.get('sell_reason', '信号触发'))

                print(f"  {code} {pos['name']:8s} "
                      f"成本:{pos['cost_price']:.2f} 卖出价:{sell_price:.2f} 原因:{reason}")

                if dry_run:
                    continue

                result = tm.sell(code, sell_price, pos['shares'], reason=reason)
                if result['success']:
                    emoji = '🟢' if '止盈' in reason else '🛑'
                    print(f"    {emoji} {reason}: 盈亏 {result['profit']:.2f}")
    else:
        print(f"\n当前持仓: {len(positions)} 只，无卖出信号")

    # 5. 重新获取可用资金
    account = tm.get_account()
    cash = account['current_capital']
    positions = tm.get_positions()
    position_value = sum(
        (p.get('current_price') or p['cost_price']) * p['shares']
        for p in positions
    )
    total_assets = cash + position_value

    # 6. 按信号买入
    buy_signals = signals[signals['signal'] == 'BUY'].copy()
    held_codes = {p['code'] for p in positions}
    buy_signals = buy_signals[~buy_signals['code'].isin(held_codes)]
    buy_signals = buy_signals.sort_values('avg7_score', ascending=False)

    print(f"\n=== 买入信号: {len(buy_signals)} 只（已过滤已持仓） ===")

    if dry_run:
        print("(dry run 模式，不实际下单)")
    else:
        # 按策略最大持仓数
        available_slots = config['max_positions'] - len(positions)
        if available_slots <= 0:
            print(f"已达最大持仓数 {config['max_positions']}，不买入")
        else:
            for _, row in buy_signals.iterrows():
                if available_slots <= 0:
                    break
                # 现金至少保留 5%
                if cash <= total_assets * 0.05:
                    print(f"现金不足 5%，停止买入")
                    break

                code = row['code']
                name = row['name']
                price = float(row['close_price'])
                if not price or price <= 0:
                    continue

                # 按策略的 max_position_pct 计算买入金额
                target_amount = total_assets * config['max_position_pct']
                buy_amount = min(target_amount, cash * 0.95)
                shares = int(buy_amount / price / 100) * 100
                if shares < 100:
                    continue

                result = tm.buy(code, name, price, shares,
                                score=float(row['avg7_score']),
                                reason=f"信号触发 ({row['avg7_score']:.1f}分)")
                if result['success']:
                    print(f"  ✅ 买入: {code} {name} {shares}股 @ {price:.2f} "
                          f"={result['total_cost']:.2f}")
                    cash -= result['total_cost']
                    available_slots -= 1

    # 7. 收盘后保存快照
    snapshot = tm.save_snapshot(date)
    print(f"\n=== 收盘快照 ===")
    print(f"  总资产: ¥{snapshot['total_assets']:.2f}")
    print(f"  现金:   ¥{snapshot['cash']:.2f}")
    print(f"  持仓:   ¥{snapshot['position_value']:.2f}")
    print(f"  净值:   {snapshot['nav']:.4f}")

    # 8. 同日双触达弹窗提示
    if both_triggered:
        print("\n" + "=" * 50)
        print("⚠️  同日双触达警告（保守=止损优先）")
        print("=" * 50)
        for t in both_triggered:
            print(f"  {t['code']} {t['name']} 在 {t['trigger_date']} 出现同一天内")
            print(f"    最高: ≥ {t['target_tp']:.2f}（止盈）")
            print(f"    最低: ≤ {t['target_sl']:.2f}（止损）")
            print(f"    已按保守原则（止损优先）记录")
            print(f"    如有疑问，请手动调整")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description='模拟仓自动交易')
    parser.add_argument('--date', type=str, default=None, help='目标日期 YYYYMMDD')
    parser.add_argument('--dry-run', action='store_true', help='仅展示，不实际交易')
    parser.add_argument('--mode', type=str, default='SIM', help='SIM 或 REAL（仅做检查用）')
    args = parser.parse_args()

    # 安全锁：sim_trader 只能跑 SIM，绝不能给实盘下单
    if args.mode == 'REAL' and not args.dry_run:
        print("=" * 60)
        print("❌ 拒绝：sim_trader.py 不允许对实盘执行实际交易！")
        print("=" * 60)
        print("原因：实盘涉及真实资金，sim_trader 的逻辑仅供参考。")
        print("实盘操作流程：")
        print("  1. 在券商 App/PC 设置条件单（止盈/止损）")
        print("  2. 盘中条件单自动触发")
        print("  3. 收盘后，在本系统「实盘」Tab 手动录入交易（按目标价）")
        print()
        print("如需检查实盘持仓的盘中触达情况，请加 --dry-run 参数")
        print("  python scripts/sim_trader.py --mode REAL --dry-run")
        print("=" * 60)
        sys.exit(1)

    if args.mode == 'REAL':
        print("⚠️  --mode REAL + --dry-run：仅检查实盘触达情况，不实际下单")

    date = args.date or datetime.now().strftime('%Y%m%d')
    run_auto_trade(date, dry_run=args.dry_run, mode=args.mode)


if __name__ == '__main__':
    main()
