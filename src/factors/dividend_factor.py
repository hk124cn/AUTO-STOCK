import pandas as pd

from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_dividend, get_price, normalize_code


def _safe_to_datetime(series):
    return pd.to_datetime(series, errors="coerce")


def _pick_announcement_col(df):
    for col in ["公告日期", "实施公告日", "除权日", "股权登记日"]:
        if col in df.columns:
            return col
    return None


def _calc_dividend_yield_from_df(div_df, price, target_date=None):
    if div_df is None or div_df.empty or price <= 0:
        return 0.0

    div_df = div_df.copy()
    date_col = _pick_announcement_col(div_df)
    if date_col is None or "派息" not in div_df.columns:
        return 0.0

    div_df[date_col] = _safe_to_datetime(div_df[date_col])
    div_df["派息"] = pd.to_numeric(div_df["派息"], errors="coerce").fillna(0)

    if target_date is None:
        # 实时：优先最近一次有效分红
        valid = div_df.dropna(subset=[date_col]).sort_values(date_col)
        if valid.empty:
            return 0.0
        latest = valid.iloc[-1]
        return max(0.0, float(latest["派息"]) / 10 / float(price))

    target_dt = pd.to_datetime(target_date)
    one_year_before = target_dt - pd.Timedelta(days=365)

    valid = div_df[(div_df[date_col] <= target_dt) & (div_df[date_col] > one_year_before)]
    if valid.empty:
        return 0.0

    total_dividend = (valid["派息"] / 10).sum()
    return max(0.0, float(total_dividend) / float(price))


def _get_latest_close(code, target_date=None):
    code = normalize_code(code)
    price_df = get_price(code)
    if price_df is None or price_df.empty or "收盘" not in price_df.columns:
        return None

    df = price_df.copy()
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")

    if target_date is None:
        return float(df["收盘"].iloc[-1])

    target_dt = pd.to_datetime(target_date)
    if "日期" not in df.columns:
        return None

    hist = df[df["日期"] <= target_dt]
    if hist.empty:
        return None
    return float(hist.iloc[-1]["收盘"])


def get_dividend_yield(stock_code: str, date: str = None):
    code = normalize_code(stock_code)
    price = _get_latest_close(code, date)
    if price is None:
        return 0.0

    div_df = get_dividend(code, refresh=False)
    ann_col = _pick_announcement_col(div_df) if div_df is not None else None

    if date is None and div_df is not None and ann_col is not None:
        temp = div_df.copy()
        temp[ann_col] = _safe_to_datetime(temp[ann_col])
        last_ann = temp[ann_col].max()
        # 若公告日距离今天太久，尝试刷新一次
        if pd.notna(last_ann) and (pd.Timestamp.today() - last_ann).days > 120:
            div_df = get_dividend(code, refresh=True)

    if date is None and (div_df is None or div_df.empty):
        div_df = get_dividend(code, refresh=True)

    return _calc_dividend_yield_from_df(div_df, price, target_date=date)


def _piecewise_linear_score(dy):
    points = [(0.00, 0), (0.02, 4), (0.05, 8), (0.08, 10), (0.10, 10)]
    if dy > 0.10:
        return 6

    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        if x1 <= dy <= x2:
            score = y1 + (dy - x1) * (y2 - y1) / (x2 - x1)
            return round(score, 2)
    return 0


def js_score(code: str, date: str = None):
    dy = get_dividend_yield(code, date)
    return _piecewise_linear_score(dy)


class dividendfactor(BaseFactor):
    def __init__(self, code, name=None):
        super().__init__(code, name)

    def calculate(self):
        score = js_score(self.code)
        return {"name": "股息率", "score": score, "sum_score": 10}
