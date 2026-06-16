#!/usr/bin/env python3
"""
未来收益标签生成器 (future_return_generator.py)

功能：
- 读取每日评分结果 (batch_result_*.csv)
- 计算N天后(5d/10d/20d)的收益率
- 生成 future_returns 数据文件

运行时间：每日 18:00（在数据下载完成后）
"""

import os
import sys
import csv
import logging
from datetime import datetime
from typing import Optional, Tuple


# 添加项目根目录到路径
AUTO_STOCK_ROOT = "/home/admin/AUTO-STOCK"
sys.path.insert(0, AUTO_STOCK_ROOT)
os.chdir(AUTO_STOCK_ROOT)  # 切换到项目根目录

# 配置日志
LOG_DIR = os.path.join(AUTO_STOCK_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"future_return_{datetime.today().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

# 路径配置
DAILY_SCORE_DIR = os.path.join(AUTO_STOCK_ROOT, "result", "daily_score")
PRICE_DIR = os.path.join(AUTO_STOCK_ROOT, "data", "price")
TRADE_CALENDAR = os.path.join(AUTO_STOCK_ROOT, "data", "calendar", "trade_days.csv")
FUTURE_RETURNS_DIR = os.path.join(AUTO_STOCK_ROOT, "result", "future_returns")


def get_trade_calendar() -> list:
    """读取交易日历"""
    with open(TRADE_CALENDAR, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row['trade_date'].replace('-', '') for row in reader]


def get_nth_trade_day(score_date: str, n: int) -> Optional[str]:
    """
    获取score_date之后第N个交易日的日期
    
    Args:
        score_date: 评分日期 (YYYYMMDD)
        n: 往后数N个交易日
    
    Returns:
        第N个交易日的日期 (YYYYMMDD)，如果不够则返回None
    """
    calendar = get_trade_calendar()
    
    try:
        idx = calendar.index(score_date)
    except ValueError:
        logger.warning(f"⚠️ 评分日期 {score_date} 不在日历中，跳过")
        return None
    
    target_idx = idx + n
    if target_idx >= len(calendar):
        logger.warning(f"⚠️ {score_date} 往后{n}个交易日超出范围(评分日在日历第{idx+1}天，共{len(calendar)}天)")
        return None
    
    return calendar[target_idx]


def get_price(code: str, date: str) -> Optional[float]:
    """
    获取指定股票在指定日期的收盘价
    
    Args:
        code: 股票代码
        date: 日期 (YYYYMMDD 或 YYYY-MM-DD)
    
    Returns:
        收盘价，如果不存在则返回None
    """
    price_file = os.path.join(PRICE_DIR, f"{code}.csv")
    if not os.path.exists(price_file):
        logger.warning(f"⚠️ {code} 价格文件不存在: {price_file}")
        return None
    
    # 标准化日期格式：统一为YYYYMMDD
    date_clean = str(date).replace('-', '')
    date_int = int(date_clean)
    
    try:
        with open(price_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_date = row.get('日期', '')
                # 处理 "20260512", "2026-05-12", 20260512 各种格式
                row_date_clean = str(row_date).replace('-', '')
                try:
                    if int(row_date_clean) == date_int:
                        price = row.get('收盘')
                        if price:
                            return float(price)
                except ValueError:
                    continue
        logger.warning(f"⚠️ {code} 在 {date} 无价格数据(文件存在但该日期缺失)")
        return None
    except Exception as e:
        logger.warning(f"⚠️ {code} 价格读取失败: {e}")
        return None


def load_batch_result(score_date: str) -> list:
    """
    读取指定日期的评分结果
    
    Returns:
        [(code, name, score, score_price), ...]
    """
    batch_file = os.path.join(DAILY_SCORE_DIR, f"batch_result_{score_date}.csv")
    if not os.path.exists(batch_file):
        logger.warning(f"评分文件不存在: {batch_file}")
        return []
    
    results = []
    try:
        with open(batch_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get('code', '').zfill(6)
                name = row.get('name', '')
                score = float(row.get('total_score', 0))
                results.append((code, name, score))
        return results
    except Exception as e:
        logger.error(f"读取评分文件失败 {batch_file}: {e}")
        return []


def generate_future_returns(score_date: str, n_days: int, force: bool = False) -> Tuple[int, int]:
    """
    生成指定日期和天数的未来收益文件
    
    Args:
        score_date: 评分日期 (YYYYMMDD)
        n_days: 天数 (5/10/20)
        force: 是否强制重新生成
    
    Returns:
        (成功数, 失败数)
    """
    # 检查价格数据是否足够
    nd_date = get_nth_trade_day(score_date, n_days)
    if nd_date is None:
        logger.warning(f"无法计算 {score_date} 的 {n_days}d 收益：超出日历范围")
        return 0, 0
    
    today = datetime.today().strftime('%Y%m%d')
    if nd_date > today:
        logger.info(f"无法计算 {score_date} 的 {n_days}d 收益：{nd_date} 还未到")
        return 0, 0
    
    # 检查是否已存在
    output_dir = os.path.join(FUTURE_RETURNS_DIR, f"{n_days}d")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"future_{n_days}d_{score_date}.csv")
    
    if os.path.exists(output_file) and not force:
        logger.info(f"{output_file} 已存在，跳过")
        return 0, 0
    
    # 加载评分数据
    stocks = load_batch_result(score_date)
    if not stocks:
        return 0, 0
    
    # 获取评分日收盘价
    stock_prices = {}
    for code, name, score in stocks:
        price = get_price(code, score_date)
        if price and price > 0:
            stock_prices[code] = {'name': name, 'score': score, 'score_price': price}
        else:
            logger.debug(f"跳过 {code}({name})：评分日价格无效或停牌")
    
    logger.info(f"{score_date} 评分股票 {len(stocks)} 只，其中 {len(stock_prices)} 只有价格数据")
    
    # 计算收益
    success_count = 0
    fail_count = 0
    fail_reasons = {}
    records = []
    
    for code, data in stock_prices.items():
        nd_price = get_price(code, nd_date)
        
        if nd_price is None:
            fail_reasons[code] = f"{nd_date}价格缺失(可能停牌)"
            fail_count += 1
            continue
        elif nd_price <= 0:
            fail_reasons[code] = f"{nd_date}价格异常({nd_price})"
            fail_count += 1
            continue
        elif nd_price == data['score_price']:
            # 价格相同可能是停牌前后复牌
            fail_reasons[code] = f"价格未变({nd_price})，疑似停牌"
            fail_count += 1
            continue
        
        score_price = data['score_price']
        nd_return = (nd_price - score_price) / score_price * 100
        nd_return = round(nd_return, 2)
        
        records.append({
            'date': today,
            'code': code,
            'name': data['name'],
            'score_date': score_date,
            'score_price': score_price,
            'nd_date': nd_date,
            'nd_price': nd_price,
            'next_nd_return': nd_return
        })
        success_count += 1
    
    # 汇总失败原因
    if fail_reasons and len(fail_reasons) <= 10:
        for code, reason in fail_reasons.items():
            logger.debug(f"  {code}: {reason}")
    elif fail_reasons:
        logger.info(f"  另有 {len(fail_reasons)} 只股票失败原因详见debug日志")
    
    # 写入文件
    if records:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['date', 'code', 'name', 'score_date', 'score_price', 
                         'nd_date', 'nd_price', 'next_nd_return']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        
        logger.info(f"✅ 生成 {output_file}: 成功 {success_count}, 失败 {fail_count}")
    else:
        logger.warning(f"⚠️ 无有效数据，未生成文件")
    
    return success_count, fail_count


def main():
    """主入口：扫描并生成所有可计算的future_returns"""
    logger.info("=" * 50)
    logger.info("未来收益标签生成器启动")
    logger.info("=" * 50)
    
    # 要追踪的天数
    n_days_list = [5, 10, 20]
    
    # 扫描所有评分文件
    batch_files = sorted([
        f.replace('batch_result_', '').replace('.csv', '')
        for f in os.listdir(DAILY_SCORE_DIR)
        if f.startswith('batch_result_') and f.endswith('.csv')
    ])
    
    logger.info(f"找到 {len(batch_files)} 个评分文件")
    
    total_success = 0
    total_fail = 0
    
    for score_date in batch_files:
        for n_days in n_days_list:
            s, f = generate_future_returns(score_date, n_days)
            total_success += s
            total_fail += f
    
    logger.info("=" * 50)
    logger.info(f"完成！总计生成：成功 {total_success}, 失败 {total_fail}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()