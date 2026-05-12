import os
from datetime import datetime, timedelta
import time

import akshare as ak
import pandas as pd

DATA_DIR = "data"
PRICE_PATH = os.path.join(DATA_DIR, "price")
FINANCE_PATH = os.path.join(DATA_DIR, "finance")
DIVIDEND_PATH = os.path.join(DATA_DIR, "dividend")
ATTENTION_PATH = os.path.join(DATA_DIR, "attention")
NEWS_PATH = os.path.join(DATA_DIR, "news")
INDUSTRY_PATH = os.path.join(DATA_DIR, "industry")
FUND_PATH = os.path.join(DATA_DIR, "fund")


for path in [PRICE_PATH, FINANCE_PATH, DIVIDEND_PATH, ATTENTION_PATH, NEWS_PATH, INDUSTRY_PATH, FUND_PATH]:
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


def get_stock_industry(code):
    """获取个股所属的行业板块（从本地映射文件）"""
    code = normalize_code(code)

    mapping_file = os.path.join(INDUSTRY_PATH, "stock_industry_mapping.csv")
    mapping_df = _read_csv_if_exists(mapping_file)

    if mapping_df is not None and not mapping_df.empty:
        match = mapping_df[mapping_df['股票代码'] == code]
        if not match.empty:
            return match.iloc[0]['行业名称']

    return None


def build_industry_mapping():
    """构建股票代码→行业板块的映射表（网络恢复后运行）"""
    import time
    mapping_file = os.path.join(INDUSTRY_PATH, "stock_industry_mapping.csv")

    existing = _read_csv_if_exists(mapping_file)
    if existing is not None and not existing.empty:
        print(f"行业映射已存在，共 {len(existing)} 条记录")
        return existing

    print("开始构建行业映射表（东方财富）...")

    max_retries = 3

    def get_with_retry(func, *args, **kwargs):
        """带重试的请求"""
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f"    重试 {i+1}/{max_retries}: {e}")
                time.sleep(2)
        return None

    try:
        # 1. 获取所有行业板块列表
        industry_list_df = get_with_retry(ak.stock_board_industry_name_em)
        if industry_list_df is None or industry_list_df.empty:
            print("无法获取行业列表")
            return None

        print(f"共 {len(industry_list_df)} 个行业板块")

        all_mappings = []

        # 2. 遍历每个行业，获取成分股
        for idx, row in industry_list_df.iterrows():
            industry_name = row.get('板块名称')
            if not industry_name:
                continue

            print(f"  处理: {industry_name}")

            try:
                # 获取该行业的成分股
                cons_df = get_with_retry(ak.stock_board_industry_cons_em, symbol=industry_name)
                if cons_df is None or cons_df.empty:
                    time.sleep(0.5)
                    continue

                # 提取股票代码
                for _, cons_row in cons_df.iterrows():
                    code = str(cons_row.get('代码', ''))
                    if code and code != 'nan':
                        code = code.zfill(6)
                        all_mappings.append({
                            '股票代码': code,
                            '行业名称': industry_name
                        })

                time.sleep(0.8)  # 延时避免被封

            except Exception as e:
                print(f"    {industry_name} 失败: {e}")
                time.sleep(2)
                continue

        if all_mappings:
            mapping_df = pd.DataFrame(all_mappings)
            mapping_df = mapping_df.drop_duplicates(subset=['股票代码'])
            mapping_df.to_csv(mapping_file, index=False)
            print(f"映射构建完成，共 {len(mapping_df)} 只股票")
            return mapping_df

        return None

    except Exception as e:
        print(f"构建行业映射失败: {e}")
        return existing


