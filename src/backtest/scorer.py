"""
历史因子评分器 — Point-in-Time 回测数据生成

对指定日期范围内的所有交易日，计算所有可回溯因子的得分。
输出预计算的评分表，供回测引擎直接使用。

支持的因子（有历史数据）：
  - 5日涨跌幅（10分）
  - 单日涨跌幅（10分）
  - 财报（20分）
  - 股息率（10分）
  - 今年相对大盘强弱（10分）

不支持的因子（无历史数据，得0分）：
  - 关注度、新闻、资金流向、行业相对强弱
"""

import gc
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# 路径配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PRICE_DIR = DATA_DIR / "price"
RESULT_DIR = BASE_DIR / "result"


class HistoricalScorer:
    """历史因子评分器（预加载优化版）"""

    def __init__(self, stock_codes: List[str] = None):
        self._stock_codes: List[str] = []
        self._name_map: Dict[str, str] = {}
        self._price_data: Dict[str, tuple] = {}  # code -> (dates_array, closes_array)
        self._finance_data: Dict[str, list] = {}  # code -> list of dicts
        self._disclosure_map: Dict[str, dict] = {}  # code -> {报告期: 公告日期}
        self._dividend_data: Dict[str, pd.DataFrame] = {}

        if stock_codes is None:
            stock_codes = [f.stem for f in PRICE_DIR.glob("*.csv")]
        self._stock_codes = [str(c).zfill(6) for c in stock_codes]

        # 加载股票名称
        pool_path = BASE_DIR / "stock_pool.csv"
        if pool_path.exists():
            try:
                pool_df = pd.read_csv(pool_path, dtype={'code': str})
                pool_df['code'] = pool_df['code'].astype(str).str.zfill(6)
                self._name_map = dict(zip(pool_df['code'], pool_df['name']))
            except Exception:
                pass

        print(f"📊 历史评分器: {len(self._stock_codes)} 只股票")

    def preload_all(self):
        """预加载所有数据"""
        t0 = time.time()

        # 价格数据
        loaded = 0
        for code in self._stock_codes:
            path = PRICE_DIR / f"{code}.csv"
            if not path.exists():
                continue
            try:
                df = pd.read_csv(path, usecols=['日期', '收盘'], dtype={'收盘': np.float32})
                if df.empty:
                    continue
                dates = pd.to_datetime(df['日期'].astype(str), format='%Y%m%d').values
                closes = df['收盘'].values
                self._price_data[code] = (dates, closes)
                loaded += 1
            except Exception:
                pass
        print(f"  价格数据: {loaded} 只 ({time.time()-t0:.1f}s)")

        # 财报数据
        t0 = time.time()
        finance_dir = DATA_DIR / "finance"
        loaded = 0
        for code in self._stock_codes:
            path = finance_dir / f"{code}.csv"
            if path.exists():
                try:
                    df = pd.read_csv(path)
                    if not df.empty:
                        self._finance_data[code] = df.to_dict('records')
                        loaded += 1
                except Exception:
                    pass
        print(f"  财报数据: {loaded} 只 ({time.time()-t0:.1f}s)")

        # 公告日期
        t0 = time.time()
        disc_dir = DATA_DIR / "disclosure"
        loaded = 0
        for code in self._stock_codes:
            path = disc_dir / f"{code}.csv"
            if path.exists():
                try:
                    df = pd.read_csv(path)
                    if not df.empty:
                        self._disclosure_map[code] = dict(
                            zip(df['报告期'].astype(str), df['公告日期'].astype(str))
                        )
                        loaded += 1
                except Exception:
                    pass
        print(f"  公告日期: {loaded} 只 ({time.time()-t0:.1f}s)")

        # 分红数据
        t0 = time.time()
        div_dir = DATA_DIR / "dividend"
        loaded = 0
        for code in self._stock_codes:
            path = div_dir / f"{code}.csv"
            if path.exists():
                try:
                    df = pd.read_csv(path)
                    if not df.empty:
                        self._dividend_data[code] = df
                        loaded += 1
                except Exception:
                    pass
        print(f"  分红数据: {loaded} 只 ({time.time()-t0:.1f}s)")

    def score_all_stocks(self, date: str) -> pd.DataFrame:
        """计算指定日期所有股票的因子得分"""
        target = pd.to_datetime(date, format='%Y%m%d')
        records = []

        for code in self._stock_codes:
            score = self._score_one(code, target)
            if score is not None:
                score['date'] = date
                score['name'] = self._name_map.get(code, '')
                records.append(score)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.sort_values('total_score', ascending=False).reset_index(drop=True)
        return df

    def _score_one(self, code: str, target_date: pd.Timestamp) -> Optional[dict]:
        """计算单只股票在指定日期的因子得分"""
        if code not in self._price_data:
            return None

        dates, closes = self._price_data[code]
        mask = dates <= target_date
        if mask.sum() < 21:
            return None

        fiveday_score = self._calc_fiveday(closes, mask)
        daily_score = self._calc_daily(closes, mask)
        finance_score = self._calc_finance(code, target_date)
        dividend_score = self._calc_dividend(code, closes, dates, mask)
        ytd_score = self._calc_ytd(dates, closes, mask, target_date)

        total = fiveday_score + daily_score + finance_score + dividend_score + ytd_score
        return {
            'code': code,
            '5日涨跌幅': fiveday_score,
            '单日涨跌幅': daily_score,
            '财报': finance_score,
            '股息率': dividend_score,
            '今年相对大盘强弱': ytd_score,
            'total_score': round(total, 2),
        }

    # ========== 因子计算（numpy数组版）==========

    @staticmethod
    def _calc_fiveday(closes: np.ndarray, mask: np.ndarray) -> float:
        c = closes[mask]
        if len(c) < 6:
            return 0
        s, e = c[-6], c[-1]
        if np.isnan(s) or np.isnan(e) or s <= 0:
            return 0
        ret = (e / s - 1) * 100
        if ret > 10:
            return 10
        elif ret > 5:
            return 8
        elif ret > 0:
            return 6
        elif ret > -5:
            return 4
        return 2

    @staticmethod
    def _calc_daily(closes: np.ndarray, mask: np.ndarray) -> float:
        c = closes[mask]
        if len(c) < 21:
            return 0
        last21 = c[-21:]
        if np.isnan(last21[-1]) or np.isnan(last21[-2]) or last21[-2] <= 0:
            return 0
        chg = (last21[-1] - last21[-2]) / last21[-2] * 100

        ma5 = np.nanmean(last21[-5:])
        ma20 = np.nanmean(last21[-20:])
        if np.isnan(ma5) or np.isnan(ma20) or ma20 <= 0:
            trend = 'weak_up'
        else:
            s = (ma5 - ma20) / ma20
            if s > 0.05:
                trend = 'strong_up'
            elif s > 0:
                trend = 'weak_up'
            elif s > -0.05:
                trend = 'weak_down'
            else:
                trend = 'strong_down'

        scores = {
            'strong_up': [(-10,-7,8),(-7,-3,6),(-3,0,4),(0,3,2),(3,7,1),(7,10,0)],
            'weak_up':   [(-10,-7,7),(-7,-3,5),(-3,0,3),(0,3,4),(3,7,6),(7,10,3)],
            'weak_down': [(-10,-7,6),(-7,-3,4),(-3,0,2),(0,3,5),(3,7,7),(7,10,8)],
            'strong_down':[(-10,-7,9),(-7,-3,7),(-3,0,3),(0,3,6),(3,7,8),(7,10,9)],
        }
        base = 5
        for lo, hi, sc in scores[trend]:
            if lo <= chg < hi:
                base = sc
                break
        return float(min(10, max(0, base)))

    def _calc_finance(self, code: str, target_date: pd.Timestamp) -> float:
        rows = self._finance_data.get(code)
        if not rows:
            return 0

        period_map = self._disclosure_map.get(code, {})

        available = []
        for row in rows:
            rp = str(row.get('报告期', ''))
            if rp in period_map:
                try:
                    if pd.to_datetime(period_map[rp]) <= target_date:
                        available.append(row)
                except Exception:
                    pass
            else:
                if self._conservative_available(rp, target_date):
                    available.append(row)

        if len(available) < 3:
            return 0

        recent3 = available[-3:]
        koufei = [self._to_float(r.get('扣非净利润同比增长率', 0)) for r in recent3]
        guimu = [self._to_float(r.get('净利润同比增长率', 0)) for r in recent3]
        yingshou = [self._to_float(r.get('营业总收入同比增长率', 0)) for r in recent3]

        k_base = self._growth_score(koufei[2], 10, 50)
        k_trend = self._trend_score(koufei, 10)
        g_base = self._growth_score(guimu[2], 5, 25)
        g_trend = self._trend_score(guimu, 5)
        y_base = self._growth_score(yingshou[2], 5, 25)
        y_trend = self._trend_score(yingshou, 5)

        total = k_base + k_trend + g_base + g_trend + y_base + y_trend
        return max(min(round(total, 2), 20), -10)

    def _calc_dividend(self, code: str, closes: np.ndarray,
                       dates: np.ndarray, mask: np.ndarray) -> float:
        c = closes[mask]
        d = dates[mask]
        if len(c) == 0:
            return 0
        price = float(c[-1])
        if np.isnan(price) or price <= 0:
            return 0

        ddf = self._dividend_data.get(code)
        if ddf is None:
            return 0

        date_col = None
        for col in ['公告日期', '实施公告日', '除权日', '股权登记日']:
            if col in ddf.columns:
                date_col = col
                break
        if date_col is None or '派息' not in ddf.columns:
            return 0

        ddf2 = ddf.copy()
        ddf2[date_col] = pd.to_datetime(ddf2[date_col], errors='coerce')
        ddf2['派息'] = pd.to_numeric(ddf2['派息'], errors='coerce').fillna(0)

        target_dt = d[-1]
        year_ago = target_dt - np.timedelta64(365, 'D')

        valid = ddf2[(ddf2[date_col] <= target_dt) & (ddf2[date_col] > year_ago)]
        if valid.empty:
            return 0

        total_div = (valid['派息'] / 10).sum()
        dy = max(0.0, float(total_div) / price)

        pts = [(0, 0), (0.02, 4), (0.05, 8), (0.08, 10), (0.10, 10)]
        if dy > 0.10:
            return 6
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            if x1 <= dy <= x2:
                return round(y1 + (dy - x1) * (y2 - y1) / (x2 - x1), 2)
        return 0

    @staticmethod
    def _calc_ytd(dates: np.ndarray, closes: np.ndarray,
                  mask: np.ndarray, target_date: pd.Timestamp) -> float:
        d = dates[mask]
        c = closes[mask]
        if len(c) == 0:
            return 0

        year_start = np.datetime64(f'{target_date.year}-01-01')
        year_mask = d >= year_start
        prev_mask = d < year_start

        if not year_mask.any() or not prev_mask.any():
            return 0

        s = float(c[prev_mask][-1])
        e = float(c[year_mask][-1])
        if np.isnan(s) or np.isnan(e) or s <= 0:
            return 0

        ret = (e / s - 1) * 100
        if ret > 20:
            return 10
        elif ret > 10:
            return 8
        elif ret > 0:
            return 6
        elif ret > -5:
            return 4
        elif ret > -10:
            return 3
        return 2

    # ========== 工具 ==========

    @staticmethod
    def _to_float(v):
        try:
            return float(str(v).replace('%', '').strip())
        except Exception:
            return 0.0

    @staticmethod
    def _growth_score(rate, full, max_neg):
        if np.isnan(rate):
            return 0
        if rate >= 0:
            return full * min(rate / 40, 1)
        return -max_neg * (rate / 100) / 10

    @staticmethod
    def _trend_score(rates, full):
        if len(rates) < 3 or any(np.isnan(r) for r in rates):
            return 0
        a, b, c = rates
        chg1, chg2 = c - b, b - a
        avg = (chg1 + chg2) / 2
        t = 0
        if c > b > a:
            t = 0.075 * full
        elif c < b < a:
            t = -0.075 * full
        elif a < 0 and c > 0 and c > b:
            t = 0.05 * full
        elif a > 0 and c < 0 and c < b:
            t = -0.05 * full
        elif avg > 5:
            t = 0.05 * full
        elif avg < -5:
            t = -0.05 * full
        return max(min(t, 0.1 * full), -0.1 * full)

    @staticmethod
    def _conservative_available(rp: str, target: pd.Timestamp) -> bool:
        try:
            dt = pd.to_datetime(rp)
        except Exception:
            return False
        y, m = dt.year, dt.month
        if m == 12:
            ddl = pd.Timestamp(y + 1, 4, 30)
        elif m == 3:
            ddl = pd.Timestamp(y, 4, 30)
        elif m == 6:
            ddl = pd.Timestamp(y, 8, 31)
        elif m == 9:
            ddl = pd.Timestamp(y, 10, 31)
        else:
            return False
        return ddl <= target


