import pandas as pd

from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_price, normalize_code


def get_5day_return(code):
    code = normalize_code(code)
    df = get_price(code)
    if df is None or df.empty or "收盘" not in df.columns:
        return 0

    df = df.copy()
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df = df.sort_values("日期")

    if len(df) < 6:
        return 0

    last_6 = df.tail(6)
    start_price = float(last_6.iloc[0]["收盘"])
    end_price = float(last_6.iloc[-1]["收盘"])
    if start_price <= 0:
        return 0

    return (end_price / start_price - 1) * 100


class FiveDayReturnFactor(BaseFactor):
    weight = 10

    def calculate(self):
        ret5 = get_5day_return(self.code)

        if ret5 > 10:
            score = 10
        elif ret5 > 5:
            score = 8
        elif ret5 > 0:
            score = 6
        elif ret5 > -5:
            score = 4
        else:
            score = 2

        return {"name": "5日涨跌幅", "score": score, "sum_score": 10}