def get_industry_change(industry_name, industry_code=None, days=20):
    """获取申万行业近期涨跌幅（本地缓存优先，不再发起网络请求）

    注意：为避免IP被封，行业涨跌幅数据需提前通过 build_industry_data.py 构建
    """
    if not industry_name and not industry_code:
        return None

    # 新方法：从新构建的缓存文件中读取
    # 缓存文件命名：change_{行业代码}_{days}d.csv
    if industry_name:
        # 尝试查找行业代码
        industry_code = _get_sw_code(industry_name)

    if industry_code:
        code = industry_code
        file_path = os.path.join(INDUSTRY_PATH, f"change_{code}_{days}d.csv")

        local = _read_csv_if_exists(file_path)
        if local is not None and not local.empty:
            return local

    # 旧方法：如果找不到缓存，尝试从原始行业映射文件查找（已废弃，不推荐）
    if not industry_code:
        mapping_file = os.path.join(INDUSTRY_PATH, "stock_industry_mapping.csv")
        mapping_df = _read_csv_if_exists(mapping_file)
        if mapping_df is not None and not mapping_df.empty:
            match = mapping_df[mapping_df['行业名称'] == industry_name]
            if not match.empty and '行业代码' in match.columns:
                industry_code = str(match.iloc[0]['行业代码']).replace('.SI', '')

    if industry_code:
        code = industry_code
        file_path = os.path.join(INDUSTRY_PATH, f"change_{code}_{days}d.csv")

        local = _read_csv_if_exists(file_path)
        if local is not None and not local.empty:
            return local

    # 如果缓存不存在，返回 None（不再发起网络请求，避免被封）
    print(f"提示: 行业 {industry_name} 的涨跌幅数据不存在")
    print(f"      请运行: python -m src.datafactory.build_industry_data --changes")
    return None


def _get_sw_code(industry_name):
    """获取申万行业代码（简化版）"""
    # 常用行业代码映射
    SW_CODE_MAP = {
        '银行': '801780',
        '非银金融': '801790',
        '房地产': '801720',
        '农林牧渔': '801010',
        '化工': '801030',
        '钢铁': '801020',
        '有色金属': '801050',
        '建筑材料': '801050',
        '建筑装饰': '801720',
        '电气设备': '801730',
        '机械设备': '801730',
        '汽车': '801880',
        '轻工制造': '801110',
        '纺织服装': '801110',
        '家用电器': '801130',
        '食品饮料': '801150',
        '休闲服务': '801210',
        '商业贸易': '801200',
        '医药生物': '801150',
        '电子': '801080',
        '计算机': '801750',
        '传媒': '801760',
        '通信': '801770',
        '公用事业': '801210',
        '交通运输': '801020',
        '采掘': '801020',
        '综合': '801010',
        '国防军工': '801660',
    }

    for key in SW_CODE_MAP:
        if key in industry_name:
            return SW_CODE_MAP[key]

    return None


def get_fund_flow_5day(refresh=False):
    """获取同花顺5日资金流向数据（每日更新，缓存本地）"""
    file_path = os.path.join(FUND_PATH, "fund_flow_5day.csv")

    local = _read_csv_if_exists(file_path)
    if not refresh and local is not None and not local.empty:
        # 检查是否需要更新（当天数据）
        if 'update_date' in local.columns:
            today = datetime.now().strftime('%Y-%m-%d')
            if local['update_date'].iloc[0] == today:
                return local

    try:
        remote = ak.stock_fund_flow_individual(symbol='5日排行')
        if remote is None or remote.empty:
            return local

        # 添加更新日期
        remote['update_date'] = datetime.now().strftime('%Y-%m-%d')

        # 标准化股票代码（去掉空格，补齐6位）
        if '股票代码' in remote.columns:
            remote['股票代码'] = remote['股票代码'].astype(str).str.strip().str.zfill(6)

        remote.to_csv(file_path, index=False)
        print(f"更新5日资金流数据，共 {len(remote)} 条")
        return remote

    except Exception as e:
        print(f"获取5日资金流失败: {e}")
        return local


def get_stock_fund_flow(code):
    """获取单只股票的5日资金流数据"""
    code = normalize_code(code)

    # 先确保有最新数据
    df = get_fund_flow_5day()
    if df is None or df.empty:
        return None

    # 查找该股票（将股票代码转为字符串匹配）
    df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
    match = df[df['股票代码'] == code]
    if match.empty:
        return None

    return match.iloc[0]


# ========== 财报公告日期相关 ==========
import re

DISCLOSURE_PATH = os.path.join(DATA_DIR, "disclosure")
os.makedirs(DISCLOSURE_PATH, exist_ok=True)

