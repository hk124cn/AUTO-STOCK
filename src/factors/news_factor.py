import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from src.core.base_factor import BaseFactor


class NewsFactor(BaseFactor):

    def __init__(self, code, name, target_date=None):
        super().__init__(code, name)
        self.target_date = target_date or datetime.today().strftime("%Y-%m-%d")


    def get_news(self):
        """
        获取个股新闻
        """
        df = ak.stock_news_em(symbol=self.code)
        if df.empty:
            return pd.DataFrame()

        df["发布时间"] = pd.to_datetime(df["发布时间"])
        return df


    def filter_before_date(self, df):
        """
        严格过滤未来函数
        """
        target_dt = pd.to_datetime(self.target_date)
        return df[df["发布时间"] <= target_dt]


    def calculate_score(self, df):
        """
        计算新闻评分
        """

        target_dt = pd.to_datetime(self.target_date)

        recent_3 = df[df["发布时间"] >= target_dt - timedelta(days=3)]
        prev_3 = df[
            (df["发布时间"] < target_dt - timedelta(days=3)) &
            (df["发布时间"] >= target_dt - timedelta(days=6))
        ]

        score = 0

        # -------- 数量评分 --------
        if len(recent_3) >= 5:
            score += 4
        elif len(recent_3) >= 3:
            score += 2

        # -------- 加速评分 --------
        if len(prev_3) > 0:
            acceleration = (len(recent_3) - len(prev_3)) / len(prev_3)
            if acceleration > 1:
                score += 3
            elif acceleration > 0.5:
                score += 2

        # -------- 关键词评分 --------
        keywords = ["重组", "并购", "中标", "定增", "算力", "AI"]

        keyword_hit = recent_3["新闻标题"].apply(
            lambda x: any(k in str(x) for k in keywords)
        ).sum()

        if keyword_hit >= 2:
            score += 3
        elif keyword_hit >= 1:
            score += 1.5

        return min(10, round(score, 1))


    def calculate(self):

        news_df = self.get_news()
        if news_df.empty:
            return {
                "name": "新闻热度评分",
                "score": 0,
                "sum_score": 10
            }

        news_df = self.filter_before_date(news_df)

        score = self.calculate_score(news_df)

        return {
            "name": "新闻",
            "score": score,
            "sum_score": 10
        }
