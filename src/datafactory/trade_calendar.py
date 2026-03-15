import akshare as ak
import pandas as pd
import os

PATH = "/root/AUTO-STOCK/data/calendar/trade_days.csv"


def init_trade_calendar():

    if os.path.exists(PATH):
        print("已存在")
        return

    print("开始下载")
    df = ak.tool_trade_date_hist_sina()

    os.makedirs("/root/AUTO-STOCK/data/calendar/", exist_ok=True)

    df.to_csv(PATH, index=False)
    print("完成")


def is_trade_day():

    df = pd.read_csv(PATH)

    today = pd.Timestamp.today().strftime("%Y-%m-%d")

    return today in df["trade_date"].values

if __name__ == "__main__":
    init_trade_calendar()