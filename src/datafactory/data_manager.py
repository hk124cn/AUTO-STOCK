import os
from datetime import datetime

import akshare as ak
import pandas as pd

DATA_DIR = "data"
PRICE_PATH = os.path.join(DATA_DIR, "price")
FINANCE_PATH = os.path.join(DATA_DIR, "finance")
DIVIDEND_PATH = os.path.join(DATA_DIR, "dividend")
ATTENTION_PATH = os.path.join(DATA_DIR, "attention")
NEWS_PATH = os.path.join(DATA_DIR, "news")


for path in [PRICE_PATH, FINANCE_PATH, DIVIDEND_PATH, ATTENTION_PATH, NEWS_PATH]:
    os.makedirs(path, exist_ok=True)


def normalize_code(code: str) -> str:
    return str(code).split(".")[0].zfill(6)


def _read_csv_if_exists(file_path):
    if not os.path.exists(file_path):
        return None
    return pd.read_csv(file_path)


def get_price(code):
    code = normalize_code(code)
    file_path = os.path.join(PRICE_PATH, f"{code}.csv")
    return _read_csv_if_exists(file_path)


def get_finance(code, refresh=False):
    code = normalize_code(code)
    file_path = os.path.join(FINANCE_PATH, f"{code}.csv")

    if not refresh:
        local = _read_csv_if_exists(file_path)
        if local is not None and not local.empty:
            return local

    try:
        remote = ak.stock_financial_abstract_ths(symbol=code, indicator="按单季度")
    except Exception:
        return _read_csv_if_exists(file_path)

    if remote is None or remote.empty:
        return _read_csv_if_exists(file_path)

    remote.to_csv(file_path, index=False)
    return remote


def get_dividend(code, refresh=False):
    code = normalize_code(code)
    file_path = os.path.join(DIVIDEND_PATH, f"{code}.csv")

    local = _read_csv_if_exists(file_path)
    if not refresh and local is not None and not local.empty:
        return local

    try:
        remote = ak.stock_dividents_cninfo(symbol=code)
    except Exception:
        return local

    if remote is None or remote.empty:
        return local

    remote.to_csv(file_path, index=False)
    return remote


def get_attention(code, refresh=False):
    code = normalize_code(code)
    file_path = os.path.join(ATTENTION_PATH, f"{code}.csv")

    local = _read_csv_if_exists(file_path)
    if not refresh and local is not None and not local.empty:
        return local

    try:
        remote = ak.stock_comment_detail_scrd_focus_em(symbol=code)
    except Exception:
        return local

    if remote is None or remote.empty:
        return local

    remote.to_csv(file_path, index=False)
    return remote


def get_news(code, refresh=False):
    code = normalize_code(code)
    day = datetime.today().strftime("%Y%m%d")
    file_path = os.path.join(NEWS_PATH, f"{code}_{day}.csv")

    if not refresh:
        local = _read_csv_if_exists(file_path)
        if local is not None and not local.empty:
            return local

    try:
        remote = ak.stock_news_em(symbol=code)
    except Exception:
        local = _read_csv_if_exists(file_path)
        if local is not None:
            return local

        # fallback to latest historical news cache
        candidates = sorted(
            f for f in os.listdir(NEWS_PATH) if f.startswith(f"{code}_") and f.endswith(".csv")
        )
        if not candidates:
            return None
        return pd.read_csv(os.path.join(NEWS_PATH, candidates[-1]))

    if remote is None or remote.empty:
        return _read_csv_if_exists(file_path)

    remote.to_csv(file_path, index=False)
    return remote
