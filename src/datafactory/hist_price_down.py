import os
import time
import pandas as pd

import akshare as ak

PATH = "data/hist_price"
os.makedirs(PATH, exist_ok=True)


def get_market(code):
    # 添加交易所前缀 (腾讯接口需要)
    if code.startswith("6"):
        code = "sh" + code
    else:
        code = "sz" + code
    try:
        print("尝试历史行情数据-腾讯...")
        return ak.stock_zh_a_hist_tx(symbol=code, start_date="20250523", end_date="20260323", adjust="qfq")
    except Exception as e:
        print(f"{code}取得失败:{e}")
        return None


def download_market(file_name):
    # 优先尝试当前目录，然后是上级目录
    if os.path.exists(file_name):
        csv_file = file_name
    elif os.path.exists(f"../../{file_name}"):
        csv_file = f"../../{file_name}"
    else:
        print("股票代码文件不存在")
        return

    df_code = pd.read_csv(csv_file)
    if "code" not in df_code.columns:
        print("CSV必须包含 code 列")
        return

    for code in df_code["code"]:
        # 转换为6位字符串
        code = str(code).zfill(6)
        file_path = os.path.join(PATH, f"{code}.csv")

        for i in range(5):
            try:
                df = get_market(code)
                if df is None or df.empty:
                    raise RuntimeError(f"{code}返回空行情")

                if os.path.exists(file_path):
                    old = pd.read_csv(file_path)
                    combined = pd.concat([old, df], ignore_index=True)
                    combined = combined.drop_duplicates("date")
                    combined = combined.sort_values("date")
                    combined.to_csv(file_path, index=False)
                else:
                    df.to_csv(file_path, index=False)

                print(f"{code}:指定历史行情下载完成")
                time.sleep(2)  # 避免API限流
                break
            except Exception as e:
                print(f"{code} 指定历史行情下载失败:{i + 1}次", e)
                time.sleep(5)
    return True

if __name__ == "__main__":
    file_name=input("请输入csv:").strip()
    download_market(file_name)
