import akshare as ak
from datetime import datetime

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
    """获取上证指数年初至今涨跌幅"""
    try:
        #sh_stocks = ak.stock_sh_a_spot_em()
        sh_stocks = ak.stock_individual_spot_xq(symbol="SH000001")
        #  print(sh_stocks)
        sh_index = sh_stocks[sh_stocks["item"] == "今年以来涨幅"]
        print(sh_index)
        
        if sh_index.empty:
            print('空')
            return 0.0

        #col_name = "今年以来涨幅"
        change = float(sh_index["value"].values[0])
        return round(change, 2)
    except Exception as e:
        print(f"⚠️ 无法获取上证指数数据: {e}")
        return 0.0
