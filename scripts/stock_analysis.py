#!/usr/bin/env python3
"""
单只股票深度分析脚本
用法: python3 stock_analysis.py <股票代码或名称>
示例: python3 stock_analysis.py 000858 或 python3 stock_analysis.py 茅台
"""

import csv
import json
import os
import re
import sys
import requests
from datetime import datetime, timedelta

# ==================== 配置 ====================
RESULT_DIR = "/home/admin/AUTO-STOCK/src/result"
REPORT_DIR = "/home/admin/AUTO-STOCK/reports/individual"
CACHE_FILE = "/home/admin/AUTO-STOCK/reports/individual/generated_at.json"
POOL_FILE = "/home/admin/AUTO-STOCK/stock_pool.csv"
HIST_PRICE_DIR = "/home/admin/AUTO-STOCK/data/hist_price/"
MX_APIKEY = os.environ.get("MX_APIKEY", "mkt_65LysqK_vB294d8JkHEvwazCMpoMSfdWJFC0Ia1mYuo")
PROGRESS_FILE = "/tmp/stock_analysis_progress_{code}.json"
TRADE_DAYS_FILE = "/home/admin/AUTO-STOCK/data/calendar/trade_days.csv"

FACTOR_LIST = ['关注度', '单日涨跌幅', '股息率', '今年相对大盘强弱', '财报', '5日涨跌幅', '行业相对强弱', '新闻', '资金流向']

FACTOR_WEIGHT = {
    '关注度': 10, '单日涨跌幅': 10, '股息率': 10, '今年相对大盘强弱': 10,
    '财报': 20, '5日涨跌幅': 10, '行业相对强弱': 10, '新闻': 10, '资金流向': 10,
}

# ==================== 妙想API获取涨跌幅 ====================
def get_stock_changepct(code):
    """通过妙想API获取股票当日涨跌幅"""
    try:
        url = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"
        headers = {"Content-Type": "application/json", "apikey": MX_APIKEY}
        payload = {"toolQuery": f"{code}今日涨跌幅"}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            dto_list = result.get('data', {}).get('data', {}).get('searchDataResultDTO', {}).get('dataTableDTOList', [])
            for dto in dto_list:
                table = dto.get('table', {})
                if 'f3' in table and table['f3']:
                    pct_str = table['f3'][0]
                    return float(pct_str.replace('%', '').replace('+', ''))
    except Exception as e:
        print(f"获取涨跌幅失败: {e}")
    return None

def get_historical_changepct(code, date_str):
    """通过妙想API获取指定日期的涨跌幅"""
    try:
        # 将 YYYYMMDD 转为 YYYY-MM-DD
        date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        url = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"
        headers = {"Content-Type": "application/json", "apikey": MX_APIKEY}
        # 查询指定日期的收盘价和涨跌幅
        payload = {"toolQuery": f"{code} {date_formatted} 收盘价 涨跌幅"}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            dto_list = result.get('data', {}).get('data', {}).get('searchDataResultDTO', {}).get('dataTableDTOList', [])
            for dto in dto_list:
                table = dto.get('table', {})
                # 查找涨跌幅字段 (f3)
                for key, val in table.items():
                    if key == 'headName':
                        continue
                    # val 可能是 ["-1.557%"] 格式
                    if val and isinstance(val, list):
                        try:
                            pct_str = val[0].replace('%', '').replace('+', '')
                            return float(pct_str)
                        except:
                            pass
    except Exception as e:
        pass
    return None

def get_multi_day_changepct(code, date_list):
    """批量获取多个日期的涨跌幅"""
    try:
        dates_str = " ".join(date_list)
        url = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"
        headers = {"Content-Type": "application/json", "apikey": MX_APIKEY}
        payload = {"toolQuery": f"{code} {dates_str} 收盘价 涨跌幅"}
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            dto_list = result.get('data', {}).get('data', {}).get('searchDataResultDTO', {}).get('dataTableDTOList', [])
            for dto in dto_list:
                table = dto.get('table', {})
                head_names = table.get('headName', [])
                # 查找涨跌幅数据
                for key, val in table.items():
                    if key == 'headName':
                        continue
                    if val and isinstance(val, list) and len(val) == len(head_names):
                        # 这个key对应的就是涨跌幅
                        pct_map = {}
                        for i, hn in enumerate(head_names):
                            # headName 格式: "2026-05-14(日)"
                            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', hn)
                            if date_match:
                                date_str = date_match.group(1).replace('-', '')
                                try:
                                    pct_str = val[i].replace('%', '').replace('+', '')
                                    pct_map[date_str] = float(pct_str)
                                except:
                                    pass
                        return pct_map
    except Exception as e:
        pass
    return {}
    try:
        url = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"
        headers = {"Content-Type": "application/json", "apikey": MX_APIKEY}
        payload = {"toolQuery": f"{code}今日涨跌幅"}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            dto_list = result.get('data', {}).get('data', {}).get('searchDataResultDTO', {}).get('dataTableDTOList', [])
            for dto in dto_list:
                table = dto.get('table', {})
                if 'f3' in table and table['f3']:
                    pct_str = table['f3'][0]
                    return float(pct_str.replace('%', '').replace('+', ''))
    except Exception as e:
        print(f"获取涨跌幅失败: {e}")
    return None

