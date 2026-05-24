#!/usr/bin/env python3
"""
全量历史行情下载脚本
从 stock_full_pool.csv 读取股票列表，下载所有股票的历史行情
防封策略：5秒间隔+随机波动、每批150只休息20分钟、断点续传
"""
import os
import sys
import time
import random
import logging
from datetime import datetime

import pandas as pd
import akshare as ak

# ========== 配置 ==========
PATH = "data/hist_price"
os.makedirs(PATH, exist_ok=True)

STOCK_POOL_FILE = "stock_full_pool.csv"
LOG_FILE = "data/hist_price_downloaded.csv"

# 下载参数
START_DATE = "20160101"
END_DATE = "20260501"  # 当前日期前一点，确保数据完整
BATCH_SIZE = 150
BATCH_REST = 20 * 60  # 20分钟
REQUEST_INTERVAL = 5  # 基础间隔
RANDOM_RANGE = 2  # 随机波动
MAX_RETRIES = 3
SKIP_AFTER_FAILURES = 3

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hist_price_download.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_market(code):
    """获取单只股票历史行情"""
    # 添加交易所前缀 (腾讯接口需要)
    if code.startswith("6"):
        symbol = "sh" + code
    else:
        symbol = "sz" + code

    try:
        df = ak.stock_zh_a_hist_tx(symbol=symbol, start_date=START_DATE, end_date=END_DATE, adjust="qfq")
        if df is None or df.empty:
            raise RuntimeError(f"{code} 返回空行情")
        return df
    except Exception as e:
        logger.error(f"{code} 获取失败: {e}")
        return None


def random_sleep():
    """随机睡眠，防止固定频率"""
    sleep_time = REQUEST_INTERVAL + random.uniform(-RANDOM_RANGE, RANDOM_RANGE)
    time.sleep(max(1, sleep_time))  # 至少1秒


def load_downloaded():
    """加载已下载的股票列表"""
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        return set(df["code"].astype(str).str.zfill(6).tolist())
    return set()


def save_progress(code, status="success", error_msg=""):
    """保存下载进度"""
    log_path = LOG_FILE
    new_row = {
        "code": code,
        "status": status,
        "error": error_msg,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if os.path.exists(log_path):
        df = pd.read_csv(log_path)
        # 更新或追加
        mask = df["code"] == code
        if mask.any():
            df.loc[mask, "status"] = status
            df.loc[mask, "error"] = error_msg
            df.loc[mask, "timestamp"] = new_row["timestamp"]
        else:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])

    df.to_csv(log_path, index=False)


def download_one(code):
    """下载单只股票，支持重试"""
    file_path = os.path.join(PATH, f"{code}.csv")
    failures = 0
    last_error = ""

    for attempt in range(MAX_RETRIES):
        try:
            df = get_market(code)
            if df is None or df.empty:
                raise RuntimeError("返回空数据")

            # 保存数据
            if os.path.exists(file_path):
                old = pd.read_csv(file_path)
                # 转换日期格式为字符串，避免排序比较问题
                df["date"] = df["date"].astype(str)
                old["date"] = old["date"].astype(str)
                combined = pd.concat([old, df], ignore_index=True)
                combined = combined.drop_duplicates("date")
                combined = combined.sort_values("date")
                combined.to_csv(file_path, index=False)
            else:
                df.to_csv(file_path, index=False)

            logger.info(f"{code}: 下载完成 ({len(df)} 条)")
            save_progress(code, "success")
            return True

        except Exception as e:
            failures += 1
            last_error = str(e)
            logger.warning(f"{code} 下载失败 ({attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(15)  # 失败重试间隔15秒

    save_progress(code, "failed", last_error if failures else "unknown")
    return False


def run():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始全量历史行情下载")
    logger.info(f"股票池: {STOCK_POOL_FILE}")
    logger.info(f"批次大小: {BATCH_SIZE}, 休息时间: {BATCH_REST // 60}分钟")
    logger.info("=" * 50)

    # 加载股票列表
    if not os.path.exists(STOCK_POOL_FILE):
        logger.error(f"股票池文件不存在: {STOCK_POOL_FILE}")
        return

    df_pool = pd.read_csv(STOCK_POOL_FILE)
    if "code" not in df_pool.columns:
        logger.error("股票池文件必须包含 code 列")
        return

    all_codes = df_pool["code"].astype(str).str.zfill(6).tolist()
    logger.info(f"总共 {len(all_codes)} 只股票")

    # 加载已下载列表（断点续传）
    downloaded = load_downloaded()
    logger.info(f"已下载: {len(downloaded)} 只")

    # 过滤待下载
    todo_codes = [c for c in all_codes if c not in downloaded]
    logger.info(f"待下载: {len(todo_codes)} 只")

    if not todo_codes:
        logger.info("所有股票已下载完成！")
        return

    # 分批下载
    total = len(todo_codes)
    success_count = 0
    fail_count = 0
    consecutive_failures = 0

    for i, code in enumerate(todo_codes):
        try:
            # 检查是否需要休息
            if i > 0 and i % BATCH_SIZE == 0:
                logger.info(f"完成 {i}/{total}，开始休息 {BATCH_REST // 60} 分钟...")
                time.sleep(BATCH_REST)

            # 下载一只
            logger.info(f"[{i + 1}/{total}] 正在下载 {code}...")
            if download_one(code):
                success_count += 1
                consecutive_failures = 0
            else:
                fail_count += 1
                consecutive_failures += 1

            # 连续失败过多，暂停一下
            if consecutive_failures >= SKIP_AFTER_FAILURES:
                logger.warning(f"连续 {consecutive_failures} 次失败，休息 5 分钟...")
                time.sleep(5 * 60)
                consecutive_failures = 0

            # 请求间隔
            random_sleep()

        except KeyboardInterrupt:
            logger.info("用户中断，保存进度...")
            break
        except Exception as e:
            logger.error(f"异常: {e}")
            save_progress(code, "error", str(e))
            fail_count += 1
            time.sleep(30)  # 异常后等待

    # 完成
    logger.info("=" * 50)
    logger.info(f"下载完成! 成功: {success_count}, 失败: {fail_count}")
    logger.info(f"进度文件: {LOG_FILE}")
    logger.info("=" * 50)


if __name__ == "__main__":
    run()