def precompute_scores(start_date: str, end_date: str,
                      stock_codes: List[str] = None,
                      rebalance_days: int = 5,
                      output_dir: str = "") -> pd.DataFrame:
    """预计算指定日期范围内的所有评分"""
    calendar_file = DATA_DIR / "calendar" / "trade_days.csv"
    cal_df = pd.read_csv(calendar_file)
    cal_col = cal_df.columns[0]
    all_days = pd.to_datetime(cal_df[cal_col])

    start_dt = pd.to_datetime(start_date, format='%Y%m%d')
    end_dt = pd.to_datetime(end_date, format='%Y%m%d')
    trade_days = all_days[(all_days >= start_dt) & (all_days <= end_dt)]
    trade_days = trade_days[::rebalance_days]
    date_strs = [d.strftime('%Y%m%d') for d in trade_days]

    if not date_strs:
        print("❌ 指定范围内无交易日")
        return pd.DataFrame()

    print(f"\n📊 预计算: {date_strs[0]} ~ {date_strs[-1]}, 共 {len(date_strs)} 个调仓日")

    scorer = HistoricalScorer(stock_codes)
    print("⏳ 预加载数据...")
    scorer.preload_all()

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    all_frames = []
    for i, ds in enumerate(date_strs):
        t0 = time.time()
        print(f"  [{i+1}/{len(date_strs)}] {ds}", end="", flush=True)

        df = scorer.score_all_stocks(ds)
        if df.empty:
            print(" (无数据)")
            continue

        elapsed = time.time() - t0
        print(f" → {len(df)}只, 均分{df['total_score'].mean():.1f}, {elapsed:.1f}s")

        all_frames.append(df)

        if output_dir:
            df.to_csv(os.path.join(output_dir, f"scores_{ds}.csv"), index=False)

        # 定期GC
        if (i + 1) % 10 == 0:
            gc.collect()

    if not all_frames:
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    print(f"\n✅ 预计算完成: {len(result)} 条, {result['code'].nunique()} 只股票")
    return result
