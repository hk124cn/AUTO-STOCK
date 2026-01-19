# 获取股票数据
import akshare as ak

def get_trend_status(close_prices, window=20):
    """
    判断股票当前趋势状态
    """
    # 计算短期和长期均线
    ma_short = close_prices.rolling(5).mean()
    ma_long = close_prices.rolling(20).mean()
    
    # 计算趋势强度
    trend_strength = (ma_short - ma_long) / ma_long
    
    if trend_strength.iloc[-1] > 0.05:  # 强势上涨
        return "strong_up"
    elif trend_strength.iloc[-1] > 0:    # 弱势上涨
        return "weak_up"  
    elif trend_strength.iloc[-1] > -0.05: # 弱势下跌
        return "weak_down"
    else:                                # 强势下跌
        return "strong_down"

def trend_aware_change_score(today_change, trend_status, volume_ratio=1.0):
    """
    基于趋势背景的涨跌幅评分
    today_change: 当日涨跌幅
    trend_status: 趋势状态
    volume_ratio: 量比，用于确认信号强度
    """
    
    base_scores = {
        'strong_up': {
            'ranges': [(-10, -7), (-7, -3), (-3, 0), (0, 3), (3, 7), (7, 10)],
            'scores': [8, 6, 4, 2, 1, 0]  # 上涨趋势中大涨要警惕
        },
        'weak_up': {
            'ranges': [(-10, -7), (-7, -3), (-3, 0), (0, 3), (3, 7), (7, 10)],
            'scores': [7, 5, 3, 4, 6, 3]  # 温和上涨中继续上涨是好事
        },
        'weak_down': {
            'ranges': [(-10, -7), (-7, -3), (-3, 0), (0, 3), (3, 7), (7, 10)],
            'scores': [6, 4, 2, 5, 7, 8]  # 下跌末期的上涨是机会
        },
        'strong_down': {
            'ranges': [(-10, -7), (-7, -3), (-3, 0), (0, 3), (3, 7), (7, 10)],
            'scores': [9, 7, 3, 6, 8, 9]  # 暴跌后的大涨是强烈信号
        }
    }
    
    # 基础评分
    config = base_scores[trend_status]
    base_score = 5  # 默认分
    
    for (low, high), score in zip(config['ranges'], config['scores']):
        if low <= today_change < high:
            base_score = score
            break
    
    # 量价确认因子
    volume_factor = 1.0
    if volume_ratio > 2.0:  # 放量
        if (trend_status in ['strong_down', 'weak_down'] and today_change > 3) or \
           (trend_status in ['strong_up'] and today_change < -3):
            volume_factor = 1.2  # 放量确认信号
    
    # 极端情况调整
    if abs(today_change) > 9.5:  # 接近涨跌停
        if trend_status in ['strong_down'] and today_change > 9:
            base_score = 10  # 暴跌后的涨停
        elif trend_status in ['strong_up'] and today_change < -9:
            base_score = 1   # 暴涨后的跌停
    
    final_score = min(10, max(0, base_score * volume_factor))
    return round(final_score)
        
def comprehensive_daily_change_score(stock_data):
    """
    修复版本：综合单日涨跌幅评分
    """
    # 首先查看数据的列名
    print("数据列名:", stock_data.columns.tolist())
    print("数据前几行:")
    print(stock_data.head())
    
    # 根据实际列名调整
    # 常见的列名映射
    column_mapping = {
        'close': ['close', '收盘', '收盘价'],
        'volume': ['volume', '成交量', '成交额']
    }
    
    # 找到实际的列名
    close_col = None
    volume_col = None
    
    for col in stock_data.columns:
        if col in column_mapping['close']:
            close_col = col
        if col in column_mapping['volume']:
            volume_col = col
    
    if close_col is None:
        print("错误: 找不到收盘价列")
        return 5  # 返回默认分数
    
    # 获取基础数据
    close_prices = stock_data[close_col]
    
    # 确保数据足够
    if len(close_prices) < 2:
        print("错误: 数据不足")
        return 5
    
    # 计算涨跌幅
    today_change = (close_prices.iloc[-1] - close_prices.iloc[-2]) / close_prices.iloc[-2] * 100
    
    # 计算趋势状态
    trend_status = get_trend_status(close_prices)
    
    # 计算量比
    volume_ratio = 1.0
    if volume_col and len(stock_data[volume_col]) >= 20:
        volume_ratio = stock_data[volume_col].iloc[-1] / stock_data[volume_col].rolling(20).mean().iloc[-1]
    
    # 获取评分
    score = trend_aware_change_score(today_change, trend_status, volume_ratio)
    
    return score

def main():
    stock_data = ak.stock_zh_a_hist(symbol="600660", period="daily",start_date="20251001",end_date="20251022",adjust="qfq")

    # 计算评分
    score = comprehensive_daily_change_score(stock_data)
    print(f"单日涨跌幅因子评分: {score}/10")

if __name__ == "__main__":
    main()
    

