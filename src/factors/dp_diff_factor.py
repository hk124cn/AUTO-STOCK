import akshare as ak
import pandas as pd
import time
from src.core.base_factor import BaseFactor
import src.utils

index_ret = None

def get_stock_ytd_return(code):
    s_code = src.utils.format_code(code)
    start_day,end_day = src.utils.getdate()
    try:
        df = ak.stock_zh_a_hist_tx(symbol=s_code, start_date=start_day, end_date=end_day, adjust="qfq")
        #df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_day, end_date=end_day, adjust="qfq")
    except Exception as e:
        print("接口异常",e)
        time.sleep(1)
        return 0
    if df.empty or len(df) < 2:
        print(f"⚠️ {code} 数据不足")
        return 0

    start_price = df.iloc[0]["close"]
    latest_price = df.iloc[-1]["close"]

    return (latest_price / start_price - 1) * 100

"""
def get_index_ytd_return():
    global INDEX_YTD_CACHE

    if INDEX_YTD_CACHE is not None:
        return INDEX_YTD_CACHE

    start_day,end_day = src.utils.getdate()
    print(f"start:{start_day},end:{end_day}")
    try:
        df = ak.stock_zh_a_daily(symbol="sh000001", start_date=start_day, end_date=end_day, adjust="qfq")
    except Exception as e:
        print("接口异常2",e)
        time.sleep(1)
        return 0

    if df.empty or len(df) < 2:
        print(f"⚠️ sh000001 数据不足")
        return 0

    start_price = df.iloc[0]["close"]
    latest_price = df.iloc[-1]["close"]
 
    INDEX_YTD_CACHE = (latest_price / start_price - 1) * 100
    return INDEX_YTD_CACHE
"""

class RelativeStrengthFactor(BaseFactor):

    weight = 10

    def calculate(self):
        global index_ret
        stock_ret = get_stock_ytd_return(self.code)
        if index_ret is None:
            index_ret = src.utils.get_market_change()
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