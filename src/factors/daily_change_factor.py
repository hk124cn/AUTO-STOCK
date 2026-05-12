import pandas as pd
from datetime import datetime, timedelta
from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_price


def get_trend_status(close_prices):
    """趋势判断：基于5日/20日均线"""
    ma_short = close_prices.rolling(5).mean()
    ma_long = close_prices.rolling(20).mean()
    trend_strength = (ma_short - ma_long) / ma_long

    if pd.isna(trend_strength.iloc[-1]):
        return "weak_up"  # 默认

    if trend_strength.iloc[-1] > 0.05:
        return "strong_up"
    elif trend_strength.iloc[-1] > 0:
        return "weak_up"
    elif trend_strength.iloc[-1] > -0.05:
        return "weak_down"
    else:
        return "strong_down"


def trend_aware_change_score(today_change, trend_status, volume_ratio=1.0):
    """单日涨跌幅评分（满分10分）"""
    base_scores = {
        'strong_up': {'ranges': [(-10,-7),(-7,-3),(-3,0),(0,3),(3,7),(7,10)], 'scores':[8,6,4,2,1,0]},
        'weak_up': {'ranges': [(-10,-7),(-7,-3),(-3,0),(0,3),(3,7),(7,10)], 'scores':[7,5,3,4,6,3]},
        'weak_down': {'ranges': [(-10,-7),(-7,-3),(-3,0),(0,3),(3,7),(7,10)], 'scores':[6,4,2,5,7,8]},
        'strong_down': {'ranges': [(-10,-7),(-7,-3),(-3,0),(0,3),(3,7),(7,10)], 'scores':[9,7,3,6,8,9]}
    }

    config = base_scores[trend_status]
    base_score = 5
    for (low, high), score in zip(config['ranges'], config['scores']):
        if low <= today_change < high:
            base_score = score
            break

    volume_factor = 1.0
    if volume_ratio > 1.5:
        if (trend_status in ['strong_down','weak_down'] and today_change > 3) or \
           (trend_status in ['strong_up'] and today_change < -3):
            volume_factor = 1.2

    if abs(today_change) > 9.5:
        if trend_status == 'strong_down' and today_change > 9:
            base_score = 10
        elif trend_status == 'strong_up' and today_change < -9:
            base_score = 1

    final_score = min(10, max(0, base_score * volume_factor))
    return round(final_score)


class DailyChangeFactor(BaseFactor):
    """单日涨跌幅因子：根据趋势状态和成交量对当日涨跌幅评分

    评分逻辑：
    1. 判断趋势（5日/20日均线）：strong_up/weak_up/weak_down/strong_down
    2. 根据趋势状态，采用不同的评分矩阵
    3. 成交量放量时，趋势反转则加分

    满分：10分
    """
    weight = 10

    def calculate(self):
        # 获取本地价格数据
        price_df = get_price(self.code)

        if price_df is None or price_df.empty or len(price_df) < 21:
            return {"name": "单日涨跌幅", "score": 0, "sum_score": 10}

        # 排序并获取最近21天数据
        price_df = price_df.copy()
        try:
            price_df['日期'] = pd.to_datetime(price_df['日期'].astype(str), format='%Y%m%d')
        except:
            try:
                price_df['日期'] = pd.to_datetime(price_df['日期'])
            except:
                return {"name": "单日涨跌幅", "score": 0, "sum_score": 10}

        price_df = price_df.sort_values('日期')

        if len(price_df) < 21:
            return {"name": "单日涨跌幅", "score": 0, "sum_score": 10}

        recent = price_df.iloc[-21:]

        close_col = '收盘'
        volume_col = '成交量'

        if close_col not in recent.columns:
            return {"name": "单日涨跌幅", "score": 0, "sum_score": 10}

        # 计算当日涨跌幅
        today_change = (recent[close_col].iloc[-1] - recent[close_col].iloc[-2]) / recent[close_col].iloc[-2] * 100

        # 趋势判断
        trend_status = get_trend_status(recent[close_col])

        # 成交量比率
        if volume_col in recent.columns and len(recent) >= 20:
            vol_mean = recent[volume_col].rolling(20).mean().iloc[-1]
            volume_ratio = recent[volume_col].iloc[-1] / vol_mean if vol_mean > 0 else 1.0
        else:
            volume_ratio = 1.0

        score = trend_aware_change_score(today_change, trend_status, volume_ratio)

        return {
            "name": "单日涨跌幅",
            "score": score,
            "sum_score": 10,
            "meta": {
                "today_change": round(today_change, 2),
                "trend_status": trend_status,
                "volume_ratio": round(volume_ratio, 2)
            }
        }


if __name__ == "__main__":
    factor = DailyChangeFactor("600660")
    print(factor.calculate())