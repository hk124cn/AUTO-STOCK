"""
信号策略回测引擎（v2）

策略逻辑：
  买入：评分达到绝对阈值 → 按仓位买入
  卖出：止盈 或 止损 触发
  仓位：初始100%资金，单只最多max_pos_pct%，最多max_positions只
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.backtest.data import load_price_df, load_stock_pool
from src.datafactory.data_manager import get_finance

RESULT_DIR = Path(__file__).resolve().parent.parent.parent / "result"


@dataclass
class SignalConfig:
    scores_dir: str
    stock_pool: str
    start_date: str = ""
    end_date: str = ""
    buy_threshold: float = 30.0
    take_profit: float = 20.0
    stop_loss: float = 9.0
    max_pos_pct: float = 20.0
    max_positions: int = 10
    cooldown_days: int = 1
    cost_rate: float = 0.0015
    initial_capital: float = 1000000.0
    sort_by_pb: bool = False  # 是否按市净率排序（低PB优先）
    sort_by_finance: bool = False  # 是否按财报评分排序（高分优先）

    # === v2 保守策略参数（默认值兼容 v1 行为）===
    # 1. 首次突破过滤：True=仅在前 7 日均分今日首次跨过阈值时买入
    first_break_only: bool = False
    # 2. 单只仓位上限的计算基数：'total_assets'=总资产(v1)，'capital'=剩余资金(v2)
    max_pos_pct_basis: str = "total_assets"
    # 3. 建仓分几天：1=v1 一次性，2/3=分 N 天建仓
    build_days: int = 1


@dataclass
class SignalTrade:
    code: str
    name: str
    buy_date: str
    sell_date: str
    buy_score: float
    sell_score: float
    buy_price: float
    sell_price: float
    shares: int
    hold_days: int
    return_rate: float
    net_return: float
    reason: str


@dataclass
class SignalResult:
    config: SignalConfig
    trades: List[SignalTrade]
    daily_nav: List[Tuple[str, float]]
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    avg_hold_days: float = 0.0
    avg_return: float = 0.0
    final_capital: float = 0.0


class SignalEngine:

    def __init__(self, config: SignalConfig):
        self.config = config
        self._pb_cache = {}  # 缓存市净率数据

    def _get_pb_ratio(self, code: str, price: float) -> float:
        """计算市净率（PB）= 股价 / 每股净资产"""
        if code in self._pb_cache:
            bvps = self._pb_cache[code]
        else:
            try:
                finance_df = get_finance(code)
                if finance_df is not None and not finance_df.empty:
                    # 获取最新的每股净资产
                    bvps_col = '每股净资产'
                    if bvps_col in finance_df.columns:
                        bvps = finance_df[bvps_col].iloc[0]
                        if isinstance(bvps, str):
                            bvps = float(bvps) if bvps != 'False' else None
                        self._pb_cache[code] = bvps
                    else:
                        self._pb_cache[code] = None
                        return None
                else:
                    self._pb_cache[code] = None
                    return None
            except Exception:
                self._pb_cache[code] = None
                return None

        if bvps is None or bvps <= 0:
            return None
        return price / bvps

    def _precompute_score_dicts(self, all_scores: dict, trade_dates: list) -> dict:
        """预计算每天的评分字典，提高查询效率"""
        score_dicts = {}
        finance_dicts = {}  # 财报评分字典
        for date in trade_dates:
            day_scores = all_scores.get(date)
            if day_scores is not None and not day_scores.empty:
                score_dicts[date] = dict(zip(day_scores['code'], day_scores['total_score']))
                # 提取财报评分
                if '财报' in day_scores.columns:
                    finance_dicts[date] = dict(zip(day_scores['code'], day_scores['财报']))
                else:
                    finance_dicts[date] = {}
            else:
                score_dicts[date] = {}
                finance_dicts[date] = {}
        self._finance_dicts = finance_dicts
        return score_dicts

    def _get_avg_score(self, code: str, current_idx: int, trade_dates: list,
                       score_dicts: dict, lookback: int = 7) -> float:
        """计算过去lookback天的平均评分（使用预计算的字典）"""
        scores = []
        for j in range(max(0, current_idx - lookback), current_idx):
            d = trade_dates[j]
            day_dict = score_dicts.get(d, {})
            if code in day_dict:
                scores.append(day_dict[code])
        return np.mean(scores) if scores else None

    def run(self, all_scores: dict, trade_dates: list,
            price_cache: dict, name_map: dict) -> SignalResult:
        """执行信号策略回测

        ⚠️ 已知前视偏差（look-ahead bias），仅供实验，不可用于策略评估。

        与 engine.py _run_scored() 的关键差异（均未修复）：

        1. T 日评分 → T 日买入（前视偏差）
           _run_scored 用 T-1 日评分决定 T 日买入；本方法用当天评分
           score_dicts.get(date) 直接取 entry_date 当天数据，即"看到了
           当天数据再决策"。

        2. 无 T+1 开盘价入场 + 滑点
           _run_scored 用 T+1 开盘价 + 0.1% 滑点作为入场价；本方法用
           get_price(code, date) 取 T 日收盘价，无滑点。高估实际收益。

        3. 已有冷却期 ✅
           cooldown_days 逻辑已实现（line 225-226, 282）。

        后果：回测收益率会系统性高于实际可实现收益，夏普比率失真。
        修复需将 T-1 评分 + T+1 开盘价 + 滑点逻辑同步到本方法，
        预计 1-2h 工作量。
        """
        cfg = self.config

        if cfg.start_date:
            trade_dates = [d for d in trade_dates if d >= cfg.start_date]
        if cfg.end_date:
            trade_dates = [d for d in trade_dates if d <= cfg.end_date]
        if len(trade_dates) < 2:
            return self._empty_result()

        # 预计算评分字典，提高查询效率
        score_dicts = self._precompute_score_dicts(all_scores, trade_dates)

        positions = {}
        capital = cfg.initial_capital
        all_trades = []
        daily_nav = []
        cooldown_until = {}

        def get_price(code, date):
            """从 price_cache 获取价格（支持 dict-of-dict 和 DataFrame 两种格式）"""
            cache = price_cache.get(code)
            if cache is None:
                return None
            if isinstance(cache, dict):
                p = cache.get(date)
                return p if p and not np.isnan(p) else None
            # DataFrame 格式（兼容旧调用）
            target = pd.to_datetime(date, format='%Y%m%d')
            row = cache[cache['日期'] == target]
            if row.empty:
                return None
            p = float(row.iloc[0]['收盘'])
            return p if not np.isnan(p) else None

        def portfolio_value(pos, date):
            total = 0
            for code, p in pos.items():
                price = get_price(code, date)
                if price:
                    total += price * p['shares']
            return total

        for i, date in enumerate(trade_dates):
            score_dict = score_dicts.get(date, {})

            # 1. 检查卖出
            codes_to_sell = []
            for code, pos in positions.items():
                cp = get_price(code, date)
                if cp is None:
                    continue
                ret_pct = (cp - pos['buy_price']) / pos['buy_price'] * 100
                hold = i - pos['entry_idx']

                reason = None
                if ret_pct >= cfg.take_profit:
                    reason = "take_profit"
                elif ret_pct <= -cfg.stop_loss:
                    reason = "stop_loss"

                if reason:
                    sell_value = cp * pos['shares']
                    fee = sell_value * cfg.cost_rate
                    capital += sell_value - fee
                    all_trades.append(SignalTrade(
                        code=code, name=name_map.get(code, ''),
                        buy_date=pos['buy_date'], sell_date=date,
                        buy_score=pos['buy_score'], sell_score=score_dict.get(code, 0),
                        buy_price=pos['buy_price'], sell_price=cp,
                        shares=pos['shares'], hold_days=hold,
                        return_rate=ret_pct,
                        net_return=((sell_value - fee) - pos['cost']) / pos['cost'] * 100,
                        reason=reason,
                    ))
                    codes_to_sell.append(code)
                    if cfg.cooldown_days > 0:
                        cooldown_until[code] = i + cfg.cooldown_days

            for c in codes_to_sell:
                del positions[c]

            # 2. 检查买入
            if score_dict and len(positions) < cfg.max_positions:
                port_val = portfolio_value(positions, date)
                total_assets = capital + port_val

                # 2a. 先处理已有持仓的"分 N 天建仓"剩余仓位（v2 新增）
                if cfg.build_days > 1:
                    for code in list(positions.keys()):
                        pos = positions[code]
                        if pos.get('filled_days', 1) >= pos.get('build_days', 1):
                            continue  # 已建满
                        bp = get_price(code, date)
                        if bp is None or bp <= 0:
                            continue
                        # 单只目标金额（仍按 total_assets 计，避免反复浮动）
                        target_amount = total_assets * pos['target_pos_pct'] / 100
                        # 每天平均金额（按总建仓天数摊）
                        amount_per_day = target_amount / pos['build_days']
                        buy_amount = min(amount_per_day, capital * 0.95)
                        if buy_amount < bp:
                            continue
                        shares = int(buy_amount / bp)
                        if shares <= 0:
                            continue
                        cost = shares * bp
                        fee = cost * cfg.cost_rate
                        total_cost = cost + fee
                        if total_cost > capital:
                            continue
                        capital -= total_cost
                        # 加权更新均价与累计成本
                        old_cost = pos['cost']
                        old_shares = pos['shares']
                        new_shares = old_shares + shares
                        new_cost_basis = old_cost + total_cost
                        pos['buy_price'] = new_cost_basis / new_shares
                        pos['cost'] = new_cost_basis
                        pos['shares'] = new_shares
                        pos['filled_days'] = pos.get('filled_days', 1) + 1

                # 2b. 寻找新候选
                candidates = []
                for code in score_dict.keys():
                    # 使用前7天平均分作为买入判断
                    avg_score = self._get_avg_score(code, i, trade_dates, score_dicts, lookback=7)
                    if avg_score is None:
                        continue
                    if code in positions:
                        continue
                    if avg_score < cfg.buy_threshold:
                        continue
                    if code in cooldown_until and i < cooldown_until[code]:
                        continue
                    # v2 新增：首次突破过滤——仅在前 7 日均分今日首次跨过阈值时买入
                    if cfg.first_break_only and i > 0:
                        prev_avg = self._get_avg_score(
                            code, i - 1, trade_dates, score_dicts, lookback=7
                        )
                        # 昨日也满足 → 不是首次突破；昨日无数据 → 也不视作突破
                        if prev_avg is None or prev_avg >= cfg.buy_threshold:
                            continue
                    # 获取财报评分用于排序
                    finance_score = self._finance_dicts.get(date, {}).get(code, 0)
                    candidates.append((code, avg_score, finance_score))

                # 排序逻辑
                if cfg.sort_by_finance:
                    # 按财报评分从高到低，财报评分相同按总评分从高到低
                    candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
                else:
                    # 按总评分从高到低
                    candidates.sort(key=lambda x: x[1], reverse=True)

                for code, score, finance_score in candidates:
                    if len(positions) >= cfg.max_positions:
                        break
                    bp = get_price(code, date)
                    if bp is None or bp <= 0:
                        continue
                    # v2 新增：单只上限基于剩余资金而非总资产（避免持仓涨时仓位膨胀）
                    if cfg.max_pos_pct_basis == "capital":
                        max_amount = capital * cfg.max_pos_pct / 100
                    else:
                        max_amount = total_assets * cfg.max_pos_pct / 100
                    # v2 新增：分 N 天建仓时，每天只买 1/N
                    if cfg.build_days > 1:
                        max_amount = max_amount / cfg.build_days
                    buy_amount = min(max_amount, capital * 0.95)
                    if buy_amount < bp:
                        continue
                    shares = int(buy_amount / bp)
                    if shares <= 0:
                        continue
                    cost = shares * bp
                    fee = cost * cfg.cost_rate
                    total_cost = cost + fee
                    if total_cost > capital:
                        continue
                    capital -= total_cost
                    positions[code] = {
                        'buy_date': date, 'buy_price': bp,
                        'buy_score': score, 'shares': shares,
                        'entry_idx': i, 'cost': total_cost,
                        # v2 新增：建仓进度（首次建仓后 filled_days=1）
                        'target_pos_pct': cfg.max_pos_pct,
                        'build_days': cfg.build_days,
                        'filled_days': 1,
                    }

            # 3. 记录净值
            port_val = portfolio_value(positions, date)
            nav = (capital + port_val) / cfg.initial_capital
            daily_nav.append((date, nav))

        # 4. 年末平仓
        last_date = trade_dates[-1]
        for code, pos in list(positions.items()):
            cp = get_price(code, last_date)
            if cp and cp > 0:
                sell_value = cp * pos['shares']
                fee = sell_value * cfg.cost_rate
                capital += sell_value - fee
                ret_pct = (cp - pos['buy_price']) / pos['buy_price'] * 100
                all_trades.append(SignalTrade(
                    code=code, name=name_map.get(code, ''),
                    buy_date=pos['buy_date'], sell_date=last_date,
                    buy_score=pos['buy_score'], sell_score=score_dict.get(code, 0),
                    buy_price=pos['buy_price'], sell_price=cp,
                    shares=pos['shares'], hold_days=len(trade_dates) - 1 - pos['entry_idx'],
                    return_rate=ret_pct,
                    net_return=((sell_value - fee) - pos['cost']) / pos['cost'] * 100,
                    reason="year_end",
                ))

        # 5. 统计
        result = SignalResult(config=cfg, trades=all_trades, daily_nav=daily_nav, final_capital=capital)
        if daily_nav:
            result.total_return = (daily_nav[-1][1] - 1) * 100
        if len(daily_nav) > 1:
            navs = [n for _, n in daily_nav]
            rets = [(navs[j+1] / navs[j] - 1) for j in range(len(navs) - 1)]
            if rets:
                years = len(daily_nav) / 250
                if years > 0 and daily_nav[-1][1] > 0:
                    result.annual_return = ((daily_nav[-1][1]) ** (1 / years) - 1) * 100
                mean_r = np.mean(rets)
                std_r = np.std(rets, ddof=1)
                if std_r > 0:
                    result.sharpe_ratio = (mean_r / std_r) * np.sqrt(250)
                peak = 1.0
                max_dd = 0.0
                for _, n in daily_nav:
                    if n > peak:
                        peak = n
                    dd = (peak - n) / peak
                    if dd > max_dd:
                        max_dd = dd
                result.max_drawdown = max_dd * 100
        if all_trades:
            wins = [t for t in all_trades if t.net_return > 0]
            result.win_rate = len(wins) / len(all_trades) * 100
            result.total_trades = len(all_trades)
            result.avg_hold_days = np.mean([t.hold_days for t in all_trades])
            result.avg_return = np.mean([t.net_return for t in all_trades])
        return result

    def _empty_result(self):
        return SignalResult(config=self.config, trades=[], daily_nav=[])
