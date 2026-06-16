"""
回测系统 — 验证因子有效性

支持两种模式：
1. scored: 使用已有 batch_result 评分（短周期，数据现成）
2. live:   重算因子评分（长周期，仅可回溯因子）

核心流程：
  每个调仓日 → 评分排序 → 选top-N → 持有N日 → 计算收益 → 统计分析
"""

import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.backtest.data import (
    get_available_score_dates,
    get_forward_return,
    get_returns_matrix,
    get_trade_days_between,
    load_batch_scores,
    load_stock_pool,
)

# ============================================================
# 配置与结果
# ============================================================


@dataclass
class BacktestConfig:
    """回测配置"""

    mode: str = "scored"  # scored=使用已有评分, live=实时计算因子
    start_date: str = ""  # YYYYMMDD, 空=最早可用
    end_date: str = ""  # YYYYMMDD, 空=最新可用
    stock_pool: str = ""  # 股票池CSV路径, 空=使用评分中的全部股票
    top_n: int = 20  # 每期选前N只
    rebalance_days: int = 5  # 调仓周期（交易日）
    hold_days: int = 5  # 持仓天数（= rebalance_days 时为连续持仓）
    cost_rate: float = 0.0015  # 交易成本（双边），0.15%
    factor_weights: Dict[str, float] = field(default_factory=dict)  # 自定义因子权重，空=默认
    score_column: str = "total_score"  # 排序依据列名
    output_dir: str = ""  # 输出目录（live模式用）


@dataclass
class Trade:
    """单笔交易记录"""

    entry_date: str
    exit_date: str
    code: str
    name: str
    entry_price: float
    exit_price: float
    return_rate: float  # 毛收益
    net_return: float  # 扣费后收益
    score: float  # 买入时评分
    rank: int  # 评分排名


@dataclass
class BacktestResult:
    """回测结果"""

    config: BacktestConfig
    trades: List[Trade]
    daily_nav: List[Tuple[str, float]]  # (date, nav)
    benchmark_nav: List[Tuple[str, float]]  # (date, nav)
    factor_ic: Dict[str, List[float]]  # 因子名 -> IC序列
    quintile_returns: Dict[str, List[float]]  # 因子名 -> 5档平均收益
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_loss_ratio: float = 0.0
    total_trades: int = 0
    turnover_count: int = 0  # 调仓次数


# ============================================================
# 回测引擎
# ============================================================


