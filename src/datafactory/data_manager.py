import pandas as pd
import os

PRICE_PATH = "data/price"
FINANCE_PATH = "data/finance"
DIVIDEND_PATH = "data/dividend"


def get_price(code):

    file = f"{PRICE_PATH}/{code}.csv"

    if not os.path.exists(file):
        return None

    return pd.read_csv(file)


def get_finance(code):

    file = f"{FINANCE_PATH}/{code}.csv"

    if not os.path.exists(file):
        return None

    return pd.read_csv(file)


def get_dividend(code):

    file = f"{DIVIDEND_PATH}/{code}.csv"

    if not os.path.exists(file):
        return None

    return pd.read_csv(file)