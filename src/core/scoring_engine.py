from typing import List, Dict


def aggregate_scores(factors: List[Dict]) -> Dict:
    """把多个因子的 score 和 weight 汇总成总分 0-100 的结构。

    因子返回应包含 'score'（数值，最好已归一化到 0~100 或 0~factor_max）和 'weight'（占比，和为1 或不为1 均可）。
    返回值为：{"total_score": float, "details": factors}
    """
    # 若 weights 没有归一化，先计算权重和
    wsum = sum(f.get('weight', 0) for f in factors)
    if wsum == 0:
        # 没有权重的情况：均等权重
        n = len(factors)
        for f in factors:
            f['_norm_weight'] = 1.0 / n
    else:
        for f in factors:
            f['_norm_weight'] = f.get('weight', 0) / wsum

    total = 0.0
    for f in factors:
        # 假设每个因子返回 score 的量纲为 0-100
        total += f.get('score', 0) * f['_norm_weight']

    return {"total_score": round(total, 2), "details": factors}
