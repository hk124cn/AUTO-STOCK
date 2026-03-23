from src.datafactory.trade_calendar import is_trade_day
from src.datafactory.market_down import download_market
from src.datafactory.price_builder import build_price


if not is_trade_day():
    print("今日不是交易日")
else:
    ok = download_market()
    if ok:
        build_price()
        print("数据清洗完成")
    else:
        print("下载失败，跳过数据清洗")
