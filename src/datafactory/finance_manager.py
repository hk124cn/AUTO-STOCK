import os

import akshare as ak
import pandas as pd

from src.datafactory.data_manager import FINANCE_PATH, normalize_code

os.makedirs(FINANCE_PATH, exist_ok=True)


def update_finance(code):
    code = normalize_code(code)
    file_path = os.path.join(FINANCE_PATH, f"{code}.csv")

    if os.path.exists(file_path):
        local = pd.read_csv(file_path)
        if "公告日期" in local.columns:
            local["公告日期"] = pd.to_datetime(local["公告日期"], errors="coerce")
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

    if "公告日期" in df.columns:
        df["公告日期"] = pd.to_datetime(df["公告日期"], errors="coerce")
        new_date = df["公告日期"].max()
    else:
        new_date = None

    if last_date is None or (new_date is not None and new_date > last_date):
        df.to_csv(file_path, index=False)
        return df

    return local
