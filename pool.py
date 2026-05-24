import akshare as ak          # 用于获取股票和指数数据的第三方库
import pandas as pd           # 数据处理核心库

def generate_stock_pool():
    df = ak.stock_info_a_code_name()
    df = df[~df["code"].str.startswith(("8", "4","9"))]  # 过滤北交所,新三板，B股
    df.to_csv("stock_full_pool.csv", index=False)

if __name__ == "__main__":                                   # 当脚本被直接运行时才会执行以下代码块内的内容...
    generate_stock_pool()