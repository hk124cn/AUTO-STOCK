from data_fetcher import get_daily_prices
import pandas as pd

def track_stocks(stock_list, start_date, end_date, filename="stock_prices.csv"):
    all_prices = []
    for ts_code in stock_list:
        df = get_daily_prices(ts_code, start_date, end_date)
        if not df.empty:
            df['ts_code'] = ts_code
            all_prices.append(df[['ts_code', 'trade_date', 'close']])
    if all_prices:
        result = pd.concat(all_prices)
        result.to_csv(filename, index=False)
        return result
    else:
        return pd.DataFrame()
