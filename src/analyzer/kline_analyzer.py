#!/usr/bin/env python3
"""
K线图分析器 - 第一层：生成股票评分-价格历史基础表

功能：
  - 遍历所有 batch_result_*.csv（每日评分）
  - 匹配对应日期的收盘价（data/price/*.csv）
  - 生成一张大表：date, code, name, close_price, total_score
  - 输出到 result/score_price_history.csv

用法：
  python3 kline_analyzer.py          # 全量生成（首次）
  python3 kline_analyzer.py --date 20260525   # 增量追加指定日期
  python3 kline_analyzer.py --code 600519    # 查询单只股票历史
"""

import pandas as pd
import numpy as np
import glob
import re
import os
import sys
import argparse
from pathlib import Path

# 路径配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "price"
RESULT_DIR = BASE_DIR / "result"
SCORE_DIR = RESULT_DIR / "daily_score"
OUTPUT_FILE = RESULT_DIR / "score_price_history.csv"


def load_price(code: str, date: str) -> float | None:
    """
    从 data/price/{code}.csv 读取指定日期的收盘价
    date: YYYYMMDD 格式
    返回: 收盘价或None（停牌/数据缺失）
    """
    price_file = DATA_DIR / f"{code}.csv"
    if not price_file.exists():
        return None
    try:
        df = pd.read_csv(price_file)
        # 日期列可能是 int 或 str
        row = df[df['日期'] == int(date)]
        if len(row) == 0:
            row = df[df['日期'].astype(str) == date]
        if len(row) == 0:
            return None
        price = row['收盘'].values[0]
        if pd.isna(price):
            return None
        return float(price)
    except Exception:
        return None


def build_history_for_date(score_date: str) -> pd.DataFrame:
    """
    生成指定日期的 (code, name, close_price, total_score) 记录
    """
    batch_file = SCORE_DIR / f"batch_result_{score_date}.csv"
    if not batch_file.exists():
        print(f"  评分文件不存在: {batch_file}")
        return pd.DataFrame()

    df = pd.read_csv(batch_file)
    records = []

    for _, row in df.iterrows():
        code = str(row.get('code', '')).zfill(6)
        name = str(row.get('name', ''))
        score = float(row.get('total_score', 0))

        close_price = load_price(code, score_date)
        if close_price is None:
            continue  # 跳过无价格数据（停牌等）

        records.append({
            'date': score_date,
            'code': code,
            'name': name,
            'close_price': close_price,
            'total_score': score,
        })

    return pd.DataFrame(records)


def build_full_history(force: bool = False) -> pd.DataFrame:
    """
    全量生成：遍历所有 batch_result 文件，构建历史大表
    """
    if OUTPUT_FILE.exists() and not force:
        print(f"历史文件已存在: {OUTPUT_FILE}")
        print("使用 --force 强制重新生成")
        return pd.read_csv(OUTPUT_FILE, dtype={'code': str})

    # 找到所有评分文件
    score_files = sorted(glob.glob(str(SCORE_DIR / "batch_result_2026*.csv")))
    print(f"找到 {len(score_files)} 个评分文件")

    all_records = []

    for f in score_files:
        m = re.search(r'batch_result_(\d+)', f)
        if not m:
            continue
        date_str = m.group(1)
        print(f"\n处理 {date_str} ...", end=" ", flush=True)

        batch_df = pd.read_csv(f)
        count = len(batch_df)
        print(f"评分 {count} 只", end=" → ", flush=True)

        date_records = build_history_for_date(date_str)
        if len(date_records):
            all_records.append(date_records)
            print(f"价格匹配成功 {len(date_records)} 只", end="", flush=True)
        else:
            print("价格匹配失败", end="", flush=True)

    if not all_records:
        print("\n没有生成任何数据！")
        return pd.DataFrame()

    result = pd.concat(all_records, ignore_index=True)
    result = result.sort_values(['code', 'date']).reset_index(drop=True)

    # 保存
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_FILE, index=False)
    print(f"\n\n✅ 已保存: {OUTPUT_FILE}")
    print(f"   总记录数: {len(result)}")
    print(f"   股票数: {result['code'].nunique()}")
    print(f"   日期范围: {result['date'].min()} ~ {result['date'].max()}")

    return result


def query_stock(code: str) -> pd.DataFrame:
    """
    查询单只股票的历史数据（用于K线图展示）
    """
    if not OUTPUT_FILE.exists():
        print("历史文件不存在，请先运行全量生成")
        return pd.DataFrame()

    df = pd.read_csv(OUTPUT_FILE, dtype={'code': str})
    code = str(code).zfill(6)
    stock_df = df[df['code'] == code].sort_values('date')

    if len(stock_df) == 0:
        print(f"未找到股票 {code} 的历史数据")
        return pd.DataFrame()

    print(f"\n{stock_df.iloc[0]['name']} ({code}) 历史数据:")
    print(f"  记录数: {len(stock_df)}")
    print(f"  日期范围: {stock_df['date'].min()} ~ {stock_df['date'].max()}")
    print(f"  评分范围: {stock_df['total_score'].min():.1f} ~ {stock_df['total_score'].max():.1f}")
    print(f"  股价范围: {stock_df['close_price'].min():.2f} ~ {stock_df['close_price'].max():.2f}")
    print()
    print(stock_df.to_string(index=False))

    return stock_df


def incremental_build(date: str) -> pd.DataFrame:
    """
    增量追加：只生成指定日期的数据，追加到大表
    """
    print(f"增量生成日期: {date}")

    new_records = build_history_for_date(date)
    if len(new_records) == 0:
        print("没有生成本次数据")
        return pd.DataFrame()

    if OUTPUT_FILE.exists():
        existing = pd.read_csv(OUTPUT_FILE, dtype={'code': str})
        # 移除该日期已有数据，替换为新数据
        existing = existing[existing['date'] != date]
        result = pd.concat([existing, new_records], ignore_index=True)
    else:
        result = new_records

    result = result.sort_values(['code', 'date']).reset_index(drop=True)
    result.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ 追加完成: {len(new_records)} 条")
    print(f"   总记录: {len(result)}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="股票评分-价格历史分析器")
    parser.add_argument('--force', action='store_true', help='强制重新生成全量历史')
    parser.add_argument('--date', type=str, help='增量追加指定日期 (YYYYMMDD)')
    parser.add_argument('--code', type=str, help='查询单只股票历史')
    args = parser.parse_args()

    if args.code:
        query_stock(args.code)
    elif args.date:
        incremental_build(args.date)
    else:
        build_full_history(force=args.force)