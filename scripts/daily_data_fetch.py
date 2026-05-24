#!/usr/bin/env python3
"""
每日数据获取脚本（整合版）

功能：依次执行以下任务
1. 价格数据下载 + 清洗
2. 资金流向数据获取
3. 行业涨幅数据获取

使用方法：
    python scripts/daily_data_fetch.py

定时任务（每天16:00执行）：
    0 16 * * 1-5 cd /path/to/AUTO-STOCK && /usr/bin/python3 scripts/daily_data_fetch.py
"""
import sys
import os
import subprocess
from datetime import datetime
import logging

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 配置日志
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
today = datetime.today().strftime("%Y%m%d")
log_file = os.path.join(LOG_DIR, f"daily_fetch_{today}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()


def is_trade_day():
    """判断今日是否是交易日"""
    from src.datafactory.trade_calendar import is_trade_day as _is_trade_day
    return _is_trade_day()


def run_script(script_path, description):
    """运行子脚本"""
    logger.info(f"=" * 40)
    logger.info(f"开始: {description}")
    logger.info("=" * 40)

    script_full_path = os.path.join(PROJECT_ROOT, script_path)

    try:
        result = subprocess.run(
            [sys.executable, script_full_path],
            cwd=PROJECT_ROOT,
            capture_output=False,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"✓ {description} 完成")
            return True
        else:
            logger.error(f"✗ {description} 失败 (返回码: {result.returncode})")
            return False
    except Exception as e:
        logger.error(f"✗ {description} 异常: {e}")
        return False


def main():
    logger.info("=" * 50)
    logger.info("每日数据获取开始")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    if not is_trade_day():
        logger.info("今日不是交易日，跳过")
        return

    success_count = 0
    fail_count = 0

    # 1. 价格数据下载 + 清洗
    if run_script("scripts/daily_download.py", "价格数据下载与清洗"):
        success_count += 1
    else:
        fail_count += 1

    # 2. 资金流向数据
    if run_script("scripts/daily_fund_flow.py", "资金流向数据获取"):
        success_count += 1
    else:
        fail_count += 1

    # 3. 行业涨幅数据
    if run_script("scripts/daily_industry_change.py", "行业涨幅数据获取"):
        success_count += 1
    else:
        fail_count += 1

    logger.info("=" * 50)
    logger.info(f"完成: 成功 {success_count}, 失败 {fail_count}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()