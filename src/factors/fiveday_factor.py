import akshare as ak
import pandas as pd
from src.core.base_factor import BaseFactor


def get_5day_return(code):
    df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")

    if len(df) < 6:
        return 0

    df = df.tail(6)

    start_price = df.iloc[0]["收盘"]
    end_price = df.iloc[-1]["收盘"]

    return (end_price / start_price - 1) * 100


class FiveDayReturnFactor(BaseFactor):

    weight = 10

    def calculate(self):

        ret5 = get_5day_return(self.code)

        # 趋势打分（0~10）
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

        print(f"5日涨跌幅: {ret5:.2f}%")

        return {
            "name": "5日涨跌幅",
            "score": score,
            "sum_score": 10
        }