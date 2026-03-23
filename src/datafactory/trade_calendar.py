import os

import akshare as ak
import pandas as pd

PATH = "data/calendar/trade_days.csv"


def init_trade_calendar(force=False):
    if os.path.exists(PATH) and not force:
        print("交易日历已存在")
        return True

    print("开始下载交易日历")
    df = ak.tool_trade_date_hist_sina()

    os.makedirs("data/calendar", exist_ok=True)
    df.to_csv(PATH, index=False)
    print("交易日历下载完成")
    return True


def is_trade_day():
    if not os.path.exists(PATH):
        init_trade_calendar()

    df = pd.read_csv(PATH)
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    return today in df["trade_date"].astype(str).values


if __name__ == "__main__":
    init_trade_calendar()
