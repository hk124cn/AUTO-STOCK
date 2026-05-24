from src.data_fetcher import get_stock_basic, get_price_change, get_financials
import pandas as pd

def filter_stocks():
    basics = get_stock_basic()
    fin = get_financials()

    # 合并基本信息和财务指标
    df = basics.merge(fin, on="ts_code", how="left")

    # 先按市净率和ROE过滤
    df = df[
        (df['pb'] >= 0.6) & (df['pb'] <= 1.6) &
        (df['roe'] >= 1) & (df['roe'] <= 7)
    ]

    # 计算过去两年的涨跌幅
    results = []
    for _, row in df.iterrows():
        change = get_price_change(row['ts_code'])
        if change is not None and change < 0:  # 过去两年下跌
            results.append(row)

    return pd.DataFrame(results)
