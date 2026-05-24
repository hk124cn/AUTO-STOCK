import pandas as pd
from datetime import datetime
from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_price, get_stock_industry, get_industry_change
import os
import time

# 导入数据管理器
from src.datafactory.data_manager import INDUSTRY_PATH

# 内存缓存：行业成分股映射
_industry_stocks_cache = None
_industry_mapping_df_cache = None


def _load_industry_mapping():
    """加载行业映射到内存（只读一次）"""
    global _industry_mapping_df_cache

    if _industry_mapping_df_cache is not None:
        return _industry_mapping_df_cache

    mapping_file = os.path.join(INDUSTRY_PATH, "stock_industry_mapping.csv")
    if not os.path.exists(mapping_file):
        print(f"警告: 行业映射文件不存在: {mapping_file}")
        return None

    try:
        _industry_mapping_df_cache = pd.read_csv(mapping_file, dtype={'股票代码': str, '行业代码': str})
        return _industry_mapping_df_cache
    except Exception as e:
        print(f"加载行业映射失败: {e}")
        return None


def get_stock_industry_from_cache(code):
    """从缓存获取个股所属行业和行业代码"""
    df = _load_industry_mapping()
    if df is None:
        return None, ''

    code = str(code).zfill(6)
    match = df[df['股票代码'] == code]

    if match.empty:
        return None, ''

    return match.iloc[0]['行业名称'], match.iloc[0]['行业代码']


def get_industry_change_by_code(sw_code, date=None, days=20):
    """根据申万行业代码获取涨跌幅

    Args:
        sw_code: 申万行业代码
        date: 日期字符串 'YYYY-MM-DD'，不传则取最新交易日
        days: 涨跌幅周期

    Returns:
        DataFrame: 包含 change_pct 等字段
    """
    if not sw_code:
        return None

    file_path = os.path.join(INDUSTRY_PATH, f"change_{sw_code}_{days}d.csv")
    if not os.path.exists(file_path):
        return None

    try:
        df = pd.read_csv(file_path)

        if df.empty:
            return None

        if date:
            # 回测模式：精确匹配日期
            match = df[df['date'] == date]
            if not match.empty:
                return match.iloc[0]

            # 没有精确匹配，取最近的前一天
            df['date'] = pd.to_datetime(df['date'])
            df = df[df['date'] <= pd.to_datetime(date)]
            if df.empty:
                return None
            df = df.sort_values('date', ascending=False)
            return df.iloc[0]
        else:
            # 正常模式：取最新日期
            df = df.sort_values('date', ascending=False)
            return df.iloc[0]

    except Exception:
        return None


def get_stock_period_return(code, days=20):
    """获取个股近期涨幅"""
    price_df = get_price(code)

    if price_df is None or price_df.empty:
        return None

    if '日期' not in price_df.columns:
        return None

    price_df = price_df.copy()
    # 兼容多种日期格式
    try:
        price_df['日期'] = pd.to_datetime(price_df['日期'].astype(str), format='%Y%m%d')
    except:
        try:
            price_df['日期'] = pd.to_datetime(price_df['日期'])
        except:
            return None
    price_df = price_df.sort_values('日期')

    if len(price_df) < 2:
        return None

    # 获取近期涨幅
    end_price = price_df.iloc[-1]['收盘']
    if len(price_df) >= days:
        start_price = price_df.iloc[-days]['收盘']
    else:
        start_price = price_df.iloc[0]['收盘']

    return (end_price - start_price) / start_price * 100


# 评分配置 - 各维度满分及权重
SCORE_CONFIG = {
    'relative': {
        'weight': 0.60,  # 相对强弱权重 60%
        'full_score': 10,
    },
    'momentum': {
        'weight': 0.20,  # 行业动量权重 20%
        'full_score': 10,
    },
    'absolute': {
        'weight': 0.20,  # 绝对强度权重 20%
        'full_score': 10,
    },
}


def calculate_industry_score(stock_pct, industry_pct):
    """多维度行业差异评分

    返回: (总分, 各维度得分详情)
    """
    # 1. 相对强弱 (60%)
    relative = stock_pct - industry_pct
    relative_score = _score_relative(relative, 10)

    # 2. 行业动量 (20%)
    momentum_score = _score_momentum(industry_pct, 10)

    # 3. 绝对强度 (20%)
    absolute_score = _score_absolute(stock_pct, 10)

    # 计算加权总分
    total = (
        relative_score * SCORE_CONFIG['relative']['weight'] +
        momentum_score * SCORE_CONFIG['momentum']['weight'] +
        absolute_score * SCORE_CONFIG['absolute']['weight']
    )

    details = {
        'relative': {'value': relative, 'score': round(relative_score, 2)},
        'momentum': {'value': industry_pct, 'score': round(momentum_score, 2)},
        'absolute': {'value': stock_pct, 'score': round(absolute_score, 2)},
    }

    return round(total, 1), details


