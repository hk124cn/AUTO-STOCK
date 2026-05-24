#!/usr/bin/env python3
"""
每日收盘后下载市场数据
在交易日16:00执行
"""
import sys
import os
from datetime import datetime
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志：同时输出到控制台和按日期的日志文件
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
today = datetime.today().strftime("%Y%m%d")
log_file = os.path.join(LOG_DIR, f"daily_download_{today}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

from src.datafactory.trade_calendar import is_trade_day
from src.datafactory.market_down import download_market

# 动态导入 price_builder 的 build_price 函数
from src.datafactory.price_builder import build_price

if __name__ == "__main__":
    if not is_trade_day():
        logger.info("今日不是交易日，跳过")
    else:
        logger.info("今日是交易日，开始下载...")
        success = download_market()

        if success:
            logger.info("数据下载成功，开始清洗...")
            build_price()
            logger.info("数据清洗完成")
        else:
            logger.info("数据下载失败或今日已存在，跳过清洗")