def _extract_report_period(title: str) -> str:
    """从公告标题提取报告期日期"""
    # 清理HTML标签
    title = title.replace('<em>', '').replace('</em>', '')

    if '年度报告' in title and '摘要' not in title:
        # 匹配 "2025年年度报告" 或 "2024年年度报告" - 中间可能有"年"
        match = re.search(r'(\d{4})年.*年度', title)
        if match:
            return f"{match.group(1)}-12-31"
    elif '半年度' in title or '半年报' in title:
        # 匹配 "2025年半年度报告" - 中间可能有"年"
        if '摘要' not in title:
            match = re.search(r'(\d{4})年.*半年度', title)
            if match:
                return f"{match.group(1)}-06-30"
    elif '第一季度' in title:
        # 匹配 "2026年第一季度报告"
        match = re.search(r'(\d{4})年第一季度', title)
        if match:
            return f"{match.group(1)}-03-31"
    elif '一季度' in title:
        # 匹配 "2026年一季度报告"
        match = re.search(r'(\d{4})年一季度', title)
        if match:
            return f"{match.group(1)}-03-31"
    elif '第三季度' in title:
        # 匹配 "2025年第三季度报告"
        match = re.search(r'(\d{4})年第三季度', title)
        if match:
            return f"{match.group(1)}-09-30"
    elif '三季度' in title:
        # 匹配 "2025年三季度报告"
        match = re.search(r'(\d{4})年三季度', title)
        if match:
            return f"{match.group(1)}-09-30"
    return None


def _get_report_type(title: str) -> str:
    """从公告标题判断财报类型"""
    if '年度报告' in title and '摘要' not in title:
        return "年报"
    elif '半年度' in title or '半年报' in title:
        if '摘要' not in title:
            return "中报"
    elif '第一季度' in title or '一季度' in title:
        return "一季报"
    elif '第三季度' in title or '三季度' in title:
        return "三季报"
    return None


def _is_cache_expired(cache_df, finance_df):
    """判断缓存是否过期：最新财务报告期 > 缓存中最新报告期"""
    if cache_df is None or cache_df.empty or finance_df is None or finance_df.empty:
        return True

    # 获取财务数据最新报告期
    finance_periods = finance_df['报告期'].dropna().unique()
    if len(finance_periods) == 0:
        return True
    latest_finance_period = max(finance_periods)

    # 获取缓存中最新报告期
    cache_periods = cache_df['报告期'].dropna().unique()
    if len(cache_periods) == 0:
        return True
    latest_cache_period = max(cache_periods)

    # 如果财务数据报告期比缓存新，说明缓存过期
    return latest_finance_period > latest_cache_period


def get_disclosure_dates(code, refresh=False):
    """获取财报披露日期列表（含报告期匹配）

    返回格式:
    [
        {"报告期": "2025-12-31", "公告日期": "2026-04-30", "类型": "年报"},
        {"报告期": "2025-09-30", "公告日期": "2025-10-30", "类型": "三季报"},
        ...
    ]
    """
    code = normalize_code(code)
    file_path = os.path.join(DISCLOSURE_PATH, f"{code}.csv")

    # 尝试读取缓存
    local = _read_csv_if_exists(file_path)

    # 获取财务数据（用于判断缓存是否过期）
    finance_df = get_finance(code)

    # 检查缓存是否过期
    if not refresh and local is not None and not local.empty:
        if not _is_cache_expired(local, finance_df):
            # 缓存有效，返回缓存数据
            return local.to_dict('records')

    # 缓存过期或不存在，需要重新获取
    try:
        # 动态确定日期范围（过去2年到未来3个月）
        now = datetime.now()
        start_date = (now - timedelta(days=730)).strftime('%Y%m%d')
        end_date = (now + timedelta(days=90)).strftime('%Y%m%d')

        remote = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=code,
            keyword='报告',
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        print(f"获取公告日期失败 {code}: {e}")
        # 返回过期缓存或空
        if local is not None and not local.empty:
            return local.to_dict('records')
        return []

    if remote is None or remote.empty:
        if local is not None and not local.empty:
            return local.to_dict('records')
        return []

    # 清理标题中的HTML标签
    remote['标题_clean'] = remote['公告标题'].str.replace('<em>', '', regex=False).str.replace('</em>', '', regex=False)

    # 提取报告期
    remote['报告期'] = remote['标题_clean'].apply(_extract_report_period)
    remote['类型'] = remote['标题_clean'].apply(_get_report_type)

    # 过滤出财报类型
    financial_reports = remote[remote['报告期'].notna()].copy()
    if financial_reports.empty:
        if local is not None and not local.empty:
            return local.to_dict('records')
        return []

    # 提取公告日期（只取日期部分）
    financial_reports['公告日期'] = financial_reports['公告时间'].str[:10]

    # 去重：同一报告期保留最新公告
    financial_reports = financial_reports.sort_values('公告日期')
    financial_reports = financial_reports.drop_duplicates(subset=['报告期'], keep='last')

    # 准备输出
    result = financial_reports[['报告期', '公告日期', '类型']].copy()
    result = result.sort_values('报告期', ascending=False)

    # 保存到本地缓存
    result.to_csv(file_path, index=False)
    print(f"更新公告日期缓存 {code}，共 {len(result)} 条")

    return result.to_dict('records')


