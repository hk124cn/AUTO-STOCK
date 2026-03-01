import akshare as ak
import pandas as pd
from src.core.base_factor import BaseFactor

def format_code(code: str) -> str:
    """补全交易所前缀（如sh/sz）"""
    if code.startswith(("sh", "sz")):      # 如果已有前缀则直接返回
        return code
    elif code.startswith("6"):             # 上海市场代码以6开头
        return "sh" + code                  # 添加sh前缀
    else:                                   # 默认视为深圳市场
        return "sz" + code                  # 添加sz前缀

# ===== 股息率主调度 =====
def get_dividend_yield(stock_code: str, date: str = None):

    if date is None:
        print("股息率实时评分模式")
        return _get_realtime_dividend_yield(stock_code)
    else:
        print("股息率回测评分模式")
        return _get_historical_dividend_yield(stock_code, date)


# ===== 实时模式 =====
def _get_realtime_dividend_yield(stock_code):
    s_code = format_code(stock_code)
    df = ak.stock_individual_spot_xq(symbol=s_code)
   # print(df)

    if df.empty:
        print("股息率(TTM)未找到")
        return None

    # 注意根据实际字段调整
    dividend_row = df[df['item'].str.contains('股息率', na=False)]  
    if dividend_row['value'].iloc[0] == None:
        dividend_value = 0
    else:
        dividend_value = float(dividend_row['value'].iloc[0])
    print(f"股息率：{dividend_value}")
    return float(dividend_value / 100)


# ===== 回测模式 =====
def _get_historical_dividend_yield(stock_code, date):

    target_date = pd.to_datetime(date)

    # 1. 获取当日价格
    price_df = ak.stock_zh_a_hist(
        symbol=stock_code,
        period="daily",
        start_date=date,
        end_date=date,
        adjust=""
    )

    if price_df.empty:
        return None

    price = price_df["收盘"].iloc[0]

    # 2. 获取分红数据
    div_df = ak.stock_dividents_cninfo(symbol=stock_code)

    if div_df.empty:
        return 0

    div_df["除权日"] = pd.to_datetime(div_df["除权日"])

    one_year_before = target_date - pd.Timedelta(days=365)

    recent_div = div_df[
        (div_df["除权日"] <= target_date) &
        (div_df["除权日"] > one_year_before)
    ]

    if recent_div.empty:
        return 0

    # 派息通常是每10股派X元
    recent_div["每股分红"] = recent_div["派息"] / 10

    total_dividend = recent_div["每股分红"].sum()

    return total_dividend / price


# ===== 分段线性评分 =====
def _piecewise_linear_score(dy):

    # 关键点
    points = [
        (0.00, 0),
        (0.02, 4),
        (0.05, 8),
        (0.08, 10),
        (0.10, 10)
    ]

    # 超过上限
    if dy >= 0.10:
        return 10

    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]

        if x1 <= dy <= x2:
            # 线性插值公式
            score = y1 + (dy - x1) * (y2 - y1) / (x2 - x1)
            return round(score, 2)

    return 0


def js_score(code: str, date: str = None):
    """
    获取评分
    :param stock_code: 股票代码
    :param date: None=实时,YYYY-MM-DD=历史
    """
    dy = get_dividend_yield(code, date)
    if dy is None:
        print("股息率评分获取失败")
        return 0

    return _piecewise_linear_score(dy)


class dividendfactor(BaseFactor):
    def __init__(self,code,name):
        super().__init__(code,name)

    def calculate(self):
        score = js_score(self.code)
       # sum_score = 10
        return{
            "name":"股息率",
            "score":score,
            "sum_score":10
        }         
