import os
import sys

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd

from src.datafactory.data_manager import PRICE_PATH, normalize_code

HIST_MARKET_PATH = "data/hist_price"
LOG_FILE = "data/hist_price_built.csv"


def load_built():
    """加载已处理的文件列表（断点续传）"""
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        return set(df["code"].astype(str).str.zfill(6).tolist())
    return set()


def save_built(code, status="success"):
    """保存处理进度"""
    new_row = {"code": code, "status": status}
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        mask = df["code"] == code
        if mask.any():
            df.loc[mask, "status"] = status
        else:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])
    df.to_csv(LOG_FILE, index=False)


def build_price():
    os.makedirs(PRICE_PATH, exist_ok=True)

    if not os.path.isdir(HIST_MARKET_PATH):
        raise FileNotFoundError(f"未找到历史行情目录: {HIST_MARKET_PATH}")

    files = sorted(file for file in os.listdir(HIST_MARKET_PATH) if file.endswith(".csv"))
    print(f"总共 {len(files)} 个文件")

    # 断点续传：加载已处理的文件
    built = load_built()
    print(f"已处理: {len(built)} 个")

    todo_files = [f for f in files if f.replace(".csv", "").zfill(6) not in built]
    print(f"待处理: {len(todo_files)} 个")

    success_count = 0
    fail_count = 0

    for filename in todo_files:
        # 文件名就是股票代码，如 600660.csv
        code = filename.replace(".csv", "")
        code = code.zfill(6)  # 保持6位
        code = normalize_code(code)

        hist_path = os.path.join(HIST_MARKET_PATH, filename)
        stock_path = os.path.join(PRICE_PATH, f"{code}.csv")

        try:
            df = pd.read_csv(hist_path)

            # 腾讯接口字段转换
            if "date" not in df.columns:
                print(f"{filename} 格式不对，跳过")
                save_built(code, "skip: no date column")
                continue

            # 转换日期格式：2025-05-23 -> 20250523
            df["日期"] = pd.to_datetime(df["date"]).dt.strftime("%Y%m%d").astype(int)

            # 选择需要的字段
            new_df = pd.DataFrame({
                "日期": df["日期"],
                "开盘": df["open"],
                "收盘": df["close"],
                "最高": df["high"],
                "最低": df["low"],
                "成交额": df["amount"]
            })

            if os.path.exists(stock_path):
                # 如果已有数据，合并并保留最新数据
                old = pd.read_csv(stock_path)
                combined = pd.concat([old, new_df], ignore_index=True)
                # 保留最新数据（相同日期取后面的）
                combined = combined.drop_duplicates("日期", keep="last")
                combined = combined.sort_values("日期")
                combined.to_csv(stock_path, index=False)
                print(f"{code}: 合并 {len(new_df)} 条新数据")
            else:
                new_df.to_csv(stock_path, index=False)
                print(f"{code}: 新建文件 {len(new_df)} 条数据")

            save_built(code, "success")
            success_count += 1

        except Exception as e:
            print(f"{code} 处理失败: {e}")
            save_built(code, f"failed: {e}")
            fail_count += 1

    print(f"\n完成! 成功: {success_count}, 失败: {fail_count}")


if __name__ == "__main__":
    build_price()