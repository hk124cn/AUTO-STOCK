import akshare as ak
import pandas as pd

def format_code(code: str) -> str:
    """补全交易所前缀"""
    if code.startswith(("sh", "sz")):
        return code
    elif code.startswith("6"):
        return "sh" + code
    else:
        return "sz" + code

def get_stock_data(stock_code, start_date, end_date):
    """获取股票历史数据（修复日期列名问题）"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"  # 前复权
        )
        # 关键：打印列名，确认日期列实际名称（比如可能是"date"而不是"日期"）
        print(f"{stock_code} 的数据列名：{df.columns.tolist()}")
        
        # 根据实际列名修改（假设日期列是"date"，如果是其他名称替换即可）
        date_col = "date"  # 这里替换为打印出的实际日期列名
        if date_col not in df.columns:
            # 保险起见，再尝试常见的列名（比如"trade_date"）
            date_col = "trade_date" if "trade_date" in df.columns else df.columns[0]
        
        # 转换日期格式并统一列名为"日期"
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.rename(columns={date_col: "日期"})
        
        df = df.sort_values("日期").set_index("日期")
        return df[["收盘"]]  # 返回收盘价
    except Exception as e:
        print(f"{stock_code} 数据获取失败：{e}")
        return pd.DataFrame()


def get_index_data(start: str, end: str):
    """获取沪深300指数数据"""
    start_fmt = start.replace("-", "")
    end_fmt = end.replace("-", "")
    df = ak.index_zh_a_hist(symbol="000300", period="daily", start_date=start_fmt, end_date=end_fmt)
    df["日期"] = pd.to_datetime(df["日期"])
    df.set_index("日期", inplace=True)
    return df

def score_stock_on_date(stock_df, index_df, date):
    """计算某股票在某日的评分"""
    weights = {"daily_change": 30, "5d_change": 30, "vs_market": 40}
    score = 0

    if date not in stock_df.index:
        return None

    # --- 单日涨跌幅 ---
    today_close = stock_df.loc[date, "收盘"]
    yesterday_close = stock_df.shift(1).loc[date, "收盘"]
    daily_change = (today_close - yesterday_close) / yesterday_close * 100

    if 2 <= daily_change <= 6:
        score += weights["daily_change"]
    elif 0 <= daily_change < 2 or 6 < daily_change <= 9:
        score += weights["daily_change"] * 0.7
    elif -2 <= daily_change < 0 or daily_change > 9:
        score += weights["daily_change"] * 0.3
    else:
        score += 0

    # --- 连续5日涨跌幅 ---
    idx = stock_df.index.get_loc(date)
    if idx >= 4:
        last5 = stock_df.iloc[idx-4:idx+1]
        change_5d = (last5["收盘"][-1] - last5["收盘"][0]) / last5["收盘"][0] * 100
        if 5 <= change_5d <= 15:
            score += weights["5d_change"]
        elif 0 <= change_5d < 5:
            score += weights["5d_change"] * 0.7
        elif change_5d > 15 or -5 > change_5d >= -10:
            score += weights["5d_change"] * 0.3
        elif change_5d < -10:
            score += 0

    # --- 今年 vs 大盘差值 ---
    stock_ytd = (stock_df.loc[date, "收盘"] - stock_df.iloc[0]["收盘"]) / stock_df.iloc[0]["收盘"] * 100
    index_ytd = (index_df.loc[date, "收盘"] - index_df.iloc[0]["收盘"]) / index_df.iloc[0]["收盘"] * 100
    diff = stock_ytd - index_ytd

    if diff > 20:
        score += weights["vs_market"]
    elif 0 <= diff <= 20:
        score += weights["vs_market"] * (diff / 20)
    elif -20 <= diff < 0:
        score += weights["vs_market"] * 0.25
    else:
        score += 0

    return round(score, 2)

def backtest(stock_pool_file, start_date, end_date, output_file="scores_backtest.csv"):
    stock_list = pd.read_csv(stock_pool_file)
    index_df = get_index_data(start_date, end_date)

    results = []
    for _, row in stock_list.iterrows():
        code, name = str(row["code"]), row["name"]
        stock_df = get_stock_data(code, start_date, end_date)

        for date in stock_df.index:
            if date not in index_df.index:  # 过滤非交易日
                continue
            s = score_stock_on_date(stock_df, index_df, date)
            if s is not None:
                results.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "code": code,
                    "name": name,
                    "score": s
                })

    pd.DataFrame(results).to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ 回测完成，结果保存至 {output_file}")

if __name__ == "__main__":
    backtest("/data/data/com.termux/files/home/AUTO-STOCK/stock_pool.csv",
             "2025-07-01", "2025-08-18")
