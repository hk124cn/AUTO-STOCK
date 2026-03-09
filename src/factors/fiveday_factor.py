import akshare as ak
import pandas as pd
from src.core.base_factor import BaseFactor
import src.utils

def get_5day_return(code):
    try:
        s_code = src.utils.format_code(code)
        start_day,end_day = src.utils.getdate()
        df = ak.stock_zh_a_hist_tx(symbol=s_code, start_date=start_day, end_date=end_day, adjust="qfq")
    except Exception as e:
        print("5日行情接口异常",e)
        return 0
    if len(df) < 6:
        print("5日行情数量不足")
        return 0

    df = df.tail(6)

    start_price = df.iloc[0]["close"]
    end_price = df.iloc[-1]["close"]

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