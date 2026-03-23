import math

from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_attention
import src.utils


def calc_focus_score(df, market_change):
    mean_focus = df["用户关注指数"].mean()
    std_focus = df["用户关注指数"].std()

    base_score = (mean_focus - 80) / 2 - std_focus / 4 + market_change / 10
    base_score = max(0, min(7, base_score))

    if mean_focus < 85 and std_focus < 3:
        stable_bonus = 2.5 - (std_focus / 3)
    else:
        stable_bonus = 0

    final_score = base_score + stable_bonus
    final_score = round(min(10, max(1, final_score)), 1)
    return final_score


def js_score(code, refresh=False):
    df = get_attention(code, refresh=refresh)
    if df is None or df.empty or "用户关注指数" not in df.columns:
        return 0

    df["用户关注指数"] = df["用户关注指数"].astype(float)
    market_change = src.utils.get_market_change()
    return calc_focus_score(df.tail(min(20, len(df))), market_change)


class attentionFactor(BaseFactor):
    def __init__(self, code, name=None):
        super().__init__(code, name)

    def calculate(self):
        score = js_score(self.code)
        return {"name": "关注度", "score": score, "sum_score": 10}