# ==================== 上一交易日 ====================
TRADE_DAYS_FILE = "/home/admin/AUTO-STOCK/data/calendar/trade_days.csv"

def get_last_trading_day(date_str):
    """根据给定日期返回上一个交易日"""
    with open(TRADE_DAYS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        dates = [row['trade_date'] for row in reader]
    date_map = {d.replace('-', ''): i for i, d in enumerate(dates)}
    if date_str in date_map:
        idx = date_map[date_str]
        if idx > 0:
            return dates[idx - 1].replace('-', '')
    return None

# ==================== 计算因子变化 ====================
def get_factor_change(code, current_date, history):
    """计算各因子与上一交易日相比的变化"""
    prev_date = get_last_trading_day(current_date)
    
    if prev_date not in history or code not in history[prev_date]:
        return None
    
    current_row = history[current_date][code]
    prev_row = history[prev_date][code]
    
    return {f: float(current_row.get(f, 0)) - float(prev_row.get(f, 0)) for f in FACTOR_LIST}

# ==================== 辅助函数 ====================
def load_stock_pool():
    pool = {}
    if os.path.exists(POOL_FILE):
        with open(POOL_FILE, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                pool[row['code'].strip().zfill(6)] = row['name'].strip()
    return pool

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def write_progress(code, progress, message):
    """写入进度到临时文件"""
    pf = PROGRESS_FILE.replace("{code}", code)
    with open(pf, 'w') as f:
        json.dump({"progress": progress, "message": message}, f)

def search_stock_by_name(query, pool):
    results = []
    query_lower = query.lower()
    for code, name in pool.items():
        if query_lower in name.lower() or query in name:
            results.append({'code': code, 'name': name})
    return results

# ==================== 读取数据 ====================
def read_all_history():
    history = {}
    for fname in os.listdir(RESULT_DIR):
        if fname.startswith("batch_result_") and fname.endswith(".csv"):
            date_str = fname.replace("batch_result_", "").replace(".csv", "")
            with open(os.path.join(RESULT_DIR, fname), 'r', encoding='utf-8') as f:
                history[date_str] = {r['code']: r for r in csv.DictReader(f)}
    return history

def get_stock_history(code, history):
    trend = []
    for date_str in sorted(history.keys()):
        if code in history[date_str]:
            row = history[date_str][code]
            trend.append({'date': date_str, 'total_score': float(row['total_score']),
                **{f: float(row.get(f, 0)) for f in FACTOR_LIST}})
    return trend

def get_stock_rank(code, date_str, history):
    if date_str not in history:
        return None, 0
    scores = [(c, float(r['total_score'])) for c, r in history[date_str].items()]
    scores.sort(key=lambda x: x[1], reverse=True)
    for i, (c, s) in enumerate(scores):
        if c == code:
            return i + 1, len(scores)
    return None, len(scores)

def get_factor_distribution(code, date_str, history):
    if date_str not in history or code not in history[date_str]:
        return None
    row = history[date_str][code]
    factors = {}
    for f in FACTOR_LIST:
        val = float(row.get(f, 0))
        tag = "强" if val >= 7 else ("中" if val >= 4 else "弱")
        factors[f] = {'value': val, 'tag': tag, 'weight': FACTOR_WEIGHT.get(f, 10)}
    return factors

# ==================== 分析函数 ====================
def analyze_score_trend(trend):
    if len(trend) < 2:
        return "数据不足，无法判断趋势"
    change = trend[-1]['total_score'] - trend[0]['total_score']
    if change > 5: return f"显著上升 (+{change:.2f})"
    elif change > 2: return f"温和上升 (+{change:.2f})"
    elif change > -2: return f"基本持平 ({change:+.2f})"
    elif change > -5: return f"温和下降 ({change:+.2f})"
    else: return f"显著下降 ({change:+.2f})"

def analyze_factor_strength(factors):
    strong = [f for f, v in factors.items() if v['tag'] == '强']
    medium = [f for f, v in factors.items() if v['tag'] == '中']
    weak = [f for f, v in factors.items() if v['tag'] == '弱']
    weighted_score = sum(factors[f]['value'] for f in FACTOR_LIST)
    max_weighted = sum(factors[f]['weight'] for f in FACTOR_LIST)
    return {'strong': strong, 'medium': medium, 'weak': weak,
            'weighted_score': weighted_score, 'max_weighted': max_weighted,
            'score_pct': weighted_score / max_weighted * 100}

# ==================== 生成 Markdown 报告 ====================
def generate_report(code, history):
    name = ""
    latest_date = sorted(history.keys())[-1]
    if code in history.get(latest_date, {}):
        name = history[latest_date][code].get('name', code)
    
    trend = get_stock_history(code, history)
    if not trend:
        return f"未找到股票 {code} 的评分数据"
    
    lines = []
    lines.append("=" * 60)
    lines.append("单只股票深度分析报告")
    lines.append(f"股票: {code} {name}")
    lines.append(f"数据日期: {trend[0]['date']} ~ {trend[-1]['date']} ({len(trend)} 天)")
    lines.append("=" * 60)
    
    # 一、基本信息
    lines.append("")
    lines.append("-" * 40)
    lines.append("一、基本信息")
    lines.append("-" * 40)
    latest = trend[-1]
    rank, total = get_stock_rank(code, latest['date'], history)
    lines.append(f"  最新总分: {latest['total_score']:.2f}")
    lines.append(f"  全市场排名: 第 {rank} / {total} 名 (前 {rank/total*100:.1f}%)")
    
    # 二、评分走势
    lines.append("")
    lines.append("-" * 40)
    lines.append("二、评分走势")
    lines.append("-" * 40)
    
    latest_date_str = trend[-1]['date']
    
    # 批量获取所有日期的涨跌幅
    date_list = [t['date'] for t in trend]
    pct_map = get_multi_day_changepct(code, date_list)
    
    for t in trend:
        r, total_r = get_stock_rank(code, t['date'], history)
        pct_str = ""
        # 从批量查询结果中获取
        date_key = t['date']
        if date_key in pct_map:
            pct_str = f" ({pct_map[date_key]:+.2f}%)"
        lines.append(f"  {t['date']}: {t['total_score']:.2f}{pct_str} 分 (第 {r}/{total_r} 名)")
    
    lines.append(f"")
    lines.append(f"  趋势判断: {analyze_score_trend(trend)}")
    
    # 三、9因子拆解
    lines.append("")
    lines.append("-" * 40)
    lines.append("三、9因子拆解（最新）")
    lines.append("-" * 40)
    
    factors = get_factor_distribution(code, latest['date'], history)
    factor_changes = get_factor_change(code, latest['date'], history)
    
    if factors:
        factor_analysis = analyze_factor_strength(factors)
        lines.append(f"  {'因子':<12s}  {'数值':<8s}  {'状态':<6s}  {'变化':<8s}  {'权重':<6s}")
        lines.append(f"  {'-' * 12}--{'-' * 10}--{'-' * 8}--{'-' * 10}--{'-' * 6}")
        
        for f in FACTOR_LIST:
            val = factors[f]['value']
            tag = factors[f]['tag']
            weight = factors[f]['weight']
            change = ""
            if factor_changes and f in factor_changes:
                chg = factor_changes[f]
                change = f"{chg:+.2f}" if chg != 0 else "0.00"
            else:
                change = "-"
            lines.append(f"  {f:<12s}  {val:<8.2f}  {tag:<6s}  {change:<8s}  {weight:<6d}")
        
        lines.append(f"  {'-' * 12}--{'-' * 10}--{'-' * 8}--{'-' * 10}--{'-' * 6}")
        lines.append(f"  {'加权总分':<12s}  {factor_analysis['weighted_score']:<8.2f}  {'':<6s}  {'':<8s}")
        
        lines.append(f"")
        strong_str = ', '.join(factor_analysis['strong']) if factor_analysis['strong'] else '无'
        medium_str = ', '.join(factor_analysis['medium']) if factor_analysis['medium'] else '无'
        weak_str = ', '.join(factor_analysis['weak']) if factor_analysis['weak'] else '无'
        lines.append(f"  强势因子 ({len(factor_analysis['strong'])}个): {strong_str}")
        lines.append(f"  中性因子 ({len(factor_analysis['medium'])}个): {medium_str}")
        lines.append(f"  弱势因子 ({len(factor_analysis['weak'])}个): {weak_str}")
        lines.append(f"")
        lines.append(f"  加权得分率: {factor_analysis['score_pct']:.1f}%")
    
    # 四、投资建议
    lines.append("")
    lines.append("-" * 40)
    lines.append("四、投资建议")
    lines.append("-" * 40)
    
    score = latest['total_score']
    trend_change = trend[-1]['total_score'] - trend[0]['total_score'] if len(trend) >= 2 else 0
    
    if score >= 60 and trend_change > 0:
        lines.append(f"  推荐关注: 高分+上升趋势，值得重点跟踪")
    elif score >= 50 and trend_change > 0:
        lines.append(f"  值得关注: 中等分数+上升趋势，可纳入观察池")
    elif score >= 50:
        lines.append(f"  中性: 分数中等但趋势不明，建议继续观察")
    elif score >= 30:
        lines.append(f"  谨慎: 分数偏低，需等待改善信号")
    else:
        lines.append(f"  回避: 分数较低，建议规避")
    
    lines.append("")
    lines.append("=" * 60)
    lines.append("分析报告完毕 | 1号自动评分系统")
    lines.append("=" * 60)
    
    return "\n".join(lines)

# ==================== 生成 HTML 报告 ====================
def generate_html_report(code, name, trend, history):
    if not trend:
        return "<html><body><h1>未找到数据</h1></body></html>"
    
    latest = trend[-1]
    rank, total = get_stock_rank(code, latest['date'], history)
    factors = get_factor_distribution(code, latest['date'], history)
    factor_analysis = analyze_factor_strength(factors) if factors else None
    changepct = get_stock_changepct(code)
    factor_changes = get_factor_change(code, latest['date'], history)
    
    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="zh-CN">')
    lines.append('<head>')
    lines.append('  <meta charset="UTF-8">')
    lines.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    lines.append(f'  <title>{code} {name} - 深度分析报告</title>')
    lines.append('  <style>')
    lines.append('    body { font-family: sans-serif; padding: 20px; background: #f5f5f5; }')
    lines.append('    .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }')
    lines.append('    h1 { color: #667eea; text-align: center; }')
    lines.append('    h2 { color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px; margin-top: 20px; }')
    lines.append('    table { width: 100%; border-collapse: collapse; margin: 15px 0; }')
    lines.append('    th, td { padding: 10px; text-align: center; border-bottom: 1px solid #eee; }')
    lines.append('    th { background: #f8f9fa; font-weight: 600; }')
    lines.append('    .strong { color: #22c55e; font-weight: 600; }')
    lines.append('    .weak { color: #ef4444; font-weight: 600; }')
    lines.append('    .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 15px 0; }')
    lines.append('    .stat-card { background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }')
    lines.append('    .stat-card .value { font-size: 24px; font-weight: 700; color: #667eea; }')
    lines.append('    .stat-card .label { font-size: 12px; color: #666; margin-top: 5px; }')
    lines.append('    .footer { text-align: center; color: #999; margin-top: 20px; font-size: 12px; }')
    lines.append('    .recommend-strong { background: #dcfce7; padding: 15px; border-radius: 8px; margin: 15px 0; }')
    lines.append('    .recommend-weak { background: #fee2e2; padding: 15px; border-radius: 8px; margin: 15px 0; }')
    lines.append('    .recommend-neutral { background: #fef9c3; padding: 15px; border-radius: 8px; margin: 15px 0; }')
    lines.append('    .back-link { text-align: center; margin-top: 20px; }')
    lines.append('    .back-link a { color: #667eea; text-decoration: none; }')
    lines.append('  .sgrid{grid-template-columns:repeat(2,1fr)}table{font-size:11px}th,td{padding:6px 8px}}.container{padding:12px;border-radius:8px}.stat-grid{grid-template-columns:repeat(3,1fr);gap:8px}.stat-card{padding:10px}.stat-card .value{font-size:18px}.stat-card .label{font-size:10px}table{font-size:11px}th,td{padding:6px 8px}h1{font-size:18px}h2{font-size:14px}}.container{padding:10px;border-radius:6px;margin:0 5px}.stat-grid{grid-template-columns:repeat(3,1fr);gap:6px}.stat-card{padding:6px}.stat-card .value{font-size:16px}.stat-card .label{font-size:9px}table{font-size:10px}th,td{padding:4px 3px}h1{font-size:16px}h2{font-size:13px}.recommend-strong,.recommend-weak,.recommend-neutral{padding:8px;font-size:11px}}@media(max-width:600px){body{padding:8px}.container{padding:10px;border-radius:6px;margin:0 5px}.stat-grid{grid-template-columns:repeat(3,1fr);gap:6px}.stat-card{padding:6px}.stat-card .value{font-size:16px}.stat-card .label{font-size:9px}table{font-size:10px}th,td{padding:4px 3px}h1{font-size:16px}h2{font-size:13px}.recommend-strong,.recommend-weak,.recommend-neutral{padding:8px;font-size:11px}}</style>\n')
    lines.append('</head>')
    lines.append('<body>')
    lines.append('  <div class="container">')
    lines.append(f'    <h1>{code} {name} 深度分析报告</h1>')
    
    # 一、基本信息
    lines.append('    <h2>一、基本信息</h2>')
    lines.append('    <div class="stat-grid">')
    lines.append(f'      <div class="stat-card"><div class="value">{latest["total_score"]:.2f}</div><div class="label">最新总分</div></div>')
    lines.append(f'      <div class="stat-card"><div class="value">{rank}/{total}</div><div class="label">全市场排名</div></div>')
    lines.append(f'      <div class="stat-card"><div class="value">{len(trend)}天</div><div class="label">数据天数</div></div>')
    lines.append('    </div>')
    
    # 二、评分走势
    lines.append('    <h2>二、评分走势</h2>')
    lines.append('    <table>')
    lines.append('      <thead><tr><th>日期</th><th>总分</th><th>当日涨跌幅</th><th>排名</th></tr></thead>')
    lines.append('      <tbody>')
    
    latest_date_str = trend[-1]['date']
    # 批量获取所有日期的涨跌幅
    date_list = [t['date'] for t in trend]
    pct_map = get_multi_day_changepct(code, date_list)

    # 最多显示最近5条
    display_trend = trend[-5:]
    for t in display_trend:
        r, total_r = get_stock_rank(code, t['date'], history)
        pct_html = '<td>-</td>'
        date_key = t['date']
        if date_key in pct_map:
            pct = pct_map[date_key]
            # 红涨绿跌
            color = '#ef4444' if pct > 0 else '#22c55e'
            pct_html = f'<td style="color:{color};">{pct:+.2f}%</td>'
        lines.append(f'        <tr><td>{t["date"]}</td><td>{t["total_score"]:.2f}</td>{pct_html}<td>{r}/{total_r}</td></tr>')
    
    lines.append('      </tbody>')
    lines.append('    </table>')
    
    # 趋势判断
    if len(trend) >= 2:
        change = trend[-1]['total_score'] - trend[0]['total_score']
        trend_text = '上升' if change > 0 else ('下降' if change < 0 else '持平')
        lines.append(f'    <p style="text-align:center;font-size:18px;color:#667eea;">趋势判断: {trend_text} ({change:+.2f})</p>')
    
    # 三、9因子拆解
    if factors:
        lines.append('    <h2>三、9因子拆解</h2>')
        lines.append('    <table>')
        lines.append('      <thead><tr><th>因子</th><th>数值</th><th>状态</th><th>变化</th><th>权重</th></tr></thead>')
        lines.append('      <tbody>')
        
        for f in FACTOR_LIST:
            val = factors[f]['value']
            tag = factors[f]['tag']
            weight = factors[f]['weight']
            tag_class = 'strong' if tag == '强' else ('weak' if tag == '弱' else '')
            
            if factor_changes and f in factor_changes:
                chg = factor_changes[f]
                if chg > 0:
                    change_html = f'<td style="color:#22c55e;">+{chg:.2f}</td>'
                elif chg < 0:
                    change_html = f'<td style="color:#ef4444;">{chg:.2f}</td>'
                else:
                    change_html = '<td>0.00</td>'
            else:
                change_html = '<td>-</td>'
            
            lines.append(f'        <tr><td>{f}</td><td>{val:.2f}</td><td class="{tag_class}">{tag}</td>{change_html}<td>{weight}</td></tr>')
        
        lines.append('      </tbody>')
        lines.append('    </table>')
        
        strong_str = ', '.join(factor_analysis['strong']) if factor_analysis['strong'] else '无'
        weak_str = ', '.join(factor_analysis['weak']) if factor_analysis['weak'] else '无'
        lines.append(f'    <p><strong>强势因子:</strong> {strong_str}</p>')
        lines.append(f'    <p><strong>弱势因子:</strong> {weak_str}</p>')
    
    # 四、投资建议
    lines.append('    <h2>四、投资建议</h2>')
    score = latest['total_score']
    trend_change = trend[-1]['total_score'] - trend[0]['total_score'] if len(trend) >= 2 else 0
    
    if score >= 60 and trend_change > 0:
        lines.append('    <div class="recommend-strong"><strong>推荐关注:</strong> 高分+上升趋势，值得重点跟踪</div>')
    elif score >= 50 and trend_change > 0:
        lines.append('    <div class="recommend-neutral"><strong>值得关注:</strong> 中等分数+上升趋势，可纳入观察池</div>')
    elif score >= 50:
        lines.append('    <div class="recommend-neutral"><strong>中性:</strong> 分数中等但趋势不明，建议继续观察</div>')
    elif score >= 30:
        lines.append('    <div class="recommend-weak"><strong>谨慎:</strong> 分数偏低，需等待改善信号</div>')
    else:
        lines.append('    <div class="recommend-weak"><strong>回避:</strong> 分数较低，建议规避</div>')
    
    lines.append('    <div class="back-link">')
    lines.append('      <a href="/reports/index.html">← 返回全体页面</a>')
    lines.append('    </div>')
    
    lines.append('    <div class="footer">')
    lines.append(f'      分析报告完毕 | 1号自动评分系统<br>')
    lines.append(f'      生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append('    </div>')
    lines.append('  </div>')
    lines.append('</body>')
    lines.append('</html>')
    
    return "\n".join(lines)

# ==================== 主程序 ====================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 stock_analysis.py <股票代码或名称>")
        print("示例: python3 stock_analysis.py 000858 或 python3 stock_analysis.py 茅台")
        sys.exit(1)
    
    query = sys.argv[1].strip()
    pool = load_stock_pool()
    cache = load_cache()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 解析股票代码
    if query.isdigit():
        code = query.zfill(6)
    else:
        results = search_stock_by_name(query, pool)
        if len(results) == 1:
            code = results[0]['code']
            print(f"找到股票: {code} {results[0]['name']}")
        elif len(results) == 0:
            print(f"未找到股票 '{query}'")
            print("该股票不在沪深300或中证1000成分股范围内，请检查代码或名称")
            sys.exit(1)
        else:
            print(f"找到多个匹配，请指定具体代码:")
            for r in results[:10]:
                print(f"  {r['code']} {r['name']}")
            sys.exit(1)
    
    # 检查是否在股票池中
    if code not in pool:
        print(f"股票 {code} 不在成分股范围内")
        print("该股票不在沪深300或中证1000成分股范围内，请检查代码或名称")
        sys.exit(1)
    
    name = pool[code]
    
    # 检查缓存
    if code in cache and cache[code] == today:
        print(f"{code} {name} 今天已生成报告，无需重新生成")
        print(f"报告路径: {REPORT_DIR}/stock_analysis_{code}.html")
        sys.exit(0)
    
    print(f"正在分析股票 {code} {name}...")

    write_progress(code, 5, "加载历史数据...")
    history = read_all_history()

    write_progress(code, 30, "正在生成报告...")
    report = generate_report(code, history)
    print(report)

    write_progress(code, 60, "正在获取涨跌幅数据...")
    trend = get_stock_history(code, history)
    html_report = generate_html_report(code, name, trend, history)

    write_progress(code, 90, "正在保存报告...")
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    # 保存文件
    with open(os.path.join(REPORT_DIR, f"stock_analysis_{code}.md"), 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nMarkdown 报告已保存: {REPORT_DIR}/stock_analysis_{code}.md")
    
    with open(os.path.join(REPORT_DIR, f"stock_analysis_{code}.html"), 'w', encoding='utf-8') as f:
        f.write(html_report)
    print(f"HTML 报告已保存: {REPORT_DIR}/stock_analysis_{code}.html")
    
    # 更新缓存
    cache[code] = today
    save_cache(cache)
    print(f"缓存已更新: {code} -> {today}")

    write_progress(code, 100, "完成")
    pf = PROGRESS_FILE.replace("{code}", code)
    if os.path.exists(pf):
        os.remove(pf)