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
    """获取股票历史数据（兼容日期列名 & 修复日期格式+代码前缀）"""
    try:
        # 日期格式转换（去掉横杠，改为YYYYMMDD）
        start_fmt = start_date.replace("-", "")
        end_fmt = end_date.replace("-", "")

        df = ak.stock_zh_a_hist(
            symbol=stock_code,  # 这里要传带sh/sz的完整代码
            period="daily",
            start_date=start_fmt,
            end_date=end_fmt,
            adjust="qfq"
        )

        # 打印列名（调试用）
        print(f"{stock_code} 数据列名：{df.columns.tolist()}")

        if df.empty:
            print(f"⚠️ {stock_code} 无数据，检查代码/日期")
            return pd.DataFrame()

        # ---- 日期列兼容处理 ----
        if "日期" in df.columns:
            date_col = "日期"
        elif "date" in df.columns:
            date_col = "date"
        elif "trade_date" in df.columns:
            date_col = "trade_date"
        else:
            raise ValueError(f"{stock_code} 未找到日期列: {df.columns}")

        df[date_col] = pd.to_datetime(df[date_col])
        df = df.rename(columns={date_col: "日期"})

        # ---- 确保有收盘价 ----
        if "收盘" not in df.columns:
            raise ValueError(f"{stock_code} 缺少收盘列: {df.columns}")

        df = df.sort_values("日期").set_index("日期")
        return df[["收盘"]]

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
        change_5d = (last5["收盘"].iloc[-1] - last5["收盘"].iloc[0]) / last5["收盘"].iloc[0] * 100

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
    stock_list = pd.read_csv(stock_pool_file, dtype={"code": str})
    index_df = get_index_data(start_date, end_date)

    results = []
    for _, row in stock_list.iterrows():
        raw_code = str(row["code"]).strip()
        if len(raw_code) != 6:
            print(f"❌ {raw_code} 不是6位代码，跳过")
            continue

        stock_df = get_stock_data(raw_code, start_date, end_date)
        if stock_df.empty:
            continue

        for date in stock_df.index:
            if date not in index_df.index:
                continue
            s = score_stock_on_date(stock_df, index_df, date)
            if s is not None:
                results.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "code": raw_code,
                    "name": row["name"],
                    "score": s
                })

    # 转 DataFrame 并保存
    df_results = pd.DataFrame(results)
    df_results.to_csv(output_file, index=False, encoding="utf-8-sig")

    # 打印前几条结果，方便调试
    print("前几条回测结果预览：")
    print(df_results.head(5))

    print(f"✅ 回测完成，结果保存至 {output_file}")

if __name__ == "__main__":
    backtest("/data/data/com.termux/files/home/AUTO-STOCK/stock_pool.csv",
             "2025-08-01", "2025-09-10")
