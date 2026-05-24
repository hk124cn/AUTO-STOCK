from data_fetcher import get_daily_prices

def backtest(ts_codes, start_date, end_date):
    """
    简单回测：计算每支股票在选股后期间的涨跌幅
    """
    results = {}
    for code in ts_codes:
        df = get_daily_prices(code, start_date, end_date)
        if not df.empty:
            returns = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]
            results[code] = returns
    return results
