import akshare as ak
import pandas as pd
import os
import time
from datetime import datetime

PATH = "/root/AUTO-STOCK/data/daily_market"

os.makedirs(PATH, exist_ok=True)


def get_market():

    try:
        print("尝试新浪接口...")
        df = ak.stock_zh_a_spot()
        return df

    except:
        print("新浪失败，尝试东方财富...")
        return ak.stock_zh_a_spot_em()


def download_market():

    today = datetime.today().strftime("%Y%m%d")
    file = f"{PATH}/{today}.csv"

    if os.path.exists(file):
        print("今日行情已存在")
        return

    for i in range(5):

        try:

            df = get_market()

            df["日期"] = today

            df.to_csv(file, index=False)

            print("今日行情下载完成")

            return

        except Exception as e:

            print(f"今日行情下载失败:{i}次", e)

            time.sleep(5)

    print("今日行情下载失败")


if __name__ == "__main__":
    download_market()