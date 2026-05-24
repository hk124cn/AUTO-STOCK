import akshare as ak
import pandas as pd
from datetime import datetime,timedelta

def format_code(code: str) -> str:
    """补全交易所前缀（如sh/sz）"""
    if code.startswith(("sh", "sz")):      # 如果已有前缀则直接返回
        return code
    elif code.startswith("6"):             # 上海市场代码以6开头
        return "sh" + code                  # 添加sh前缀
    else:                                   # 默认视为深圳市场
        return "sz" + code                  # 添加sz前缀

def getdate():
    # 获取今年日期范围
    today = datetime.today()
    year_start = f"{today.year}0101"  # 20260101
    today_str = today.strftime("%Y%m%d")  # 20260219
    return year_start,today_str

def get_market_change():
    """获取上证指数年初至今涨跌幅（通用版）"""
    try:
        # 获取上证指数历史数据
        sh_data = ak.stock_zh_index_daily(symbol="sh000001")
        
        # 处理日期索引
        if 'date' in sh_data.columns:
            sh_data['date'] = pd.to_datetime(sh_data['date'])
            sh_data.set_index('date', inplace=True)
        
        # 获取当前年份
        current_year = datetime.now().year
        
        # 查找去年最后一个交易日
        # 从去年12月31日开始往前找，直到找到有数据的那天
        search_date = f"{current_year-1}-12-31"
        search_dt = pd.to_datetime(search_date)
        
        # 往前找最多30天（应对元旦假期）
        for days_back in range(30):
            target_date = search_dt - timedelta(days=days_back)
            if target_date in sh_data.index:
                start_price = sh_data.loc[target_date, 'close']
                start_date = target_date
                break
        else:
            print(f"无法找到{current_year-1}年的交易日数据")
            return 0.0
        
        # 获取当前最新价格
        end_price = sh_data.iloc[-1]['close']
        end_date = sh_data.index[-1]
        
        # 计算涨幅
        change = (end_price - start_price) / start_price * 100
        
        """print(f"基准日: {start_date.strftime('%Y-%m-%d')} 收盘价: {start_price:.2f}")
        print(f"当前日: {end_date.strftime('%Y-%m-%d')} 收盘价: {end_price:.2f}")
        print(f"上证指数年初至今涨幅: {change:.2f}%") """
        
        return round(change, 2)
        
    except Exception as e:
        print(f"⚠️ 无法获取上证指数数据: {e}")
        return 0.0