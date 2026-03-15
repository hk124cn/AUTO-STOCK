import pandas as pd
import os

MARKET_PATH = "data/market_daily"
PRICE_PATH = "data/price"

os.makedirs(PRICE_PATH, exist_ok=True)


def build_price():

    files = sorted(os.listdir(MARKET_PATH))

    for f in files:

        path = f"{MARKET_PATH}/{f}"

        df = pd.read_csv(path)

        for _, row in df.iterrows():

            code = row["代码"]

            stock_path = f"{PRICE_PATH}/{code}.csv"

            new_row = pd.DataFrame([{
                "日期": row["日期"],
                "收盘": row["最新价"],
                "成交额": row["成交额"]
            }])

            if os.path.exists(stock_path):

                old = pd.read_csv(stock_path)

                old = pd.concat([old, new_row])

                old = old.drop_duplicates("日期")

                old.to_csv(stock_path, index=False)

            else:

                new_row.to_csv(stock_path, index=False)