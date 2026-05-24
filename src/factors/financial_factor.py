import copy

import pandas as pd

from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_finance, normalize_code


FIELDS = ["报告期", "净利润同比增长率", "扣非净利润同比增长率", "营业总收入同比增长率"]


def score_single_item(growth_rates, full_score, max_negative_score):
    """
    评分逻辑：
    1. 正增长：40%增长=满分(full_score)，不/10
    2. 负增长：max_negative_score×(rate/100)，然后/10转换
    3. 趋势评分：综合计算环比变化趋势
    """
    last_last, last, current = growth_rates
    rate = current

    # 1. 基础评分
    if rate >= 0:
        # 正增长：40%增长=满分，不/10
        base_score = full_score * min(rate / 40, 1)
    else:
        # 负增长：原始分 = max_negative_score × (rate/100)，然后/10转换
        # max_negative_score是正数如50，结果是负数
        raw_score = -max_negative_score * (rate / 100)  # rate是负数，所以结果为负
        base_score = raw_score / 10

    # 2. 趋势评分：综合计算
    trend_score = calculate_trend_score(last_last, last, current, full_score)

    total = base_score + trend_score
    return round(total, 2), round(trend_score, 2)


def calculate_trend_score(last_last, last, current, full_score):
    """
    趋势评分计算：
    - 连续增长/下降（同向趋势）
    - V型反转（从负转正）
    - 倒V反转（从正转负）
    - 波动中上升/下降
    """
    # 环比变化
    change1 = current - last   # 本季跟上季比
    change2 = last - last_last  # 上季跟上上季比
    avg_change = (change1 + change2) / 2  # 平均变化

    trend_score = 0

    # 模式1：连续同向变化（连续增长或连续下降）
    if current > last > last_last:
        trend_score = 0.075 * full_score  # 连续增长 (7.5%)
    elif current < last < last_last:
        trend_score = -0.075 * full_score  # 连续下降 (-7.5%)

    # 模式2：V型反转（从负转到正，或负得少→正得多）
    elif last_last < 0 and current > 0 and current > last:
        # 从负转正，趋势向好
        trend_score = 0.05 * full_score  # 5%

    # 模式3：倒V反转（从正转到负，或正得多→负得少）
    elif last_last > 0 and current < 0 and current < last:
        # 从正转负，趋势向下
        trend_score = -0.05 * full_score  # -5%

    # 模式4：基于平均变化幅度
    # 如果平均变化 > 5%，表示整体向上
    elif avg_change > 5:
        trend_score = 0.05 * full_score  # 5%
    # 如果平均变化 < -5%，表示整体向下
    elif avg_change < -5:
        trend_score = -0.05 * full_score  # -5%

    # 限制趋势评分范围 ±10%
    max_trend = 0.1 * full_score
    trend_score = max(min(trend_score, max_trend), -max_trend)

    return trend_score


def calc_total_score(data):
    """
    计算总分
    - 扣非(50%权重): 正增长满分10分，负增长封顶-50分→/10
    - 归母(25%权重): 正增长满分5分，负增长封顶-25分→/10
    - 营收(25%权重): 正增长满分5分，负增长封顶-25分→/10
    - 趋势分单独加
    """
    # 获取当前同比
    koufei_rate = data["扣非净利润同比增长率"][2]
    guimu_rate = data["归母净利润同比增长率"][2]
    yingshou_rate = data["营业总收入同比增长率"][2]

    # 计算基础分（不含趋势）
    # 扣非：正增长满分10分，负增长封顶-50分
    if koufei_rate >= 0:
        koufei_base = 10 * min(koufei_rate / 40, 1)  # 正增长不/10
    else:
        koufei_base = 50 * (koufei_rate / 100) / 10  # 负增长/10，rate是负数所以结果为负

    # 归母：正增长满分5分，负增长封顶-25分
    if guimu_rate >= 0:
        guimu_base = 5 * min(guimu_rate / 40, 1)
    else:
        guimu_base = 25 * (guimu_rate / 100) / 10

    # 营收：正增长满分5分，负增长封顶-25分
    if yingshou_rate >= 0:
        yingshou_base = 5 * min(yingshou_rate / 40, 1)
    else:
        yingshou_base = 25 * (yingshou_rate / 100) / 10

    base_total = koufei_base + guimu_base + yingshou_base

    # 计算趋势分
    koufei = score_single_item(data["扣非净利润同比增长率"], 10, -50)
    guimu = score_single_item(data["归母净利润同比增长率"], 5, -25)
    yingshou = score_single_item(data["营业总收入同比增长率"], 5, -25)
    trend_total = koufei[1] + guimu[1] + yingshou[1]

    # 最终评分 = 基础分 + 趋势分
    total = base_total + trend_total

    # 限制范围
    total = max(min(total, 20), -10)

    # 返回总分和各分项得分（含详细数据）
    detail_scores = {
        "扣非净利润": {
            "total": round(koufei[0], 2),
            "trend": round(koufei[1], 2)
        },
        "归母净利润": {
            "total": round(guimu[0], 2),
            "trend": round(guimu[1], 2)
        },
        "营业收入": {
            "total": round(yingshou[0], 2),
            "trend": round(yingshou[1], 2)
        }
    }
    return round(total, 2), detail_scores


def _to_float(v):
    try:
        return float(str(v).replace("%", "").strip())
    except Exception:
        return 0.0


def _window(df, p_flg):
    """
    根据p_flg取数窗口（用于计算最近3个季度的同比趋势评分）

    参数:
        df: 按时间正序排列的财务数据DataFrame
        p_flg: 1=本季度, 2=上季度, 0=上上季度

    返回:
        取对应的3个季度数据进行评分计算

    示例（假设数据最后3行: 2025-06, 2025-09, 2025-12）:
        p_flg=1: tail(3)     → [2025-06, 2025-09, 2025-12] 用于计算2025-12的评分
        p_flg=2: iloc[-4:-1] → [2025-03, 2025-06, 2025-09] 用于计算2025-09的评分
        p_flg=0: iloc[-5:-2] → [2024-12, 2025-03, 2025-06] 用于计算2025-06的评分
    """
    if p_flg == 1:
        return df[FIELDS].tail(3)
    if p_flg == 2:
        return df[FIELDS].iloc[-4:-1]
    return df[FIELDS].iloc[-5:-2]


def js_score(gpcode, p_flg):
    code = normalize_code(gpcode)
    df = get_finance(code)
    if df is None or df.empty or not all(f in df.columns for f in FIELDS):
        return 0, {}

    df_selected = _window(df, p_flg).copy()
    if len(df_selected) < 3:
        return 0, {}

    for col in ["净利润同比增长率", "扣非净利润同比增长率", "营业总收入同比增长率"]:
        df_selected[col] = df_selected[col].map(_to_float)

    data = {
        "扣非净利润同比增长率": list(df_selected["扣非净利润同比增长率"]),
        "归母净利润同比增长率": list(df_selected["净利润同比增长率"]),
        "营业总收入同比增长率": list(df_selected["营业总收入同比增长率"]),
    }

    total, detail = calc_total_score(data)
    return total, detail


class FinancialFactor(BaseFactor):
    def __init__(self, code, name=None):
        super().__init__(code, name)

    def calculate(self):
        score, detail = js_score(self.code, 1)
        return {"name": "财报", "score": round(score, 2), "detail": detail, "sum_score": 20}