class BacktestEngine:
    """回测引擎主类"""

    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(self) -> BacktestResult:
        """执行回测"""
        if self.config.mode == "live":
            return self._run_live()
        return self._run_scored()

    def _run_live(self) -> BacktestResult:
        """live模式：使用 HistoricalScorer 实时计算因子"""
        from src.backtest.scorer import HistoricalScorer, precompute_scores

        cfg = self.config

        # 加载股票池
        stock_codes = None
        if cfg.stock_pool:
            pool_df = load_stock_pool(cfg.stock_pool)
            if not pool_df.empty:
                stock_codes = pool_df['code'].tolist()

        # 预计算评分
        scores_df = precompute_scores(
            start_date=cfg.start_date,
            end_date=cfg.end_date,
            stock_codes=stock_codes,
            rebalance_days=cfg.rebalance_days,
            output_dir=cfg.output_dir,
        )

        if scores_df.empty:
            print("❌ 没有生成任何评分数据")
            return self._empty_result()

        # 获取所有调仓日
        all_dates = sorted(scores_df['date'].unique())
        rebalance_dates = all_dates  # 已按 rebalance_days 采样

        print(f"\n📊 调仓日数量: {len(rebalance_dates)}")
        print(f"📊 Top-N: {cfg.top_n}, 持仓天数: {cfg.hold_days}")
        print(f"📊 交易成本: {cfg.cost_rate*100:.2f}% (双边)")
        print()

        # 执行调仓循环
        all_trades = []
        daily_nav = []
        benchmark_nav = []
        factor_ic_series = {}
        quintile_returns_acc = {}

        nav = 1.0
        bench_nav = 1.0

        for i in range(len(rebalance_dates) - 1):
            entry_date = rebalance_dates[i]
            exit_date = rebalance_dates[i + 1]

            print(f"🔄 调仓 {i+1}/{len(rebalance_dates)-1}: {entry_date} → {exit_date}", end="")

            # 获取当日评分
            day_scores = scores_df[scores_df['date'] == entry_date].copy()
            if day_scores.empty:
                print(" (无评分数据，跳过)")
                continue

            # 排序选股
            sort_col = cfg.score_column
            if sort_col not in day_scores.columns:
                sort_col = 'total_score'

            day_scores = day_scores.sort_values(sort_col, ascending=False).reset_index(drop=True)
            day_scores['rank'] = range(1, len(day_scores) + 1)

            top_stocks = day_scores.head(cfg.top_n)
            all_codes = day_scores['code'].tolist()

            # 计算收益
            top_returns = get_returns_matrix(
                top_stocks['code'].tolist(), entry_date, cfg.hold_days
            )

            if not top_returns:
                print(" (无价格数据，跳过)")
                continue

            gross_return = sum(top_returns.values()) / len(top_returns)
            net_return = gross_return - cfg.cost_rate

            bench_returns = get_returns_matrix(all_codes, entry_date, cfg.hold_days)
            bench_return = (
                sum(bench_returns.values()) / len(bench_returns) if bench_returns else 0
            )

            nav *= 1 + net_return
            bench_nav *= 1 + bench_return

            daily_nav.append((exit_date, nav))
            benchmark_nav.append((exit_date, bench_nav))

            # 记录交易
            for _, row in top_stocks.iterrows():
                code = row['code']
                if code in top_returns:
                    ret = top_returns[code]
                    trade = Trade(
                        entry_date=entry_date,
                        exit_date=exit_date,
                        code=code,
                        name=str(row.get('name', '')),
                        entry_price=0,
                        exit_price=0,
                        return_rate=ret,
                        net_return=ret - cfg.cost_rate,
                        score=float(row.get(sort_col, 0)),
                        rank=int(row['rank']),
                    )
                    all_trades.append(trade)

            # 计算因子IC
            self._calc_period_ic(
                day_scores, entry_date, cfg.hold_days,
                factor_ic_series, quintile_returns_acc,
            )

            n_traded = len(top_returns)
            print(f" ✓ 选{len(top_stocks)}股, 成交{n_traded}股, 收益{net_return*100:+.2f}%")

        result = self._build_result(
            all_trades, daily_nav, benchmark_nav,
            factor_ic_series, quintile_returns_acc,
        )

        return result

    def _run_scored(self) -> BacktestResult:
        """scored模式：使用已有 batch_result 评分

        前视偏差修复（2026-06-16）：
        - 评分日（signal_date）= T-1：用前一交易日的 batch_result 决策
        - 入场价 = T+1 开盘价（在 get_forward_return 中实现）
        - 加冷却期：同一股票 cooldown_days 天内不再选中
        """
        cfg = self.config

        # 1. 确定回测日期序列
        score_dates = get_available_score_dates()
        if not score_dates:
            print("❌ 没有找到任何评分数据 (result/daily_score/batch_result_*.csv)")
            return self._empty_result()

        # 按调仓周期采样
        if cfg.start_date:
            score_dates = [d for d in score_dates if d >= cfg.start_date]
        if cfg.end_date:
            score_dates = [d for d in score_dates if d <= cfg.end_date]

        if len(score_dates) < 2:
            print(f"❌ 可用评分日期不足: {len(score_dates)} 天")
            return self._empty_result()

        # 按 rebalance_days 采样调仓日
        rebalance_dates = score_dates[:: cfg.rebalance_days]
        # 确保最后一天包含在内
        if score_dates[-1] not in rebalance_dates:
            rebalance_dates.append(score_dates[-1])

        print(f"📊 回测区间: {score_dates[0]} ~ {score_dates[-1]}")
        print(f"📊 可用评分天数: {len(score_dates)}")
        print(f"📊 调仓日数量: {len(rebalance_dates)}")
        print(f"📊 Top-N: {cfg.top_n}, 持仓天数: {cfg.hold_days}")
        print(f"📊 交易成本: {cfg.cost_rate*100:.2f}% (双边)")

        # 加载冷却期参数（从 strategies 注册表）
        cooldown_days = 0
        try:
            from src.backtest.strategies import get_active_config
            cfg_strategy = get_active_config()
            cooldown_days = cfg_strategy.get('cooldown_days', 0)
            if cooldown_days > 0:
                print(f"📊 冷却期: {cooldown_days} 天（同一股票冷却期内不再选中）")
        except Exception:
            pass
        print()

        # 2. 加载股票池（如有）
        pool_codes = None
        if cfg.stock_pool:
            pool_df = load_stock_pool(cfg.stock_pool)
            if not pool_df.empty:
                pool_codes = set(pool_df['code'].tolist())
                print(f"📋 股票池: {len(pool_codes)} 只股票")

        # 3. 执行调仓循环
        all_trades = []
        daily_nav = []
        benchmark_nav = []
        factor_ic_series = {}
        quintile_returns_acc = {}

        nav = 1.0  # 组合净值
        bench_nav = 1.0  # 基准净值

        # 冷却期：记录每只股票最近一次买入的 entry_date
        last_entry_date: Dict[str, str] = {}

        for i in range(len(rebalance_dates) - 1):
            entry_date = rebalance_dates[i]
            exit_date = rebalance_dates[i + 1]

            # 修复前视偏差：用 T-1 的评分决策 T 日的买入
            # entry_date 是回测中的"开盘日"，对应的评分应来自 entry_date 之前的最后一个交易日
            entry_idx_in_dates = score_dates.index(entry_date)
            if entry_idx_in_dates == 0:
                # 第一个日期没有 T-1，跳过
                print(f"🔄 调仓 {i+1}/{len(rebalance_dates)-1}: {entry_date} (首日，无 T-1 评分，跳过)")
                continue
            score_date = score_dates[entry_idx_in_dates - 1]

            print(f"🔄 调仓 {i+1}/{len(rebalance_dates)-1}: 评分日 {score_date} → 买入日 {entry_date} → 卖出日 {exit_date}", end="")

            # 加载评分（用 T-1 日的 batch_result）
            scores_df = load_batch_scores(score_date)
            if scores_df is None or scores_df.empty:
                print(" (无评分数据，跳过)")
                continue

            # 过滤股票池
            if pool_codes is not None:
                scores_df = scores_df[scores_df['code'].isin(pool_codes)]

            if scores_df.empty:
                print(" (过滤后无股票，跳过)")
                continue

            # 应用冷却期：过滤掉冷却期内的股票
            if cooldown_days > 0:
                entry_dt = pd.to_datetime(entry_date, format='%Y%m%d')

                def _in_cooldown(code):
                    last = last_entry_date.get(code)
                    if not last:
                        return False
                    last_dt = pd.to_datetime(last, format='%Y%m%d')
                    return (entry_dt - last_dt).days < cooldown_days

                before = len(scores_df)
                scores_df = scores_df[~scores_df['code'].apply(_in_cooldown)]
                after = len(scores_df)
                if before != after:
                    print(f" [冷却过滤 {before-after} 只]", end="")

            # 排序选股
            sort_col = cfg.score_column
            if sort_col not in scores_df.columns:
                sort_col = 'total_score'

            scores_df = scores_df.sort_values(sort_col, ascending=False).reset_index(drop=True)
            scores_df['rank'] = range(1, len(scores_df) + 1)

            # Top-N 选股
            top_stocks = scores_df.head(cfg.top_n)
            all_codes = scores_df['code'].tolist()

            # 计算 top-N 组合收益（用 entry_date 作为信号日，T+1 开盘买入）
            top_returns = get_returns_matrix(
                top_stocks['code'].tolist(), entry_date, cfg.hold_days
            )

            if not top_returns:
                print(" (无价格数据，跳过)")
                continue

            # 记录冷却期
            for code in top_stocks['code'].tolist():
                last_entry_date[code] = entry_date

            # 等权组合毛收益
            gross_return = sum(top_returns.values()) / len(top_returns)
            net_return = gross_return - cfg.cost_rate  # 扣除交易成本

            # 基准：全部股票等权
            bench_returns = get_returns_matrix(all_codes, entry_date, cfg.hold_days)
            bench_return = (
                sum(bench_returns.values()) / len(bench_returns) if bench_returns else 0
            )

            # 更新净值
            nav *= 1 + net_return
            bench_nav *= 1 + bench_return

            daily_nav.append((exit_date, nav))
            benchmark_nav.append((exit_date, bench_nav))

            # 记录交易
            for _, row in top_stocks.iterrows():
                code = row['code']
                if code in top_returns:
                    ret = top_returns[code]
                    trade = Trade(
                        entry_date=entry_date,
                        exit_date=exit_date,
                        code=code,
                        name=str(row.get('name', '')),
                        entry_price=0,  # 后续可补充
                        exit_price=0,
                        return_rate=ret,
                        net_return=ret - cfg.cost_rate,
                        score=float(row.get(sort_col, 0)),
                        rank=int(row['rank']),
                    )
                    all_trades.append(trade)

            # 计算因子IC（如果有多因子列）
            self._calc_period_ic(
                scores_df, entry_date, cfg.hold_days,
                factor_ic_series, quintile_returns_acc,
            )

            n_traded = len(top_returns)
            print(f" ✓ 选{len(top_stocks)}股, 成交{n_traded}股, 收益{net_return*100:+.2f}%")

        # 4. 汇总统计
        result = self._build_result(
            all_trades, daily_nav, benchmark_nav,
            factor_ic_series, quintile_returns_acc,
        )

        return result

    def _calc_period_ic(
        self,
        scores_df: pd.DataFrame,
        date: str,
        hold_days: int,
        ic_series: Dict[str, List[float]],
        quintile_acc: Dict[str, List[List[float]]],
    ):
        """计算当期各因子的IC值和分位收益"""
        # 因子列（排除非因子列）
        exclude = {'code', 'name', 'total_score', 'rank', 'date'}
        factor_cols = [c for c in scores_df.columns if c not in exclude]

        # 计算所有股票的未来收益
        all_returns = get_returns_matrix(scores_df['code'].tolist(), date, hold_days)
        if len(all_returns) < 10:
            return

        scores_df = scores_df.copy()
        scores_df['fwd_return'] = scores_df['code'].map(all_returns)
        scores_df = scores_df.dropna(subset=['fwd_return'])

        if len(scores_df) < 10:
            return

        for col in factor_cols:
            if col not in scores_df.columns:
                continue

            # 确保因子列为数值
            factor_vals = pd.to_numeric(scores_df[col], errors='coerce')
            valid_mask = factor_vals.notna()
            if valid_mask.sum() < 10:
                continue

            valid = scores_df.loc[valid_mask].copy()
            valid['_factor'] = factor_vals[valid_mask]
            valid['_return'] = valid['fwd_return']

            # IC: Spearman rank correlation (手动实现，避免scipy依赖)
            ic = valid['_factor'].rank().corr(valid['_return'].rank())
            if not np.isnan(ic):
                ic_series.setdefault(col, []).append(ic)

            # 分位收益（5档）
            try:
                valid['_quintile'] = pd.qcut(
                    valid['_factor'], 5, labels=False, duplicates='drop'
                )
                q_ret = valid.groupby('_quintile')['_return'].mean().tolist()
                quintile_acc.setdefault(col, []).append(q_ret)
            except Exception:
                pass

    def _build_result(
        self, trades, daily_nav, benchmark_nav, ic_series, quintile_acc
    ) -> BacktestResult:
        """汇总统计指标"""
        cfg = self.config
        result = BacktestResult(
            config=cfg,
            trades=trades,
            daily_nav=daily_nav,
            benchmark_nav=benchmark_nav,
            factor_ic=ic_series,
            quintile_returns={},
        )

        if not daily_nav:
            return result

        # 总收益
        result.total_return = daily_nav[-1][1] - 1.0
        result.benchmark_return = benchmark_nav[-1][1] - 1.0 if benchmark_nav else 0
        result.excess_return = result.total_return - result.benchmark_return

        # 年化收益（假设250个交易日）
        n_periods = len(daily_nav)
        if n_periods > 1:
            total_days = n_periods * cfg.rebalance_days
            years = total_days / 250
            if years > 0 and (1 + result.total_return) > 0:
                result.annual_return = (1 + result.total_return) ** (1 / years) - 1

        # 日收益率序列
        navs = [1.0] + [nav for _, nav in daily_nav]
        daily_rets = [(navs[i + 1] / navs[i] - 1) for i in range(len(navs) - 1)]

        # 夏普比率（年化）
        if daily_rets and len(daily_rets) > 1:
            mean_ret = np.mean(daily_rets)
            std_ret = np.std(daily_rets, ddof=1)
            if std_ret > 0:
                # 年化：每期收益的夏普 × sqrt(250/rebalance_days)
                periods_per_year = 250 / cfg.rebalance_days
                result.sharpe_ratio = (mean_ret / std_ret) * np.sqrt(periods_per_year)

        # 最大回撤
        peak = 1.0
        max_dd = 0.0
        for _, nav in daily_nav:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak
            if dd > max_dd:
                max_dd = dd
        result.max_drawdown = max_dd

        # 胜率
        if trades:
            wins = [t for t in trades if t.net_return > 0]
            losses = [t for t in trades if t.net_return <= 0]
            result.total_trades = len(trades)
            result.win_rate = len(wins) / len(trades)
            result.avg_win = np.mean([t.net_return for t in wins]) if wins else 0
            result.avg_loss = np.mean([t.net_return for t in losses]) if losses else 0
            if result.avg_loss != 0:
                result.profit_loss_ratio = abs(result.avg_win / result.avg_loss)

        result.turnover_count = len(daily_nav)

        # 分位收益汇总（对齐长度后取平均）
        for factor_name, q_series in quintile_acc.items():
            if q_series:
                max_len = max(len(q) for q in q_series)
                aligned = []
                for q in q_series:
                    if len(q) == max_len:
                        aligned.append(q)
                if aligned:
                    avg_quintile = np.nanmean(aligned, axis=0).tolist()
                    result.quintile_returns[factor_name] = avg_quintile

        return result

    def _empty_result(self) -> BacktestResult:
        return BacktestResult(
            config=self.config,
            trades=[],
            daily_nav=[],
            benchmark_nav=[],
            factor_ic={},
            quintile_returns={},
        )


