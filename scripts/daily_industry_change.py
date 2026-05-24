#!/usr/bin/env python3
"""行业涨幅数据获取（被 daily_data_fetch.py 调用）"""

import os
import sys
import time
from datetime import datetime, timedelta
from datetime import date

import akshare as ak
import pandas as pd

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.datafactory.data_manager import INDUSTRY_PATH, _read_csv_if_exists

# 配置
INDUSTRY_PATH = "data/industry"
REQUEST_DELAY = 2.0  # 请求延时（秒）
MAX_RETRIES = 3


def get_with_retry(func, *args, **kwargs):
    """带重试的请求"""
    for i in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"    重试 {i+1}/{MAX_RETRIES}: {e}")
            time.sleep(3)
    return None


def get_industry_change(sw_code, days=20):
    """获取单个行业20日涨跌幅"""
    remote = get_with_retry(ak.index_hist_sw, symbol=sw_code, period="day")
    if remote is None or remote.empty:
        return None

    # 处理日期列
    if '日期' in remote.columns:
        remote['日期'] = pd.to_datetime(remote['日期'])
    elif 'date' in remote.columns:
        remote['日期'] = pd.to_datetime(remote['date'])
    else:
        return None

    remote = remote.sort_values('日期')

    if len(remote) < 2:
        return None

    end_date = remote['日期'].max()
    start_date = end_date - timedelta(days=days)
    recent = remote[remote['日期'] >= start_date]

    if len(recent) >= 2:
        start_price = recent.iloc[0]['收盘']
        end_price = recent.iloc[-1]['收盘']
        change_pct = (end_price - start_price) / start_price * 100
        return round(change_pct, 2)

    return None


def append_industry_change(sw_code, sw_name, days=20):
    """追加行业涨跌幅到文件"""
    file_path = os.path.join(INDUSTRY_PATH, f"change_{sw_code}_{days}d.csv")
    today = date.today().strftime('%Y-%m-%d')

    # 获取当日涨跌幅
    change_pct = get_industry_change(sw_code, days)
    if change_pct is None:
        return False

    # 构建新行
    new_row = pd.DataFrame([{
        'date': today,
        'industry': sw_name,
        'industry_code': sw_code,
        'change_pct': change_pct,
        'days': days
    }])

    # 读取现有数据
    if os.path.exists(file_path):
        local = pd.read_csv(file_path)

        # 兼容旧格式（没有date列）
        if 'date' not in local.columns:
            # 迁移旧数据
            print(f"    检测到旧格式数据，正在迁移...")
            # 尝试从 update_time 或其他列推断日期
            if 'update_time' in local.columns:
                local['date'] = pd.to_datetime(local['update_time']).dt.strftime('%Y-%m-%d')
            else:
                local['date'] = 'unknown'

        # 检查今日是否已存在
        if today in local['date'].values:
            print(f"    今日({today})已存在，跳过")
            return True

        # 追加新数据
        combined = pd.concat([local, new_row], ignore_index=True)
    else:
        combined = new_row

    combined.to_csv(file_path, index=False)
    print(f"    {sw_name}({sw_code}): {change_pct}%")
    return True


def main():
    print("=" * 50)
    print("每日行业涨幅数据获取")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 读取行业代码列表（从 build_industry_data.py 导入）
    # 使用申万二级行业代码（131个）
    from src.datafactory.build_industry_data import SW_CODES

    os.makedirs(INDUSTRY_PATH, exist_ok=True)

    success_count = 0
    fail_count = 0

    for idx, item in enumerate(SW_CODES):
        sw_code = item[0]
        sw_name = item[1]

        print(f"[{idx+1}/{len(SW_CODES)}] {sw_name}({sw_code})...", end=" ")

        if append_industry_change(sw_code, sw_name, days=20):
            success_count += 1
        else:
            fail_count += 1

        time.sleep(REQUEST_DELAY)

    print()
    print("=" * 50)
    print(f"完成: 成功 {success_count}, 失败 {fail_count}")
    print("=" * 50)


if __name__ == "__main__":
    main()