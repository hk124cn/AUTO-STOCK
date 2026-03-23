import copy

import pandas as pd

from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_finance, normalize_code


FIELDS = ["报告期", "净利润同比增长率", "扣非净利润同比增长率", "营业总收入同比增长率"]


def score_single_item(growth_rates, full_score):
    last_last, last, current = growth_rates
    rate = current
    base_score = full_score * min(rate / 50, 1)

    if rate < 0:
        penalty = max(rate / 10 * (full_score * 0.2), -full_score)
        base_score += penalty

    trend_score = 0
    if current > last > last_last:
        trend_score = 0.2 * full_score
    elif current < last < last_last:
        trend_score = -0.2 * full_score

    trend_score = max(min(trend_score, 0.2 * full_score), -0.2 * full_score)
    total = base_score + trend_score
    total = max(min(total, full_score), -full_score)
    return round(total, 2), round(trend_score, 2)


def calc_total_score(data):
    scores = {}
    scores["扣非净利润"] = score_single_item(data["扣非净利润同比增长率"], 10)
    scores["归母净利润"] = score_single_item(data["归母净利润同比增长率"], 5)
    scores["营业收入"] = score_single_item(data["营业总收入同比增长率"], 5)
    total = sum([s[0] for s in scores.values()])
    return max(min(total, 20), -10)


def _to_float(v):
    try:
        return float(str(v).replace("%", "").strip())
    except Exception:
        return 0.0


def _window(df, p_flg):
    if p_flg == 1:
        return df[FIELDS].tail(3)
    if p_flg == 2:
        return df[FIELDS].iloc[-4:-1]
    return df[FIELDS].iloc[-5:-2]


def js_score(gpcode, p_flg):
    code = normalize_code(gpcode)
    df = get_finance(code)
    if df is None or df.empty or not all(f in df.columns for f in FIELDS):
        return 0

    df_selected = _window(df, p_flg).copy()
    if len(df_selected) < 3:
        return 0

    for col in ["净利润同比增长率", "扣非净利润同比增长率", "营业总收入同比增长率"]:
        df_selected[col] = df_selected[col].map(_to_float)

    data = {
        "扣非净利润同比增长率": list(df_selected["扣非净利润同比增长率"]),
        "归母净利润同比增长率": list(df_selected["净利润同比增长率"]),
        "营业总收入同比增长率": list(df_selected["营业总收入同比增长率"]),
    }

    return calc_total_score(data)


class FinancialFactor(BaseFactor):
    def __init__(self, code, name=None):
        super().__init__(code, name)

    def calculate(self):
        score = round(js_score(self.code, 1), 2)
        return {"name": "财报", "score": score, "sum_score": 20}
