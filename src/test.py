import akshare as ak
import pandas as pd


class DividendYieldFactor:

    def __init__(self):
        self.max_score = 10

    # ===== 对外主接口 =====
    def get_score(self, stock_code: str, date: str = None):
        """
        获取评分
        :param stock_code: 股票代码
        :param date: None=实时，YYYY-MM-DD=历史
        """
        dy = self.get_dividend_yield(stock_code, date)

        if dy is None:
            return 0

        return self._piecewise_linear_score(dy)


    # ===== 股息率主调度 =====
    def get_dividend_yield(self, stock_code: str, date: str = None):

        if date is None:
            return self._get_realtime_dividend_yield(stock_code)
        else:
            return self._get_historical_dividend_yield(stock_code, date)


    # ===== 实时模式 =====
    def _get_realtime_dividend_yield(self, stock_code):

        df = ak.stock_individual_spot_xq(symbol=stock_code)

        if df.empty:
            return None

        # 注意根据实际字段调整
        if "dividend_yield" in df.columns:
            return float(df["dividend_yield"].iloc[0]) / 100
        else:
            return None


    # ===== 回测模式 =====
    def _get_historical_dividend_yield(self, stock_code, date):

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
    def _piecewise_linear_score(self, dy):

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
