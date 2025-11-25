import akshare as ak          # 用于获取股票和指数数据的第三方库
import pandas as pd           # 数据处理核心库
from datetime import timedelta # 处理日期加减运算
from datetime import datetime

def format_code(code: str) -> str:
    """补全交易所前缀（如sh/sz）"""
    if code.startswith(("sh", "sz")):      # 如果已有前缀则直接返回
        return code
    elif code.startswith("6"):             # 上海市场代码以6开头
        return "sh" + code                  # 添加sh前缀
    else:                                   # 默认视为深圳市场
        return "sz" + code                  # 添加sz前缀

def get_stock_data(stock_code, start_date, end_date):
    """获取指定代码的股票历史行情数据"""
    try:
        # 标准化日期格式（移除短横线）
        start_fmt = start_date.replace("-", "")  # 例：2025-08-01 → 20250801
        end_fmt = end_date.replace("-", "")      # 例：2025-09-10 → 20250910

        # 调用AKShare接口获取数据
        df = ak.stock_zh_a_hist(
            symbol=stock_code,                # 传入带交易所前缀的完整代码
            period="daily",                   # 按日频度获取数据
            start_date=start_fmt,             # 开始日期（格式化后的值）
            end_date=end_fmt,                 # 结束日期（格式化后的值）
            adjust="qfq"                     # 启用前复权调整
        )

        print(f"{stock_code} 数据列名：{df.columns.tolist()}")  # 调试用：打印实际收到的列名

        if df.empty:                                 # 如果返回空DataFrame
            print(f"&#9888;️ {stock_code} 无数据，检查代码/日期")    # 提示错误信息
            return pd.DataFrame()                 # 返回空表避免后续异常

        # 根据不同平台的命名习惯确定日期列名称
        if "日期" in df.columns:               # 中文平台常用“日期”作为列名
            date_col = "日期"
        elif "date" in df.columns:              # 英文平台可能使用date
            date_col = "date"
        elif "trade_date" in df.columns:         # 部分API返回trade_date
            date_col = "trade_date"
        else:                                   # 找不到任何已知的日期列时报错
            raise ValueError(f"{stock_code} 未找到日期列: {df.columns}")

        # 将字符串类型的日期转换为datetime类型，并重命名为统一的名称“日期”
        df[date_col] = pd.to_datetime(df[date_col])  # 转换数据类型
        df = df.rename(columns={date_col: "日期"})     # 标准化列名便于后续操作

        # 确保必须存在的关键字段存在（这里检查是否有收盘价）
        if "收盘" not in df.columns:            # 如果缺少收盘价字段
            raise ValueError(f"{stock_code} 缺少收盘列: {df.columns}") # 抛出详细错误信息

        # 设置索引为日期以便快速定位特定交易日的数据
        df = df.sort_values("日期").set_index("日期")  # 按日期排序并设为索引
        return df[["收盘"]]                     # 只保留收盘价这一数值型特征

    except Exception as e:                     # 捕获所有可能发生的异常
        print(f"{stock_code} 数据获取失败：{e}")   # 打印具体的错误原因
        return pd.DataFrame()                   # 发生异常时返回空表保护程序继续运行

def get_index_data(start: str, end: str):
    """获取沪深300指数的历史行情数据"""
    start_fmt = start.replace("-", "")         # 同上进行日期格式标准化
    end_fmt = end.replace("-", "")             # 同上进行日期格式标准化
    df = ak.index_zh_a_hist(symbol="000300",    # 沪深300指数的标准代号是000300
        period="daily",                        # 同样按日频度获取数据
        start_date=start_fmt,                  # 传入格式化后的起始日期
        end_date=end_fmt)                      # 传入格式化后的结束日期
    df["日期"] = pd.to_datetime(df["日期"])     # 转换日期列为datetime类型
    df.set_index("日期", inplace=True)          # 就地修改DataFrame，将日期设为索引
    return df                                 # 返回处理好的指数数据

