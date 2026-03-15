import akshare as ak
import pandas as pd
import os
import time

PATH = "data/finance"

os.makedirs(PATH, exist_ok=True)


def update_finance(code):

    file = f"{PATH}/{code}.csv"

    if os.path.exists(file):

        local = pd.read_csv(file)

        if "公告日期" in local.columns:

            local["公告日期"] = pd.to_datetime(local["公告日期"])

            last_date = local["公告日期"].max()

        else:

            last_date = None

    else:

        local = None
        last_date = None

    try:

        df = ak.stock_financial_report_sina(symbol=code)

    except Exception:

        return local

    if df is None or df.empty:
        return local

    df["公告日期"] = pd.to_datetime(df["公告日期"])

    new_date = df["公告日期"].max()

    if last_date is None or new_date > last_date:

        print(f"{code} 财报更新")

        df.to_csv(file, index=False)

        return df

    return local