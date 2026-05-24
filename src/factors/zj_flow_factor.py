import pandas as pd
from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_stock_fund_flow, normalize_code


def parse_money(value):
    """解析金额字符串，返回万元"""
    if pd.isna(value):
        return 0

    value = str(value).strip()
    if not value:
        return 0

    try:
        if '亿' in value:
            return float(value.replace('亿', '').replace(',', '')) * 10000
        elif '万' in value:
            return float(value.replace('万', '').replace(',', ''))
        elif '千' in value:
            return float(value.replace('千', '').replace(',', '')) * 0.1
        else:
            return float(value.replace(',', ''))
    except:
        return 0


class FundFlowFactor(BaseFactor):
    """资金流向因子：基于同花顺5日资金流数据

    评分逻辑（总分10分）：
    - 资金净额方向：净流入 +3，净流出 +0
    - 换手率：10%~20% +3，20%~50% +2，<10%或50%~80% +1，>80% +0
    - 阶段涨幅：0%~15% +3，15%~30% +2，30%~50% +1，>50%或<0% +0
    - 净额规模：>1亿 +1，<1亿 +0
    """
    weight = 10

    def calculate(self):
        code = normalize_code(self.code)
        flow_data = get_stock_fund_flow(code)

        if flow_data is None:
            return {"name": "资金流向", "score": 0, "sum_score": 10}

        score = 0

        # 1. 资金净额方向 (+3 / +0)
        net_amount = parse_money(flow_data.get('资金流入净额', 0))
        if net_amount > 0:
            score += 3

        # 2. 换手率 (+3 / +2 / +1 / +0)
        turnover_rate = flow_data.get('连续换手率', 0)
        try:
            turnover_rate = float(str(turnover_rate).replace('%', ''))
        except:
            turnover_rate = 0

        if 10 <= turnover_rate <= 20:
            score += 3
        elif 20 < turnover_rate <= 50:
            score += 2
        elif (0 < turnover_rate < 10) or (50 < turnover_rate <= 80):
            score += 1
        # > 80% 得 0 分

        # 3. 阶段涨幅 (+3 / +2 / +1 / +0)
        change_pct = flow_data.get('阶段涨跌幅', 0)
        try:
            change_pct = float(str(change_pct).replace('%', ''))
        except:
            change_pct = 0

        if 0 <= change_pct <= 15:
            score += 3
        elif 15 < change_pct <= 30:
            score += 2
        elif 30 < change_pct <= 50:
            score += 1
        # > 50% 或 < 0% 得 0 分

        # 4. 净额规模 (+1 / +0)
        if net_amount > 10000:  # > 1亿 = 10000万
            score += 1

        return {
            "name": "资金流向",
            "score": score,
            "sum_score": 10,
            "meta": {
                "net_amount": net_amount,
                "turnover_rate": turnover_rate,
                "change_pct": change_pct
            }
        }