def score_stock_on_date(stock_df, index_df, date):
    """计算某只股票在某个交易日的综合得分及相关市场数据"""
    weights = {"daily_change": 30, "5d_change": 30, "vs_market": 40}  # 各项指标的权重配置
    score = 0                                   # 初始化总分为0

    if date not in stock_df.index:              # 如果请求的日期不在数据范围内
        return None                             # 直接返回None表示无法计算该日数据

    # =====================================================
    # Part 1: 基础信息采集（新增）                     #
    # ---------------------------------------------------
    today_close = stock_df.loc[date, "收盘"]      # &#9989; 获取当日收盘价作为基准点
    # 生成理论上的未来5个工作日的自然日序列        #
    future_dates = pd.date_range(start=date + timedelta(days=1), periods=5)  # 从明天开始往后推5天
    # 过滤掉那些不在实际情况中的无效日期（比如节假日休市的日子）#
    available_future_dates = [d for d in future_dates if d in stock_df.index]  # 只保留确实存在的交易日

    # 初始化变量存储结果                          #
    future_close = None                          # 未来目标日的收盘价待定
    if len(available_future_dates) > 0:         # 只要有任意一天的有效数据就能继续算下去
        end_future_date = available_future_dates[-1]  # 取最远的那个有效日期作为终点
        future_close = stock_df.loc[end_future_date, "收盘"]  # &#128204; 获取未来第5日（或最近可用日）收盘价

    # =====================================================
    # Part 2: 原有评分逻辑（保持不变）               #
    # ---------------------------------------------------
    # --- 单日涨跌幅得分 ---
    yesterday_close = stock_df.shift(1).loc[date, "收盘"]  # 获取前一日收盘价
    daily_change = (today_close - yesterday_close) / yesterday_close * 100  # 计算涨跌幅百分比

    # 根据不同的涨幅范围给予相应的分数奖励      #
    if 2 <= daily_change <= 6:                   # 理想区间[2%,6%]得满分
        score += weights["daily_change"]         # 加上全额权重分
    elif 0 <= daily_change < 2 or 6 < daily_change <= 9:  # 次优区间[0,2)∪(6,9]打七折
        score += weights["daily_change"] * 0.7   # 乘以折扣系数0.7
    elif -2 <= daily_change < 0 or daily_change > 9:      # 风险区域[-2,0)∪(9,∞)打三折
        score += weights["daily_change"] * 0.3   # 乘以保守系数0.3
    else:                                        # 极端情况不给分
        score += 0                              # 不加也不减分

    # --- 连续5日涨跌幅得分 ---
    idx = stock_df.index.get_loc(date)          # 找到当前日期在整个序列中的位置索引
    if idx >= 4:                                # 确保前面至少有4个数据点才能构成5日窗口
        last5 = stock_df.iloc[idx-4:idx+1]       # 提取包含今天的最近5个交易日的数据切片
        change_5d = (last5["收盘"].iloc[-1] - last5["收盘"].iloc[0]) / last5["收盘"].iloc[0] * 100  # 计算5日累计收益率

        # 根据5日趋势表现分配对应的分数         #
        if 5 <= change_5d <= 15:                 # 优秀趋势[5%,15%]拿满额积分
            score += weights["5d_change"]        # 添加全部权重分
        elif 0 <= change_5d < 5:                 # 温和上涨[0,5%)适当加分
            score += weights["5d_change"] * 0.7  # 打折后计入总分
        elif change_5d > 15 or -5 > change_5d >= -10:  # 过热或小幅回调酌情给点辛苦分
            score += weights["5d_change"] * 0.3  # 象征性鼓励一下
        elif change_5d < -10:                    # 大幅下跌零容忍政策
            score += 0                          # 完全不给分

    # =====================================================
    # Part 3: 对比大盘表现（原有逻辑保持不变）           #
    # ---------------------------------------------------
    stock_ytd = (stock_df.loc[date, "收盘"] - stock_df.iloc[0]["收盘"]) / stock_df.iloc[0]["收盘"] * 100  # 本年至今个股涨跌幅
    index_ytd = (index_df.loc[date, "收盘"] - index_df.iloc[0]["收盘"]) / index_df.iloc[0]["收盘"] * 100     # 同期大盘基准涨跌幅
    diff = stock_ytd - index_ytd                 # 超额收益差值

    # 根据跑赢大盘的程度给予额外奖励              #
    if diff > 20:                                # 大幅领先于市场主流水平
        score += weights["vs_market"]            # 全加该项权重分
    elif 0 <= diff <= 20:                        # 基本同步波动但略有优势
        score += weights["vs_market"] * (diff / 20)  # 线性插值得到比例化的奖金
    elif -20 <= diff < 0:                        # 落后于大势但仍可控范围内
        score += weights["vs_market"] * 0.25     # 给少许安慰奖
    else:                                        # 严重拖沓表现恶劣
        score += 0                              # 一毛不拔

    # =====================================================
    # Part 4: 构造最终返回结构（含新字段）           #
    # ---------------------------------------------------
    # 四舍五入到小数点后两位以提高可读性      #
    round_score = round(score, 2)               # &#128313; 对总分进行取舍到分位
    # 处理价格相关的数值精度问题               #
    rounded_today_close = round(float(today_close), 2)        # 当日收盘价保留两位小数
    rounded_future_close = round(float(future_close), 2) if future_close is not None else None  # 未来收盘价同理
    # 计算百分比变化量并做格式化              #
    pct_chg = None                             # 默认无数据状态
    if future_close is not None:               # 只有存在有效终值时才有意义计算增长率
        pct_chg = round(((future_close / today_close) - 1) * 100, 2)  # 标准复利公式换算成百分比形式

    return {
        'score': round_score,                   # 传统评分体系下的量化评估结果
        'close_price': rounded_today_close,     # &#10004;️ 新增：当日收盘绝对价格
        'future_close_price': rounded_future_close, # &#10004;️ 新增：未来目标日收盘绝对价格
        'pct_change': pct_chg                   # &#10004;️ 新增：期间价格变动幅度（百分比）
    }

