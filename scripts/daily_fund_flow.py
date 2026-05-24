#!/usr/bin/env python3
"""资金流向数据获取（被 daily_data_fetch.py 调用）"""

import os
import sys
import glob
from datetime import datetime
from datetime import date

import akshare as ak
import pandas as pd

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.datafactory.data_manager import FUND_PATH

# 配置
FUND_PATH = "data/fund"
MAX_RETRIES = 3


def get_with_retry(func, *args, **kwargs):
    """带重试的请求"""
    for i in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"    重试 {i+1}/{MAX_RETRIES}: {e}")
            import time
            time.sleep(3)
    return None


def get_latest_fund_flow():
    """获取全市场资金流向数据"""
    print("获取同花顺5日资金流向数据...")
    df = get_with_retry(ak.stock_fund_flow_individual, symbol='5日排行')

    if df is None or df.empty:
        print("获取失败")
        return None

    # 标准化股票代码
    if '股票代码' in df.columns:
        df['股票代码'] = df['股票代码'].astype(str).str.strip().str.zfill(6)

    return df


def save_fund_flow(df):
    """保存资金流向数据，按日期命名"""
    os.makedirs(FUND_PATH, exist_ok=True)
    today = date.today().strftime('%Y%m%d')

    # 新文件名
    file_path = os.path.join(FUND_PATH, f"fund_flow_5day_{today}.csv")

    # 检查是否已存在
    if os.path.exists(file_path):
        print(f"今日({today})数据已存在，跳过")
        return True

    # 保存
    df['update_date'] = today
    df.to_csv(file_path, index=False)
    print(f"已保存 {len(df)} 条数据到 {file_path}")
    return True


def main():
    print("=" * 50)
    print("每日资金流向数据获取")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    df = get_latest_fund_flow()
    if df is not None:
        save_fund_flow(df)

    print("=" * 50)
    print("完成")
    print("=" * 50)


if __name__ == "__main__":
    main()