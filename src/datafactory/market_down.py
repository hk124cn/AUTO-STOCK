import os
import time
from datetime import datetime

import akshare as ak

PATH = "data/daily_market"
os.makedirs(PATH, exist_ok=True)


def get_market():
    try:
        print("尝试新浪接口...")
        return ak.stock_zh_a_spot()
    except Exception:
        print("新浪失败，尝试东方财富...")
        return ak.stock_zh_a_spot_em()


def download_market():
    today = datetime.today().strftime("%Y%m%d")
    file_path = os.path.join(PATH, f"{today}.csv")

    if os.path.exists(file_path):
        print("今日行情已存在")
        return True

    for i in range(5):
        try:
            df = get_market()
            if df is None or df.empty:
                raise RuntimeError("返回空行情")

            df["日期"] = today
            df.to_csv(file_path, index=False)
            print("今日行情下载完成")
            return True
        except Exception as e:
            print(f"今日行情下载失败:{i + 1}次", e)
            time.sleep(5)

    print("今日行情下载失败")
    return False


if __name__ == "__main__":
    download_market()