def backtest(stock_pool_file, start_date, end_date, output_file="scores_backtest.csv"):
    """执行回测流程并将结果保存到CSV文件"""
    stock_list = pd.read_csv(stock_pool_file, dtype={"code": str})  # 读取候选池文件，确保代码列为字符串类型
    index_df = get_index_data(start_date, end_date)                 # 预先加载好整个区间内的大盘参考数据

    results = []                                               # 创建一个空列表用来收集所有记录
    for _, row in stock_list.iterrows():                         # 遍历每一行代表一只潜在的投资标的
        raw_code = str(row["code"]).strip()                     # 去除两端空白字符得到纯净的交易代码
        if len(raw_code) != 6:                                  # 验证是否符合A股标准的六位数编码规则
            print(f"&#10060; {raw_code} 不是6位代码，跳过")           # 如果不符合规范则忽略这条记录
            continue                                           # 跳到下一轮循环处理下一个条目

        stock_df = get_stock_data(raw_code, start_date, end_date)  # 尝试获取这只股票的历史数据
        if stock_df.empty:                                      # 如果未能成功获取到有效数据（例如停牌期间无成交记录）
            continue                                           # 那么跳过此票继续看下一只

        for date in stock_df.index:                             # 对每一个有效的交易日期进行分析
            if date not in index_df.index:                     # 确保当天也有对应的大盘数据可供比较
                continue                                       # 否则跳过这一天的数据点
            # 调用核心算法模块获得综合分析报告                 #
            result = score_stock_on_date(stock_df, index_df, date)
            if result is not None:                             # 确保函数没有返回空值的情况下才进行处理
                # 解包字典获取各个维度的信息                   #
                score_value = result['score']                   # 主要关注的量化评价体系下的得分情况...
                close_price = result['close_price']             # &#10004;️ 新增：当天收盘价
                future_close_price = result['future_close_price'] # &#10004;️ 新增：未来收盘价
                pct_change = result['pct_change']               # &#10004;️ 新增：期间涨幅百分比

                results.append({                              # 构建一个新的字典对象加入到结果集中去
                    "date": date.strftime("%Y-%m-%d"),       
                    "code": raw_code,                        
                    "name": row["name"],                        # 对应的名字字段也一并保存下来供识别用途...
                    "score": score_value,                      # 核心评分指标延续以往定义不变...
                    "pct_change": pct_change,                  # &#10004;️ 新增：两者之间的价格变动幅度（百分比）
                    "close_price": close_price,                # &#10004;️ 新增：当日收盘价格数值
                    "future_close_price": future_close_price  # &#10004;️ 新增：未来目标日收盘价格数值
                })

    # 将所有累积起来的临时结构转换成正式的结构型表格对象     #
    df_results = pd.DataFrame(results)                      # 根据上面收集的一系列记录创建一个新的DataFrame实例
    # 确保新增列也被正确导出                   #
    df_results.to_csv(output_file, index=False, encoding="utf-8-sig")  # 写入磁盘持久化存储起来以便后续分析查看...

    # 友好提示用户已经完成了多少工作量以及在哪里可以找到产出物 #
    print("前几条回测结果预览：")                            # 让用户快速瞥一眼大概的质量如何...
    print(df_results.head(5))                               # 展示头部五行作为一个样本示例...

    print(f"&#9989; 回测完成，结果保存至 {output_file}")          # 确认任务成功结束的消息通知用户...

if __name__ == "__main__":                                   # 当脚本被直接运行时才会执行以下代码块内的内容...
    backtest("stock_pool.csv",                              # 输入参数之一：包含待评估清单的文件路径...
             "2025-08-01",                                  # 测试时间段的起点设定...
             str(datetime.now().date()))
