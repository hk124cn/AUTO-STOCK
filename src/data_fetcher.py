import tushare as ts
from config.config import TUSHARE_TOKEN
import pandas as pd

ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()

def get_stock_basic():
    """获取股票基本信息"""
    return pro.stock_basic(
        exchange='', 
        list_status='L', 
        fields='ts_code,symbol,name,area,industry,market,list_date'
    )

def get_price_change(ts_code: str):
    """获取最近两年的涨跌幅（按收盘价）"""
    df = pro.daily(ts_code=ts_code, start_date='20230101')
    if df.empty:
        return None
    df = df.sort_values('trade_date')
    start_price = df.iloc[0]['close']
    end_price = df.iloc[-1]['close']
    return round((end_price - start_price) / start_price * 100, 2)

def get_financials():
    """获取财务指标（PB, ROE）"""
    return pro.fina_indicator_vip(fields='ts_code,pb,roe')

