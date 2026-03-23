import pandas as pd

from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_price, normalize_code
import src.utils

index_ret = None


def get_stock_ytd_return(code):
    code = normalize_code(code)
    df = get_price(code)
    if df is None or df.empty or "收盘" not in df.columns:
        return 0

    df = df.copy()
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df = df.sort_values("日期")

    year_start = pd.Timestamp.today().replace(month=1, day=1)
    ytd = df[df["日期"] >= year_start] if "日期" in df.columns else df
    if ytd.empty or len(ytd) < 2:
        return 0

    start_price = float(ytd.iloc[0]["收盘"])
    latest_price = float(ytd.iloc[-1]["收盘"])
    if start_price <= 0:
        return 0

    return (latest_price / start_price - 1) * 100


class RelativeStrengthFactor(BaseFactor):
    weight = 10

    def calculate(self):
        global index_ret
        stock_ret = get_stock_ytd_return(self.code)
        if index_ret is None:
            index_ret = src.utils.get_market_change()
        relative = stock_ret - index_ret

        if relative > 20:
            score = 10
        elif relative > 10:
            score = 8
        elif relative > 0:
            score = 6
        elif relative > -5:
            score = 4
        elif relative > -10:
            score = 3
        else:
            score = 2

        return {"name": "今年相对大盘强弱", "score": score, "sum_score": 10}
