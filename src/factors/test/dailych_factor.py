import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

# ==============================
# 趋势判断
# ==============================
def get_trend_status(close_prices):
    ma_short = close_prices.rolling(5).mean()
    ma_long = close_prices.rolling(20).mean()
    def generate_stock_pool():
        df = ak.stock_info_a_code_name()
        df = df[~df["code"].str.startswith(("8", "4"))]  # 可过滤北交所
        df.to_csv("stock_trend.csv", index=False)
    trend_strength = (ma_short - ma_long) / ma_long

    if trend_strength.iloc[-1] > 0.05:
        return "strong_up"
    elif trend_strength.iloc[-1] > 0:
        return "weak_up"
    elif trend_strength.iloc[-1] > -0.05:
        return "weak_down"
    else:
        return "strong_down"


# ==============================
# 单日涨跌幅评分
# ==============================
def trend_aware_change_score(today_change, trend_status, volume_ratio=1.0):
    base_scores = {
        'strong_up': {'ranges': [(-10,-7),(-7,-3),(-3,0),(0,3),(3,7),(7,10)], 'scores':[8,6,4,2,1,0]},
        'weak_up': {'ranges': [(-10,-7),(-7,-3),(-3,0),(0,3),(3,7),(7,10)], 'scores':[7,5,3,4,6,3]},
        'weak_down': {'ranges': [(-10,-7),(-7,-3),(-3,0),(0,3),(3,7),(7,10)], 'scores':[6,4,2,5,7,8]},
        'strong_down': {'ranges': [(-10,-7),(-7,-3),(-3,0),(0,3),(3,7),(7,10)], 'scores':[9,7,3,6,8,9]}
    }

    config = base_scores[trend_status]
    base_score = 5
    for (low, high), score in zip(config['ranges'], config['scores']):
        if low <= today_change < high:
            base_score = score
            break

    volume_factor = 1.0
    if volume_ratio > 1.5:
        if (trend_status in ['strong_down','weak_down'] and today_change > 3) or \
           (trend_status in ['strong_up'] and today_change < -3):
            volume_factor = 1.2

    if abs(today_change) > 9.5:
        if trend_status == 'strong_down' and today_change > 9:
            base_score = 10
        elif trend_status == 'strong_up' and today_change < -9:
            base_score = 1

    final_score = min(10, max(0, base_score * volume_factor))
    return round(final_score)


# ==============================
# 获取今日评分（动态最近21日）
# ==============================
def today_score(symbol):
    today = datetime.today()
    start_date = (today - timedelta(days=40)).strftime("%Y%m%d")  # 拉取最近 40 天，确保有交易日 >=21天
    end_date = today.strftime("%Y%m%d")
    print(f"symbol:{symbol}")
    print(f"start_date:{start_date}")
    print(f"end_date:{end_date}")
    df = ak.stock_zh_a_hist(symbol="600660", period="daily",start_date="20251001",end_date="20251022",adjust="qfq")
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
    df = df.sort_values("日期").reset_index(drop=True)

    # 取最后21条数据
    if len(df) < 21:
        print("数据不足21天，无法计算今日评分")
        return
    recent = df.iloc[-21:]

    close_col = '收盘' if '收盘' in df.columns else 'close'
    volume_col = '成交量' if '成交量' in df.columns else 'volume'

    today_change = (recent[close_col].iloc[-1] - recent[close_col].iloc[-2]) / recent[close_col].iloc[-2] * 100
    trend_status = get_trend_status(recent[close_col])
    volume_ratio = recent[volume_col].iloc[-1] / recent[volume_col].rolling(20).mean().iloc[-1] if volume_col in recent.columns else 1.0

    score = trend_aware_change_score(today_change, trend_status, volume_ratio)
    print(f"今日评分 ({symbol}): {score}/10")


# ==============================
# 获取任意目标日评分
# ==============================
def target_day_score(symbol, target_date):
    # target_date: "YYYY-MM-DD"
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    start_date = (target_dt - timedelta(days=40)).strftime("%Y%m%d")
    end_date = target_dt.strftime("%Y%m%d")

    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
    df = df.sort_values("日期").reset_index(drop=True)

    # 找到目标日索引
    idx = df.index[df["日期"] == target_dt.strftime("%Y%m%d")].tolist()
    if not idx:
        print(f"{target_date} 没有交易数据")
        return
    idx = idx[0]

    if idx < 20:
        print("目标日之前数据不足20天，无法计算评分")
        return

    recent = df.iloc[idx-20:idx+1]  # 前20天 + 目标日 = 21条
    close_col = '收盘' if '收盘' in df.columns else 'close'
    volume_col = '成交量' if '成交量' in df.columns else 'volume'

    today_change = (recent[close_col].iloc[-1] - recent[close_col].iloc[-2]) / recent[close_col].iloc[-2] * 100
    trend_status = get_trend_status(recent[close_col])
    volume_ratio = recent[volume_col].iloc[-1] / recent[volume_col].rolling(20).mean().iloc[-1] if volume_col in recent.columns else 1.0

    score = trend_aware_change_score(today_change, trend_status, volume_ratio)
    print(f"{target_date}评分 ({symbol}): {score}/10")


# ==============================
# 测试
# ==============================
if __name__ == "__main__":
    symbol = "600660"
    today_score(symbol)
    #target_day_score(symbol, "2026-02-24")