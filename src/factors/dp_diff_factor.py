import pandas as pd
from datetime import datetime
from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_price, normalize_code
import src.utils

index_ret = None


def get_stock_ytd_return(code):
    """获取个股年初至今收益率"""
    price_df = get_price(code)
    
    if price_df is None or price_df.empty:
        return None
    
    # 确保日期列存在且为日期类型
    if '日期' not in price_df.columns:
        return None
    
    price_df['日期'] = pd.to_datetime(price_df['日期'])
    price_df.set_index('日期', inplace=True)
    
    # 获取去年最后一个交易日的价格
    current_year = datetime.now().year
    last_year_end = f"{current_year-1}-12-31"
    
    last_year_data = price_df[price_df.index <= last_year_end]
    if last_year_data.empty:
        return None
    
    start_price = last_year_data.iloc[-1]['收盘']
    end_price = price_df.iloc[-1]['收盘']
    
    return (end_price - start_price) / start_price * 100


class RelativeStrengthFactor(BaseFactor):
    weight = 10

    def calculate(self):
        global index_ret
        stock_ret = get_stock_ytd_return(self.code)
        print(f"今年本股票涨幅:{stock_ret}")
        if index_ret is None:
            index_ret = src.utils.get_market_change()
        relative = stock_ret - index_ret

        if relative > 20:
            score = 10
        elif relative > 10:
            score = 8
        elif relative > 0:
            score = 6
        elif relative > -5:
            score = 4
        elif relative > -10:
            score = 3
        else:
            score = 2

        return {"name": "今年相对大盘强弱", "score": score, "sum_score": 10}
