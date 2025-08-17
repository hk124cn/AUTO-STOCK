import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# --------------------------
# 1. 基础参数设置
# --------------------------
current_date = datetime.now().strftime("%Y%m%d")
one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
two_year_ago = (datetime.now() - timedelta(days=365*2)).strftime("%Y%m%d")

pb_min, pb_max = 0.6, 1.6  # 市净率范围
roe_min, roe_max = 1, 7    # 净资产收益率范围（%）


# --------------------------
# 2. 工具函数（与之前一致，复用）
# --------------------------
def get_stock_list():
    """获取A股股票列表（去重处理）"""
    try:
        stock_df = ak.stock_zh_a_spot_em()
        stock_df = stock_df[['代码', '名称']]
        # 过滤股票代码（6/0/3开头）并去重
        stock_df = stock_df[stock_df['代码'].str.match(r'^6|^0|^3')].drop_duplicates(subset=['代码'])
        return stock_df
    except Exception as e:
        print(f"获取股票列表失败：{e}")
        return pd.DataFrame()


def get_price_history(stock_code):
    """获取个股过去2年的价格数据（前复权）"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=two_year_ago,
            end_date=current_date,
            adjust="qfq"  # 前复权
        )
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期').set_index('日期')
        return df[['收盘']]
    except Exception as e:
        print(f"{stock_code} 价格数据获取失败：{e}")
        return pd.DataFrame()

def get_financial_indicators(stock_code):
    """优化指标匹配逻辑，兼容更多 PB/ROE 表述形式"""
    try:
        # 获取个股详情数据
        df = ak.stock_a_indicator_lg(symbol=stock_code)
       # df = ak.stock_individual_info_em(symbol=stock_code)
       # print("DataFrame的列名：", df.columns)

        if df.empty:
            print(f"{stock_code} 无指标数据")
            return None
        
        # 取最后一行数据（最新日期）
        last_row = df.iloc[-1]  # -1 表示最后一行
        
        # 提取日期和PB
        latest_date = last_row['trade_date']
        latest_pb = last_row['pb']
        
        # 打印验证
        print(f"{stock_code} 最新数据 - 日期：{latest_date}，PB：{latest_pb}")

        # PB有效性校验（排除非数字、NaN、范围外）
        if not (isinstance(latest_pb, (float, int)) and not np.isnan(latest_pb)):
            print(f"{stock_code} PB数据无效（{latest_pb}），跳过")
            return None
        if not (pb_min <= latest_pb <= pb_max):
            print(f"{stock_code} PB不达标（{latest_pb}），跳过ROE查询")
            return None

       #2, 调用接口获取指定日期的业绩报表数据
        df = ak.stock_yjbb_em(date="20250331")
       # 根据股票代码筛选数据（精确匹配）
        target_data = df[df["股票代码"] == stock_code]
        
        if not target_data.empty:
            # 提取"净资产收益率"列的值（取第一行结果）
            roe = target_data["净资产收益率"].iloc[0]
            roe = round(roe, 4)  # 保留4位小数
        else:
            print(f"未找到股票代码 {stock_code} 在 20250331 的业绩数据")
            return None

        if roe is not None:
            print(f"股票 {stock_code} 在 20250331 的净资产收益率（ROE）为：{roe}%")
        
        # 直接验证数值有效性（无需转字符串，数值类型本身可判断）
        # 排除非数值（如NaN、None）和无效范围（ROE为负等，根据需求调整）
#        if not (isinstance(latest_pb, (int, float, np.number)) and isinstance(roe, (int, float, np.number))):
 #           print(f"{stock_code} PB或ROE不是有效数值（PB: {latest_pb}, ROE: {roe}）")
  #          return None
# ROE有效性校验
        if not (isinstance(roe, (float, int)) and not np.isnan(roe)):
            print(f"{stock_code} ROE数据无效（{roe}），跳过")
            return None
        if not (roe_min <= roe <= roe_max):
            print(f"{stock_code} ROE不达标（{roe}），跳过")
            return None

        return {'pb': latest_pb, 'roe': roe}
    
    except Exception as e:
        print(f"{stock_code} 财务数据获取失败：{e}")
        return None


# --------------------------
# 3. 核心筛选逻辑（调整顺序：先财务，后价格）
# --------------------------
def filter_stocks(stock_list):
    """先筛选PB和ROE，再检查连续下跌的价格条件"""
    selected_stocks = []
    
    for idx, row in stock_list.iterrows():
        code = row['代码']
        name = row['名称']
        print(f"正在筛选：{code} {name}（{idx+1}/{len(stock_list)}）")
        
        # 第一步：先检查财务指标（PB和ROE）
        financial_data = get_financial_indicators(code)
        if not financial_data:
            continue  # 财务数据缺失，直接跳过
        
        pb = financial_data['pb']
        roe = financial_data['roe']
        
        # 财务指标不在范围内，直接跳过（不进入价格检查）
    #    if not (pb_min <= pb <= pb_max and roe_min <= roe <= roe_max):
     #       print(f"{code} 财务指标不达标（PB: {pb}, ROE: {roe}），跳过")
      #      continue
        
        # 第二步：财务指标达标后，再检查价格是否连续两年下跌
        price_df = get_price_history(code)
        if price_df.empty or len(price_df) < 240:  # 至少需要240个交易日（约1年）
            continue
        
        # 提取价格数据
        latest_price = price_df.iloc[-1]['收盘']
        one_year_ago_price = price_df[price_df.index <= pd.to_datetime(one_year_ago)].iloc[-1]['收盘']
        two_year_ago_price = price_df[price_df.index <= pd.to_datetime(two_year_ago)].iloc[-1]['收盘']
        
        # 检查连续下跌条件
        if not (latest_price < one_year_ago_price and one_year_ago_price < two_year_ago_price):
            print(f"{code} 价格未连续下跌，跳过")
            continue
        
        # 所有条件满足，加入结果
        selected_stocks.append({
            '代码': code,
            '名称': name,
            '最新价': latest_price,
            '1年跌幅(%)': round((latest_price - one_year_ago_price)/one_year_ago_price * 100, 2),
            '2年跌幅(%)': round((latest_price - two_year_ago_price)/two_year_ago_price * 100, 2),
            '市净率(PB)': pb,
            '净资产收益率(ROE, %)': roe
        })
        
        # 控制请求频率
        time.sleep(1)
    
    return pd.DataFrame(selected_stocks)


# --------------------------
# 4. 执行选股并保存结果
# --------------------------
if __name__ == "__main__":
    print(f"开始选股（日期：{current_date}）...")
    
    stock_list = get_stock_list()
    if stock_list.empty:
        print("无股票数据，程序退出")
        exit()
    
    result = filter_stocks(stock_list)
    
    if not result.empty:
        save_path = f"选股结果_{current_date}.csv"
        result.to_csv(save_path, index=False, encoding='utf-8-sig')
        print(f"选股完成，共筛选出 {len(result)} 只股票，结果已保存至 {save_path}")
        print(result[['代码', '名称', '市净率(PB)', '净资产收益率(ROE, %)', '2年跌幅(%)']])
    else:
        print("未筛选出符合条件的股票")
