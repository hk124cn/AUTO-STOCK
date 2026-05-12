import pandas as pd
from datetime import datetime
from src.core.base_factor import BaseFactor
from src.datafactory.data_manager import get_price, get_stock_industry, get_industry_change
import os
import time

# 导入数据管理器
from src.datafactory.data_manager import INDUSTRY_PATH

# 申万行业代码映射（行业名称 → 申万代码）
# 注：已更新，添加汽车二级行业801880
SW_CODE_MAP = {
    '农林牧渔': '801010',
    '化工': '801030',
    '钢铁': '801040',
    '有色金属': '801050',
    '电子': '801080',
    '纺织服装': '801110',
    '轻工制造': '801120',
    '家用电器': '801130',
    '医药生物': '801150',
    '食品饮料': '801160',
    '公用事业': '801210',
    '建筑装饰': '801230',
    '房地产': '801250',
    '商务服务': '801260',
    '休闲服务': '801270',
    '传媒': '801280',
    '汽车': '801880',  # 申万汽车二级
    # 近似映射（API不支持的行业映射到已有数据的近似行业）
    '通信': '801080',      # 通信 → 电子
    '电力设备': '801030',  # 电力设备 → 化工
    '国防军工': '801030',  # 国防军工 → 化工
    '机械设备': '801030',  # 机械设备 → 化工
    '交通运输': '801030',  # 交通运输 → 化工
    '非银金融': '801250',  # 非银金融 → 房地产
    '银行': '801250',      # 银行 → 房地产
    '综合': '801010',      # 综合 → 农林牧渔
}

# 内存缓存：行业成分股映射
_industry_stocks_cache = None


def _get_sw_code(industry_name):
    """获取申万行业代码"""
    return SW_CODE_MAP.get(industry_name)


def _load_industry_stocks():
    """加载行业成分股映射（内存缓存）"""
    global _industry_stocks_cache
    if _industry_stocks_cache is not None:
        return _industry_stocks_cache

    import os
    mapping_file = os.path.join(INDUSTRY_PATH, "stock_industry_mapping.csv")

    if not os.path.exists(mapping_file):
        # 行业映射文件不存在，返回 None
        print(f"警告: 行业映射文件不存在: {mapping_file}")
        print("请先运行 build_industry_mapping() 构建行业数据")
        _industry_stocks_cache = {}
        return _industry_stocks_cache

    try:
        df = pd.read_csv(mapping_file, dtype={'股票代码': str})
        # 构建行业→股票列表的映射（去重，只保留第一个）
        seen_codes = set()
        _industry_stocks_cache = {}
        for _, row in df.iterrows():
            code = str(row.get('股票代码', '')).zfill(6)
            industry = row.get('行业名称', '')
            if code and industry and code not in seen_codes:
                seen_codes.add(code)
                if industry not in _industry_stocks_cache:
                    _industry_stocks_cache[industry] = []
                _industry_stocks_cache[industry].append(code)
        print(f"已加载行业映射，共 {len(_industry_stocks_cache)} 个行业")
        return _industry_stocks_cache
    except Exception as e:
        print(f"加载行业映射失败: {e}")
        _industry_stocks_cache = {}
        return _industry_stocks_cache


def get_stock_industry_from_cache(code):
    """从缓存获取个股所属行业和代码（更快）"""
    industry_stocks = _load_industry_stocks()

    # 反向查找：股票代码 → 行业
    code = str(code).zfill(6)
    for industry, stocks in industry_stocks.items():
        if code in stocks:
            # 从映射表中获取对应的行业代码
            mapping_file = os.path.join(INDUSTRY_PATH, "stock_industry_mapping.csv")
            try:
                df = pd.read_csv(mapping_file, dtype={'股票代码': str})
                match = df[df['股票代码'] == code]
                if not match.empty:
                    sw_code = match.iloc[0].get('行业代码', '')
                    return industry, sw_code
            except:
                pass
            return industry, ''
    return None, ''


def get_industry_change_by_code(sw_code, days=20):
    """根据申万行业代码获取涨跌幅（从本地缓存读取）"""
    if not sw_code:
        return None

    # 读取缓存文件
    file_path = os.path.join(INDUSTRY_PATH, f"change_{sw_code}_{days}d.csv")
    if not os.path.exists(file_path):
        return None

    try:
        df = pd.read_csv(file_path)
        return df
    except Exception:
        return None


