import akshare as ak
import copy, sys

def score_single_item(growth_rates, full_score):
    """
    计算单项得分
    growth_rates: [前年同期, 去年同期, 本年季度]（三个同比增长率，单位%）
    full_score: 该项的最高分（正增长最高分）
    """
    last_last, last, current = growth_rates

    # === 基础增长分 ===
    rate = current
    if rate >= 50:
        base_score = full_score
    elif rate >= 30:
        base_score = full_score * 0.8
    elif rate >= 20:
        base_score = full_score * 0.7
    elif rate >= 10:
        base_score = full_score * 0.5
    elif rate >= 0:
        base_score = full_score * 0.3
    elif rate >= -10:
        base_score = full_score * 0.1
    else:
        base_score = 0

    # === 负增长额外扣分 ===
    if rate < 0:
        penalty = max(rate / 10 * (full_score * 0.2), -full_score)
        base_score += penalty

    # === 趋势加减分 ===
    trend_score = 0
    if current > last > last_last:      # 连续改善
        trend_score = 0.2 * full_score
    elif current < last < last_last:    # 连续恶化
        trend_score = -0.2 * full_score

    trend_score = max(min(trend_score, 0.2 * full_score), -0.2 * full_score)

    total = base_score + trend_score
    total = max(min(total, full_score), -full_score)
    return round(total, 2), round(trend_score, 2)


def calc_total_score(data):
    """
    data: dict
    {
        "归母净利润同比增长率": [前年, 去年, 本年],
        "营业总收入同比增长率": [前年, 去年, 本年]
    }
    """
    scores = {}
    scores["扣非净利润"] = score_single_item(data["扣非净利润同比增长率"], 10)
    scores["归母净利润"] = score_single_item(data["归母净利润同比增长率"], 5)
    scores["营业收入"] = score_single_item(data["营业总收入同比增长率"], 5)

    total = sum([s[0] for s in scores.values()])
    trend_adj = sum([s[1] for s in scores.values()])

    print("\n=== 各项得分明细 ===")
    for k, v in scores.items():
        print(f"{k}: {v[0]}分（趋势调整: {v[1]}）")

    print(f"\n趋势加减总分: {trend_adj}")
    print(f"总分（封顶20分，最低-10分）: {max(min(total, 20), -10)}")

def get_score(time):
    # 最近三个季度（倒序）
    if time == "本季度":
       df_selected = df[fields].tail(3)
    elif time == "上季度":
       df_selected = df[fields].iloc[-4:-1]
    elif time == "上上季度":
       df_selected = df[fields].iloc[-5:-2]
       
    # 直接修改列名
   # df_selected.columns = ["日期", "净利润", "扣非", "收入"]
    df_for_print = copy.deepcopy(df_selected)
    new_order = ['报告期','营业总收入同比增长率','净利润同比增长率','扣非净利润同比增长率']
    df_for_print = df_for_print[new_order]
    df_for_print.columns = ["报告期","营收",
            "净利润",
            "扣非" ]
    print(f"\n{gpcode}:{gpname}")
    print(f"\n{time}的最近三个季度关键指标：")
    print(df_for_print.to_string(justify='left'))
    # 把增长率列转成 float（去掉 % 号和非数字）
    def to_float(v):
        try:
            return float(str(v).replace("%", "").strip())
        except:
            return 0.0

    df_selected = df_selected.map(to_float)

    # 按报告期升序排列
    df_selected = df_selected.sort_values("报告期")

    # 生成输入数据
    data = {
        "扣非净利润同比增长率": list(df_selected["扣非净利润同比增长率"]),
        "归母净利润同比增长率": list(df_selected["净利润同比增长率"]),
        "营业总收入同比增长率": list(df_selected["营业总收入同比增长率"])
    }

    # 调用评分逻辑
    calc_total_score(data)

def get_stock_name(stock_code):
     # 调用东方财富接口获取个股信息，返回DataFrame格式
     stock_info = ak.stock_individual_info_em(symbol=stock_code)
     #print("结果：", stock_info)
     if stock_info.empty:
         raise  Exception("错误股票代码")
     else:
      # 提取"股票名称"对应的数值（不同市场代码格式需正确，如沪市6开头、深市0/3开头）
         stockn = stock_info[stock_info['item'] == '股票简称']['value'].values[0]
         return stockn
     
def main():
    global df, fields,gpcode,gpname
   # 拉取同花顺财务摘要数据
    print("输入股票代码:",end="")
    gpcode = input()
    try:
       gpname = get_stock_name(gpcode)
    except Exception as err:
       print('异常:股票代码不正确:\n' + str(err))
       sys.exit()
    df = ak.stock_financial_abstract_ths(symbol=gpcode, indicator="按单季度")

    fields = ["报告期", "净利润同比增长率", "扣非净利润同比增长率", "营业总收入同比增长率"]

    #print("可用字段：", list(df.columns))

    if not all(f in df.columns for f in fields):
        print("❌ 目标字段不在返回数据中，请检查接口输出。")
        return

    caibao = ["本季度","上季度","上上季度"]
    get_score(caibao[0])
    get_score(caibao[1])
    #get_score(caibao[2])

if __name__ == "__main__":
    main()