def get_disclosure_date_by_quarter(code, quarter: str = "本季度"):
    """根据季度获取对应的公告日期

    quarter: "本季度" / "上季度" / "上上季度"
    """
    disclosure_list = get_disclosure_dates(code)
    if not disclosure_list:
        return None

    # 构建报告期到公告日期的映射
    period_to_date = {d['报告期']: d['公告日期'] for d in disclosure_list}

    # 获取财务数据确定当前有哪些报告期
    finance_df = get_finance(code)
    if finance_df is None or finance_df.empty:
        return None

    # 获取所有报告期，按时间倒序
    periods = finance_df['报告期'].dropna().unique()
    periods = sorted(periods, reverse=True)

    # 映射 quarter 到索引
    quarter_map = {"本季度": 0, "上季度": 1, "上上季度": 2}
    idx = quarter_map.get(quarter, 0)

    if idx >= len(periods):
        return None

    target_period = periods[idx]
    disclosure_date = period_to_date.get(target_period)

    if disclosure_date:
        return {
            "报告期": target_period,
            "公告日期": disclosure_date,
            "类型": next((d['类型'] for d in disclosure_list if d['报告期'] == target_period), "")
        }
    return None


def get_kline_after_disclosure(code, quarter: str = "本季度", days: int = 7):
    """获取财报公告发布后N个交易日的K线数据

    返回: {"报告期": "", "公告日期": "", "类型": "", "kline": [], "error": ""}
    """
    # 检查公告日期
    disclosure_info = get_disclosure_date_by_quarter(code, quarter)
    if not disclosure_info or not disclosure_info.get('公告日期'):
        return {"error": f"未找到 {quarter} 的财报公告日期", "kline": []}

    # 获取价格数据
    price_df = get_price(code)
    if price_df is None or price_df.empty:
        return {"error": "未找到价格数据，请先更新行情数据", "kline": []}

    # 转换日期格式
    price_df = price_df.copy()
    price_df['日期'] = pd.to_datetime(price_df['日期'].astype(str), format='%Y%m%d')

    # 公告日期
    disclosure_date = pd.to_datetime(disclosure_info['公告日期'])

    # 找到公告日期之前的最后一个交易日（用于计算涨跌幅）
    before_disclosure = price_df[price_df['日期'] <= disclosure_date].sort_values('日期')
    prev_close = None
    if not before_disclosure.empty:
        prev_close = float(before_disclosure.iloc[-1]['收盘'])

    # 找到公告日期之后的N个交易日
    after_disclosure = price_df[price_df['日期'] > disclosure_date].head(days)

    if after_disclosure.empty:
        return {
            "报告期": disclosure_info['报告期'],
            "公告日期": disclosure_info['公告日期'],
            "类型": disclosure_info['类型'],
            "prev_close": prev_close,
            "kline": [],
            "error": f"公告日期 {disclosure_info['公告日期']} 后无交易数据（可能是节假日前后）"
        }

    # 转换为真实的OHLC格式
    kline = []
    for _, row in after_disclosure.iterrows():
        # 处理NaN值，转换为None以确保JSON兼容
        def safe_float(val):
            import math
            v = float(val)
            return v if not math.isnan(v) else None

        kline.append({
            "date": row['日期'].strftime('%Y-%m-%d'),
            "open": safe_float(row['开盘']),
            "close": safe_float(row['收盘']),
            "high": safe_float(row['最高']),
            "low": safe_float(row['最低']),
            "volume": safe_float(row.get('成交额', 0)) if '成交额' in row and pd.notna(row.get('成交额')) else 0
        })

    return {
        "报告期": disclosure_info['报告期'],
        "公告日期": disclosure_info['公告日期'],
        "类型": disclosure_info['类型'],
        "prev_close": prev_close,
        "kline": kline,
        "error": ""
    }