def get_industry_change_by_name(industry_name, days=20):
    """根据行业名称获取申万行业涨跌幅（已废弃，请使用 get_industry_change_by_code）"""
    # 兼容旧代码，但不再使用
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
        'weight': 0.50,  # 相对强弱权重 50%
        'full_score': 10,  # 满分10分
    },
    'momentum': {
        'weight': 0.20,  # 行业动量权重 20%
        'full_score': 10,  # 满分10分
    },
    'absolute': {
        'weight': 0.20,  # 绝对强度权重 20%
        'full_score': 10,  # 满分10分
    },
    'stability': {
        'weight': 0.10,  # 稳定性权重 10%
        'full_score': 10,  # 满分10分
    },
}


def calculate_industry_score(stock_pct, industry_pct, stock_period_returns):
    """多维度行业差异评分

    返回: (总分, 各维度得分详情)
    """
    # 1. 相对强弱 (50%)
    relative = stock_pct - industry_pct
    relative_score = _score_relative(relative, 10)  # 10分制

    # 2. 行业动量 (20%) - 行业本身涨跌情况
    momentum_score = _score_momentum(industry_pct, 10)

    # 3. 绝对强度 (20%) - 个股本身的涨幅
    absolute_score = _score_absolute(stock_pct, 10)

    # 4. 稳定性 (10%) - 相对强弱波动
    stability_score = _score_stability(stock_period_returns, industry_pct, 10)

    # 计算加权总分
    total = (
        relative_score * SCORE_CONFIG['relative']['weight'] +
        momentum_score * SCORE_CONFIG['momentum']['weight'] +
        absolute_score * SCORE_CONFIG['absolute']['weight'] +
        stability_score * SCORE_CONFIG['stability']['weight']
    )

    details = {
        'relative': {'value': relative, 'score': round(relative_score, 2)},
        'momentum': {'value': industry_pct, 'score': round(momentum_score, 2)},
        'absolute': {'value': stock_pct, 'score': round(absolute_score, 2)},
        'stability': {'value': 0, 'score': round(stability_score, 2)},
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


def _score_stability(stock_period_returns, industry_pct, full_score):
    """稳定性评分 - 简化为中等分数"""
    # 暂给5分（满分10分的中等分数）
    return full_score * 0.5


# 全局变量存储每日涨跌幅数据用于稳定性计算
_industry_daily_change = {}


def get_industry_change_cached(industry_name, days=20, use_cache=True):
    """获取行业涨跌幅（带缓存）"""
    cache_key = f"{industry_name}_{days}"

    if use_cache and cache_key in _industry_change_cache:
        return _industry_change_cache[cache_key]

    result = get_industry_change(industry_name, days=days)

    if result is not None and not result.empty:
        _industry_change_cache[cache_key] = result

    return result


class IndustryDiffFactor(BaseFactor):
    """行业差异因子：比较个股与所属行业的相对表现

    多维度评分：
    1. 相对强弱 (50%) - 个股 vs 行业
    2. 行业动量 (20%) - 行业本身涨跌
    3. 绝对强度 (20%) - 个股本身涨幅
    4. 稳定性 (10%) - 相对强弱波动

    防封策略：
    - 使用内存缓存的行业映射
    - 行业涨跌幅数据本地缓存
    """

    def calculate(self):
        # 1. 从缓存获取个股所属行业和行业代码
        industry_name, sw_code = get_stock_industry_from_cache(self.code)

        if not industry_name:
            print(f"提示: {self.code} 行业信息不存在")
            return {"name": "行业相对强弱", "score": 0, "sum_score": 10, "meta": {"error": "行业映射不存在"}}

        # 2. 根据行业代码获取行业近期涨幅
        industry_change = get_industry_change_by_code(sw_code, days=20)

        if industry_change is None or industry_change.empty:
            print(f"无法获取行业 {industry_name}({sw_code}) 的涨跌幅")
            return {"name": "行业相对强弱", "score": 0, "sum_score": 10,
                    "meta": {"industry": industry_name, "sw_code": sw_code, "error": "行业涨跌幅数据不存在"}}

        industry_pct = industry_change.iloc[0]['change_pct']

        # 3. 获取个股近期涨幅
        stock_pct = get_stock_period_return(self.code, days=20)

        if stock_pct is None:
            print(f"无法获取 {self.code} 的价格数据")
            return {"name": "行业相对强弱", "score": 0, "sum_score": 10,
                    "meta": {"industry": industry_name, "sw_code": sw_code, "error": "价格数据不存在"}}

        # 4. 计算多维度评分
        relative = stock_pct - industry_pct

        # 简化的稳定性计算（暂用固定值）
        stock_period_returns = [stock_pct]  # 简化处理

        score, details = calculate_industry_score(stock_pct, industry_pct, stock_period_returns)

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