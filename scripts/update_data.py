from src.datafactory.trade_calendar import init_trade_calendar, is_trade_day
from src.datafactory.market_down import download_market
from src.datafactory.price_builder import build_price

# init_trade_calendar()  2026年内不用再下载交易日

if not is_trade_day():

    print("今日不是交易日")

else:

    download_market()

    build_price()