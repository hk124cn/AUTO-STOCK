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
        # 使用当天23:59:59确保当天新闻不被过滤
        end_of_day = target_dt.replace(hour=23, minute=59, second=59)
        return df[df["发布时间"] <= end_of_day]

    def calculate_score(self, df):
        # 使用当天23:59:59确保当天新闻不被过滤
        target_dt = pd.to_datetime(self.target_date).replace(hour=23, minute=59, second=59)
        recent_3 = df[df["发布时间"] >= target_dt - timedelta(days=3)]
        prev_3 = df[
            (df["发布时间"] < target_dt - timedelta(days=3))
            & (df["发布时间"] >= target_dt - timedelta(days=6))
        ]

        # 情绪过滤：只过滤包含负面关键词的新闻，保留正面和中性新闻
        negative_keywords = ["下跌", "净流出", "出逃", "跌超", "减持", "流出超", "撤离", "爆雷", "风险"]

        def is_negative(title):
            return any(kw in str(title) for kw in negative_keywords)

        # 对recent_3过滤：只保留非负面新闻
        recent_3_filtered = recent_3[~recent_3["新闻标题"].apply(is_negative)] if len(recent_3) > 0 and "新闻标题" in recent_3.columns else pd.DataFrame()
        # 对prev_3也过滤（用于加速比计算）
        prev_3_filtered = prev_3[~prev_3["新闻标题"].apply(is_negative)] if len(prev_3) > 0 and "新闻标题" in prev_3.columns else pd.DataFrame()

        score = 0
        if len(recent_3_filtered) >= 5:
            score += 4
        elif len(recent_3_filtered) >= 3:
            score += 2
        elif len(recent_3_filtered) >= 1:
            score += 1

        if len(prev_3_filtered) > 0:
            acceleration = (len(recent_3_filtered) - len(prev_3_filtered)) / len(prev_3_filtered)
            if acceleration > 1:
                score += 3
            elif acceleration > 0.5:
                score += 2

        keywords = ["重组", "并购", "中标", "定增", "算力", "AI"]
        keyword_hit = sum(1 for x in recent_3_filtered["新闻标题"] if any(k in str(x) for k in keywords)) if len(recent_3_filtered) > 0 and "新闻标题" in recent_3_filtered.columns else 0

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