def _score_relative(relative, full_score):
    """相对强弱评分 - 个股 vs 行业"""
    # 相对强弱 > 15%: 满分
    # 相对强弱 > 10%: 80%分
    # 相对强弱 > 5%: 60%分
    # 相对强弱 > 0%: 40%分
    # 相对强弱 > -5%: 20%分
    # 相对强弱 <= -5%: 0分
    if relative > 15:
        return full_score
    elif relative > 10:
        return full_score * 0.8
    elif relative > 5:
        return full_score * 0.6
    elif relative > 0:
        return full_score * 0.4
    elif relative > -5:
        return full_score * 0.2
    else:
        return 0


def _score_momentum(industry_pct, full_score):
    """行业动量评分 - 行业本身上涨加分，下跌扣分"""
    # 行业上涨 > 10%: 满分
    # 行业上涨 > 5%: 80%分
    # 行业上涨 > 0%: 50%分
    # 行业下跌 > -5%: 20%分
    # 行业下跌 <= -5%: 0分
    if industry_pct > 10:
        return full_score
    elif industry_pct > 5:
        return full_score * 0.8
    elif industry_pct > 0:
        return full_score * 0.5
    elif industry_pct > -5:
        return full_score * 0.2
    else:
        return 0


def _score_absolute(stock_pct, full_score):
    """绝对强度评分 - 个股本身涨幅"""
    # 个股上涨 > 20%: 满分
    # 个股上涨 > 10%: 80%分
    # 个股上涨 > 0%: 50%分
    # 个股下跌 > -10%: 20%分
    # 个股下跌 <= -10%: 0分
    if stock_pct > 20:
        return full_score
    elif stock_pct > 10:
        return full_score * 0.8
    elif stock_pct > 0:
        return full_score * 0.5
    elif stock_pct > -10:
        return full_score * 0.2
    else:
        return 0


class IndustryDiffFactor(BaseFactor):
    """行业差异因子：比较个股与所属行业的相对表现

    多维度评分：
    1. 相对强弱 (60%) - 个股 vs 行业
    2. 行业动量 (20%) - 行业本身涨跌
    3. 绝对强度 (20%) - 个股本身涨幅

    数据来源：
    - 行业映射：data/industry/stock_industry_mapping.csv
    - 行业涨跌幅：data/industry/change_{sw_code}_20d.csv
    """

    def calculate(self):
        # 1. 从缓存获取个股所属行业和行业代码
        industry_name, sw_code = get_stock_industry_from_cache(self.code)

        if not industry_name:
            print(f"提示: {self.code} 行业信息不存在")
            return {"name": "行业相对强弱", "score": 0, "sum_score": 10, "meta": {"error": "行业映射不存在"}}

        # 2. 根据行业代码获取行业近期涨幅
        industry_change = get_industry_change_by_code(sw_code, days=20)

        if industry_change is None:
            print(f"无法获取行业 {industry_name}({sw_code}) 的涨跌幅")
            return {"name": "行业相对强弱", "score": 0, "sum_score": 10,
                    "meta": {"industry": industry_name, "sw_code": sw_code, "error": "行业涨跌幅数据不存在"}}

        industry_pct = industry_change['change_pct']

        # 3. 获取个股近期涨幅
        stock_pct = get_stock_period_return(self.code, days=20)

        if stock_pct is None:
            print(f"无法获取 {self.code} 的价格数据")
            return {"name": "行业相对强弱", "score": 0, "sum_score": 10,
                    "meta": {"industry": industry_name, "sw_code": sw_code, "error": "价格数据不存在"}}

        # 4. 计算多维度评分
        relative = stock_pct - industry_pct
        score, details = calculate_industry_score(stock_pct, industry_pct)

        print(f"{self.code} 个股:{stock_pct:.2f}% 行业:{industry_name}:{industry_pct:.2f}% 相对:{relative:.2f}% → 得分:{score}")

        return {
            "name": "行业相对强弱",
            "score": score,
            "sum_score": 10,
            "meta": {
                "industry": industry_name,
                "sw_code": sw_code,
                "stock_return": round(stock_pct, 2),
                "industry_return": round(industry_pct, 2),
                "relative": round(relative, 2),
                "details": details
            }
        }