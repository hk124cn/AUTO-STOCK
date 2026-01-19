import akshare as ak
import sys
import math
from src.core.base_factor import BaseFactor

def get_stock_name(stock_code):
    """获取股票简称"""
    stock_info = ak.stock_individual_info_em(symbol=stock_code)
    if stock_info.empty:
        raise Exception("错误股票代码")
    stock_name = stock_info[stock_info['item'] == '股票简称']['value'].values[0]
    return stock_name


def get_market_change():
    """获取上证指数年初至今涨跌幅"""
    try:
        #sh_stocks = ak.stock_sh_a_spot_em()
        sh_stocks = ak.stock_individual_spot_xq(symbol="SH000001")
        print(sh_stocks)
        sh_index = sh_stocks[sh_stocks["item"] == "今年以来涨幅"]
        print(sh_index)
        return 19.25
        if sh_index.empty:
            print('空')
            return 0.0

        #col_name = "今年以来涨幅"
        change = float(sh_index["value"].values[0])
        return round(change, 2)
    except Exception as e:
        print(f"⚠️ 无法获取上证指数数据: {e}")
        return 0.0


def calc_focus_score(df, market_change):
    """计算关注度得分"""
    mean_focus = df["用户关注指数"].mean()
    std_focus = df["用户关注指数"].std()

    # --- 热度分（0~7分） ---
    base_score = (mean_focus - 80) / 2 - std_focus / 4 + market_change / 10
    base_score = max(0, min(7, base_score))  # 限制在 0~7 分

    # --- 稳健分（0~3分） ---
    if mean_focus < 85 and std_focus < 3:
        stable_bonus = 2.5 - (std_focus / 3)
    else:
        stable_bonus = 0

    final_score = base_score + stable_bonus
    final_score = round(min(10, max(1, final_score)), 1)  # 最低1分，最高10分

    return final_score, mean_focus, std_focus


def main():
    print("输入股票代码:", end="")
    gpcode = input().strip()
    try:
        gpname = get_stock_name(gpcode)
    except Exception as err:
        print('异常: 股票代码不正确:\n' + str(err))
        sys.exit()

    print(f"\n=== {gpcode}: {gpname} ===")

    # 获取股民关注度
    df = ak.stock_comment_detail_scrd_focus_em(symbol=gpcode)
    if df.empty:
        print("❌ 未获取到关注度数据")
        sys.exit()

    print("最近关注度（部分数据）:")
    print(df.tail(10))

    # 获取上证指数涨跌幅
    market_change = get_market_change()
    print(f"\n📈 上证指数年初至今涨跌幅: {market_change}%")

    # 计算评分
    score, mean_focus, std_focus = calc_focus_score(df.tail(20), market_change)

    print("\n📊 股民关注度评分结果:")
    print(f"平均关注度: {mean_focus:.2f}")
    print(f"波动(标准差): {std_focus:.2f}")
    print(f"市场趋势修正: {market_change:+.2f}%")
    print(f"最终得分: {score}/10")


if __name__ == "__main__":
    main()

class attentionFactor(BaseFactor):
    def __init__(self,code,name):
        super().__init__(code,name)

    def calculate(self):
        return{
            "name":"股民关注度",
            "score":7
        }      