# ============================================================
# 单因子回测
# ============================================================


def run_factor_analysis(
    start_date: str = "",
    end_date: str = "",
    stock_pool: str = "",
    hold_days: int = 5,
) -> Dict[str, Dict]:
    """逐因子分析：IC、IC_IR、分位收益

    Returns:
        {
            factor_name: {
                "ic_mean": float,
                "ic_std": float,
                "ic_ir": float,
                "quintile_returns": [q1, q2, q3, q4, q5],
                "monotonicity": float,  # 分位收益单调性
            }
        }
    """
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        stock_pool=stock_pool,
        top_n=20,
        rebalance_days=hold_days,
        hold_days=hold_days,
    )

    engine = BacktestEngine(config)
    result = engine.run()

    analysis = {}
    for factor_name, ic_list in result.factor_ic.items():
        if len(ic_list) < 2:
            continue

        ic_arr = np.array(ic_list)
        ic_mean = np.nanmean(ic_arr)
        ic_std = np.nanstd(ic_arr, ddof=1)
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0

        q_rets = result.quintile_returns.get(factor_name, [])
        monotonicity = _calc_monotonicity(q_rets) if q_rets else 0

        analysis[factor_name] = {
            "ic_mean": round(ic_mean, 4),
            "ic_std": round(ic_std, 4),
            "ic_ir": round(ic_ir, 4),
            "quintile_returns": [round(r, 4) for r in q_rets] if q_rets else [],
            "monotonicity": round(monotonicity, 4),
            "periods": len(ic_list),
        }

    return analysis


def _calc_monotonicity(quintile_rets: List[float]) -> float:
    """计算分位收益的单调性（-1到1，1=完全单调递增）"""
    if len(quintile_rets) < 2:
        return 0

    n = len(quintile_rets)
    concordant = 0
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += 1
            if quintile_rets[j] > quintile_rets[i]:
                concordant += 1
            elif quintile_rets[j] < quintile_rets[i]:
                concordant -= 1

    return concordant / total if total > 0 else 0
