from datetime import datetime, timedelta

import pandas as pd

from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_news


class NewsFactor(BaseFactor):
    def __init__(self, code, name=None, target_date=None):
        super().__init__(code, name)
        self.target_date = target_date or datetime.today().strftime("%Y-%m-%d")

    def get_news(self):
        df = get_news(self.code)
        if df is None or df.empty:
            return pd.DataFrame()

        if "发布时间" in df.columns:
            df["发布时间"] = pd.to_datetime(df["发布时间"])
        return df

    def filter_before_date(self, df):
        target_dt = pd.to_datetime(self.target_date)
        return df[df["发布时间"] <= target_dt]

    def calculate_score(self, df):
        target_dt = pd.to_datetime(self.target_date)
        recent_3 = df[df["发布时间"] >= target_dt - timedelta(days=3)]
        prev_3 = df[
            (df["发布时间"] < target_dt - timedelta(days=3))
            & (df["发布时间"] >= target_dt - timedelta(days=6))
        ]

        score = 0
        if len(recent_3) >= 5:
            score += 4
        elif len(recent_3) >= 3:
            score += 2

        if len(prev_3) > 0:
            acceleration = (len(recent_3) - len(prev_3)) / len(prev_3)
            if acceleration > 1:
                score += 3
            elif acceleration > 0.5:
                score += 2

        keywords = ["重组", "并购", "中标", "定增", "算力", "AI"]
        keyword_hit = recent_3["新闻标题"].apply(lambda x: any(k in str(x) for k in keywords)).sum()

        if keyword_hit >= 2:
            score += 3
        elif keyword_hit >= 1:
            score += 1.5

        return min(10, round(score, 1))

    def calculate(self):
        news_df = self.get_news()
        if news_df.empty or "发布时间" not in news_df.columns or "新闻标题" not in news_df.columns:
            return {"name": "新闻", "score": 0, "sum_score": 10}

        news_df = self.filter_before_date(news_df)
        score = self.calculate_score(news_df)
        return {"name": "新闻", "score": score, "sum_score": 10}
