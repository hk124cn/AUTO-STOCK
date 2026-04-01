import os
from datetime import datetime

import akshare as ak
import pandas as pd

DATA_DIR = "data"
PRICE_PATH = os.path.join(DATA_DIR, "price")
FINANCE_PATH = os.path.join(DATA_DIR, "finance")
DIVIDEND_PATH = os.path.join(DATA_DIR, "dividend")
ATTENTION_PATH = os.path.join(DATA_DIR, "attention")
NEWS_PATH = os.path.join(DATA_DIR, "news")


for path in [PRICE_PATH, FINANCE_PATH, DIVIDEND_PATH, ATTENTION_PATH, NEWS_PATH]:
    os.makedirs(path, exist_ok=True)


def normalize_code(code: str) -> str:
    if len(code) == 6:
        return code
    elif len(code) == 8:
        return code[2:]
    else:
        return str(code).split(".")[0].zfill(6)


def _read_csv_if_exists(file_path):
    if not os.path.exists(file_path):
        return None
    return pd.read_csv(file_path)


def get_price(code):
    code = normalize_code(code)
    file_path = os.path.join(PRICE_PATH, f"{code}.csv")
    return _read_csv_if_exists(file_path)


def get_finance(code, refresh=False):
    code = normalize_code(code)
    file_path = os.path.join(FINANCE_PATH, f"{code}.csv")

    if not refresh:
        local = _read_csv_if_exists(file_path)
        if local is not None and not local.empty:
            return local

    try:
        remote = ak.stock_financial_abstract_ths(symbol=code, indicator="按单季度")
    except Exception:
        return _read_csv_if_exists(file_path)

    if remote is None or remote.empty:
        return _read_csv_if_exists(file_path)

    remote.to_csv(file_path, index=False)
    return remote


def get_dividend(code, refresh=False):
    code = normalize_code(code)
    file_path = os.path.join(DIVIDEND_PATH, f"{code}.csv")

    local = _read_csv_if_exists(file_path)
    if not refresh and local is not None and not local.empty:
        return local

    try:
        remote = ak.stock_history_dividend_detail(symbol=code, indicator="分红")
        #没有了？ remote = ak.stock_dividents_cninfo(symbol=code)
    except Exception:
        return local

    if remote is None or remote.empty:
        return local

    remote.to_csv(file_path, index=False)
    return remote


def get_attention(code, refresh=False):
    code = normalize_code(code)
    file_path = os.path.join(ATTENTION_PATH, f"{code}.csv")
    
    # 获取远程数据（滚动窗口）
    try:
        remote = ak.stock_comment_detail_scrd_focus_em(symbol=code)
        if remote is None or remote.empty:
            return _read_csv_if_exists(file_path)
        
        remote['交易日'] = pd.to_datetime(remote['交易日'])
        
    except Exception as e:
        print(f"获取关注度数据失败 {code}: {e}")
        return _read_csv_if_exists(file_path)
    
    # 读取本地历史数据
    local = _read_csv_if_exists(file_path)
    
    if local is None or local.empty:
        # 首次获取，直接保存
        remote.to_csv(file_path, index=False)
        return remote
    
    # 合并数据
    local['交易日'] = pd.to_datetime(local['交易日'])
    
    # 关键：只添加本地没有的日期
    existing_dates = set(local['交易日'].dt.date)
    new_rows = remote[~remote['交易日'].dt.date.isin(existing_dates)]
    
    if new_rows.empty:
        print(f"没有新数据，本地已有 {len(local)} 条记录")
        return local
    
    # 合并新数据
    combined = pd.concat([local, new_rows], ignore_index=True)
    combined = combined.sort_values('交易日')
    combined.to_csv(file_path, index=False)
    
    print(f"添加 {len(new_rows)} 条新数据，总计 {len(combined)} 条")
    return combined

def get_news(code, refresh=False):
    """
    获取新闻数据，每天更新，累积存储，自动去重
    """
    code = normalize_code(code)
    # 使用固定文件名，累积存储
    file_path = os.path.join(NEWS_PATH, f"{code}.csv")
    
    # 读取本地已有数据
    local = _read_csv_if_exists(file_path)
    
    # 获取远程数据（每天都要获取）
    try:
        remote = ak.stock_news_em(symbol=code)
        if remote is None or remote.empty:
            return local
        
        # 处理远程数据
        if '发布时间' in remote.columns:
            remote['发布时间'] = pd.to_datetime(remote['发布时间'])
        
        # 如果没有本地数据，直接保存
        if local is None or local.empty:
            remote.to_csv(file_path, index=False)
            print(f"首次获取 {code} 新闻，共 {len(remote)} 条")
            return remote
        
        # 有本地数据，需要合并去重
        if '发布时间' not in local.columns:
            return remote
        
        local['发布时间'] = pd.to_datetime(local['发布时间'])
        
        # 选择去重字段（优先用链接，其次用标题）
        dedup_field = None
        if '新闻链接' in remote.columns and '新闻链接' in local.columns:
            dedup_field = '新闻链接'
        elif '新闻标题' in remote.columns and '新闻标题' in local.columns:
            dedup_field = '新闻标题'
        
        if dedup_field:
            # 使用链接或标题去重
            existing_values = set(local[dedup_field].dropna())
            new_news = remote[~remote[dedup_field].isin(existing_values)]
        else:
            # 没有合适的去重字段，使用发布时间和标题组合
            local['key'] = local['发布时间'].dt.date.astype(str) + local.get('新闻标题', '')
            remote['key'] = remote['发布时间'].dt.date.astype(str) + remote.get('新闻标题', '')
            existing_keys = set(local['key'])
            new_news = remote[~remote['key'].isin(existing_keys)]
            new_news = new_news.drop(columns=['key'])
        
        if new_news.empty:
            print(f"{code} 没有新新闻，本地已有 {len(local)} 条")
            return local
        
        # 合并新数据
        combined = pd.concat([local, new_news], ignore_index=True)
        
        # 按时间排序
        if '发布时间' in combined.columns:
            combined = combined.sort_values('发布时间')
        
        # 保存
        combined.to_csv(file_path, index=False)
        print(f"{code} 添加 {len(new_news)} 条新新闻，总计 {len(combined)} 条")
        
        return combined
        
    except Exception as e:
        print(f"获取新闻失败 {code}: {e}")
        return local