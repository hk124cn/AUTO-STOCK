import os

import pandas as pd

from src.datafactory.data_manager import PRICE_PATH, normalize_code

MARKET_PATHS = ("data/daily_market", "data/market_daily")


def _resolve_market_path(paths=MARKET_PATHS):
    return next((path for path in paths if os.path.isdir(path)), None)


def build_price():
    os.makedirs(PRICE_PATH, exist_ok=True)

    market_path = _resolve_market_path()
    if market_path is None:
        raise FileNotFoundError(
            "未找到日行情目录，请确认以下任一路径存在: " + ", ".join(MARKET_PATHS)
        )

    files = sorted(file for file in os.listdir(market_path) if file.endswith(".csv"))

    for filename in files:
        path = os.path.join(market_path, filename)
        df = pd.read_csv(path)

        for _, row in df.iterrows():
            code = normalize_code(row["代码"])
            stock_path = os.path.join(PRICE_PATH, f"{code}.csv")

            new_row = pd.DataFrame(
                [{"日期": row["日期"], "收盘": row["最新价"], "成交额": row.get("成交额", None)}]
            )

            if os.path.exists(stock_path):
                old = pd.read_csv(stock_path)
                old = pd.concat([old, new_row], ignore_index=True)
                old = old.drop_duplicates("日期")
                old = old.sort_values("日期")
                old.to_csv(stock_path, index=False)
            else:
                new_row.to_csv(stock_path, index=False)
