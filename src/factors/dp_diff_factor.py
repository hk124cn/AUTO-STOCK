import akshare as ak
import pandas as pd
import time
from datetime import datetime
from src.core.base_factor import BaseFactor

def getdate():
    # 获取今年日期范围
    today = datetime.today()
    year_start = f"{today.year}0101"  # 20260101
    today_str = today.strftime("%Y%m%d")  # 20260219
    return year_start,today_str


def get_stock_ytd_return(code):
    start_day,end_day = getdate()
    df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_day, end_date=end_day, adjust="qfq")

    if df.empty or len(df) < 2:
        print(f"⚠️ {code} 数据不足")
        return 0
    print(df.columns.tolist())
    print(df.head(3))

    start_price = df.iloc[0]["收盘"]
    latest_price = df.iloc[-1]["收盘"]

    return (latest_price / start_price - 1) * 100


def get_index_ytd_return():
    start_day,end_day = getdate()
    df = ak.stock_zh_a_daily(symbol="sh000001", period="daily", start_date=start_day, end_date=end_day, adjust="qfq")

    if df.empty or len(df) < 2:
        print(f"⚠️ {code} 数据不足")
        return 0

    start_price = df.iloc[0]["close"]
    latest_price = df.iloc[-1]["close"]

    return (latest_price / start_price - 1) * 100


class RelativeStrengthFactor(BaseFactor):

    weight = 10

    def calculate(self):

        stock_ret = get_stock_ytd_return(self.code)
        index_ret = get_index_ytd_return()

        relative = stock_ret - index_ret

        # 打分逻辑（0~10分）
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

        print(f"今年个股涨幅: {stock_ret:.2f}%")
        print(f"今年大盘涨幅: {index_ret:.2f}%")
        print(f"相对强弱: {relative:.2f}%")

        return {
            "name": "今年相对大盘强弱",
            "score": score,
            "sum_score": 10
        }