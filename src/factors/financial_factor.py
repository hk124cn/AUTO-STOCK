# src/factors/financial_factor.py
from src.core.base_factor import BaseFactor
import akshare as ak
import copy
import sys

class FinancialFactor(BaseFactor):
    """
    财报因子：根据单季度财务数据计算评分
    满分：20分
    """

    def score_single_item(self, growth_rates, full_score):
        """单项得分计算逻辑（保持原逻辑）"""
        last_last, last, current = growth_rates

        # === 基础增长分 ===
        rate = current
        if rate >= 50:
            base_score = full_score
        elif rate >= 30:
            base_score = full_score * 0.8
        elif rate >= 10:
            base_score = full_score * 0.6
        elif rate >= 0:
            base_score = full_score * 0.4
        elif rate >= -10:
            base_score = full_score * 0.2
        else:
            base_score = 0

        # === 负增长额外扣分 ===
        if rate < 0:
            penalty = max(rate / 10 * (full_score * 0.2), -full_score)
            base_score += penalty

        # === 趋势加减分 ===
        trend_score = 0
        if current > last > last_last:
            trend_score = 0.2 * full_score
        elif current < last < last_last:
            trend_score = -0.2 * full_score

        total = base_score + trend_score
        total = max(min(total, full_score), -full_score)

        return round(total, 2), round(trend_score, 2)

    def calc_total_score(self, data):
        """三个财务指标计算综合得分"""
        scores = {}
        scores["扣非净利润"] = self.score_single_item(data["扣非净利润同比增长率"], 10)
        scores["归母净利润"] = self.score_single_item(data["归母净利润同比增长率"], 5)
        scores["营业收入"] = self.score_single_item(data["营业总收入同比增长率"], 5)

        total = sum([s[0] for s in scores.values()])
        trend_adj = sum([s[1] for s in scores.values()])

        return total, trend_adj, scores

    def calculate(self):
        """主流程：拉取数据 + 计算 + 返回结果"""
        try:
            df = ak.stock_financial_abstract_ths(symbol=self.code, indicator="按单季度")
            fields = ["报告期", "净利润同比增长率", "扣非净利润同比增长率", "营业总收入同比增长率"]

            if not all(f in df.columns for f in fields):
                raise Exception("接口字段缺失")

            # 最近三个季度数据
            df_selected = df[fields].tail(3)
            df_selected.columns = ["报告期", "净利润同比增长率", "扣非净利润同比增长率", "营业总收入同比增长率"]

            # 转换为数值
            def to_float(v):
                try:
                    return float(str(v).replace("%", "").strip())
                except:
                    return 0.0

            df_selected = df_selected.map(to_float)
            df_selected = df_selected.sort_values("报告期")

            data = {
                "扣非净利润同比增长率": list(df_selected["扣非净利润同比增长率"]),
                "归母净利润同比增长率": list(df_selected["净利润同比增长率"]),
                "营业总收入同比增长率": list(df_selected["营业总收入同比增长率"]),
            }

            total, trend_adj, detail = self.calc_total_score(data)

            result = {
                "name": "financial",
                "desc": "财报因子",
                "score": max(min(total, 20), 0),  # 封顶20分
                "max_score": 20,
                "meta": {
                    "trend_adj": trend_adj,
                    "detail": detail
                }
            }
            return result

        except Exception as e:
            return {
                "name": "financial",
                "desc": "财报因子",
                "score": 0,
                "max_score": 20,
                "meta": {"error": str(e)}
            }
