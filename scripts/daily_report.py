#!/usr/bin/env python3
"""
每日多因子评分分析报告生成器
生成日期: 2026-05-13
作者: 1号
"""

import csv
import os
import sys
import requests
import re
from datetime import datetime, timedelta

# ==================== 上一交易日 ====================
TRADE_DAYS_FILE = "/home/admin/AUTO-STOCK/data/calendar/trade_days.csv"

def get_last_trading_day(date_str):
    """根据给定日期返回上一个交易日（跳过周末和假节日）"""
    with open(TRADE_DAYS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        dates = [row['trade_date'] for row in reader]
    date_map = {d.replace('-', ''): i for i, d in enumerate(dates)}
    if date_str in date_map:
        idx = date_map[date_str]
        if idx > 0:
            return dates[idx - 1].replace('-', '')
    return None

# ==================== 配置 ====================
RESULT_DIR = "/home/admin/AUTO-STOCK/result/daily_score"
SELF_STOCK_FILE = "/home/admin/AUTO-STOCK/stock_self_selected.csv"
FOCUS_STOCK_FILE = "/home/admin/AUTO-STOCK/stock_focus.csv"

# ==================== 配置 ====================
RESULT_DIR = "/home/admin/AUTO-STOCK/result/daily_score"
SELF_STOCK_FILE = "/home/admin/AUTO-STOCK/stock_self_selected.csv"
FOCUS_STOCK_FILE = "/home/admin/AUTO-STOCK/stock_focus.csv"

# ==================== 从本地数据获取涨跌幅 ====================
PRICE_DIR = "/home/admin/AUTO-STOCK/data/price"

def get_stock_changepct(codes):
    """从本地CSV文件获取股票今日涨跌幅"""
    results = {}
    if not codes:
        return results

    for code in codes:
        try:
            filepath = os.path.join(PRICE_DIR, f"{code}.csv")
            if not os.path.exists(filepath):
                continue
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if len(rows) >= 2:
                    today_close = float(rows[-1]['收盘'])
                    yest_close = float(rows[-2]['收盘'])
                    if yest_close > 0:
                        pct = (today_close - yest_close) / yest_close * 100
                        results[code] = round(pct, 2)
        except Exception as e:
            pass

    return results

def get_stock_price_info(codes):
    """从本地CSV文件获取股票收盘价和涨跌幅"""
    results = {}
    if not codes:
        return results

    for code in codes:
        try:
            filepath = os.path.join(PRICE_DIR, f"{code}.csv")
            if not os.path.exists(filepath):
                continue
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if len(rows) >= 1:
                    today_close = float(rows[-1]['收盘'])
                    today_date = rows[-1]['日期']
                    pct = None
                    if len(rows) >= 2:
                        yest_close = float(rows[-2]['收盘'])
                        if yest_close > 0:
                            pct = round((today_close - yest_close) / yest_close * 100, 2)
                    results[code] = {'close': today_close, 'date': today_date, 'change_pct': pct}
        except Exception as e:
            pass

    return results

# ==================== 读取数据 ====================
def read_result(date_str):
    filepath = os.path.join(RESULT_DIR, f"batch_result_{date_str}.csv")
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def read_all_history():
    history = {}
    for fname in os.listdir(RESULT_DIR):
        if fname.startswith("batch_result_") and fname.endswith(".csv"):
            date_str = fname.replace("batch_result_", "").replace(".csv", "")
            data = read_result(date_str)
            if data:
                history[date_str] = data
    return history

def read_self_stock():
    stocks = set()
    if os.path.exists(SELF_STOCK_FILE):
        with open(SELF_STOCK_FILE, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                stocks.add(row['code'])
    return stocks

def read_focus_stock():
    stocks = {}
    if os.path.exists(FOCUS_STOCK_FILE):
        with open(FOCUS_STOCK_FILE, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                stocks[row['code']] = row['name']
    return stocks

# ==================== 因子分析 ====================
FACTOR_NAMES = {
    '关注度': '关注度', '单日涨跌幅': '单日涨跌幅', '股息率': '股息率',
    '今年相对大盘强弱': '相对大盘', '财报': '财报', '5日涨跌幅': '5日涨跌',
    '行业相对强弱': '行业强弱', '新闻': '新闻', '资金流向': '资金流向',
}

FACTOR_LIST = ['关注度', '单日涨跌幅', '股息率', '今年相对大盘强弱', '财报', '5日涨跌幅', '行业相对强弱', '新闻', '资金流向']

def get_score_distribution(data):
    scores = [float(r['total_score']) for r in data]
    buckets = {}
    ranges = [('90+', 90, float('inf')), ('80-90', 80, 90), ('70-80', 70, 80),
              ('60-70', 60, 70), ('50-60', 50, 60), ('40-50', 40, 50),
              ('30-40', 30, 40), ('20-30', 20, 30), ('10-20', 10, 20), ('10以下', 0, 10)]
    for name, low, high in ranges:
        buckets[name] = sum(1 for s in scores if low <= s < high)
    return buckets, scores

def get_top_n(data, n=10):
    return sorted(data, key=lambda x: float(x['total_score']), reverse=True)[:n]

def get_factor_champions(data, factor):
    return sorted(data, key=lambda x: float(x.get(factor, 0)), reverse=True)[:5]

def display_width(s):
    """计算字符串的显示宽度（中文字符=2，ASCII=1）"""
    return sum(2 if ord(c) > 127 else 1 for c in s)

def pad_to_width(s, width):
    """将字符串补齐到指定显示宽度"""
    return s + ' ' * (width - display_width(s))

def get_score_trend(code, history):
    """获取某股票在所有可用日期中的评分走势"""
    trend = []
    for date_str in sorted(history.keys(), reverse=True):
        for row in history[date_str]:
            if row['code'] == code:
                trend.append({'date': date_str, 'score': float(row['total_score'])})
                break
    return trend

def compare_yesterday(today_data, yesterday_data):
    if not yesterday_data:
        return None
    yest_map = {r['code']: r for r in yesterday_data}
    changes = []
    for r in today_data:
        if r['code'] in yest_map:
            change = float(r['total_score']) - float(yest_map[r['code']]['total_score'])
            changes.append({'code': r['code'], 'name': r['name'],
                           'today': float(r['total_score']),
                           'yesterday': float(yest_map[r['code']]['total_score']),
                           'change': change})
    return changes

def get_latest_rank(code, history):
    """获取某股票在全市场中的最新排名"""
    latest = {}
    for date_str, rows in history.items():
        for r in rows:
            c = r['code']
            s = float(r['total_score'])
            if c not in latest or s > latest[c][1]:
                latest[c] = (r['name'], s)
    sorted_list = sorted(latest.items(), key=lambda x: x[1][1], reverse=True)
    for i, (c, (n, s)) in enumerate(sorted_list):
        if c == code:
            return i + 1, len(sorted_list)
    return None, len(sorted_list)

# ==================== 特别关注股票分析 ====================
def analyze_focus_stock(code, name, today_row, history, yesterday_data=None):
    lines = []
    lines.append(f"    ┌{'─' * 46}")
    lines.append(f"    │ 📌 {code} {name}")
    lines.append(f"    └{'─' * 46}")

    if not today_row:
        lines.append(f"    ⚠️  不在评分池中，无法分析")
        return lines

    score = float(today_row['total_score'])
    lines.append(f"    📊 总分: {score:.2f}")

    # 因子拆解 — Markdown 表格（任何渲染器都能正确显示）
    lines.append(f"    📋 9因子拆解:")
    lines.append(f"")
    # 获取昨日数据用于因子变化对比
    yesterday_map = {r["code"]: r for r in yesterday_data} if yesterday_data else {}
    yesterday_row = yesterday_map.get(code) if yesterday_data else None
    
    lines.append(f"    | 因子 | 今日 | 变化 | 状态 |")
    lines.append(f"    |------|------|------|------|")
    for f in FACTOR_LIST:
        val = today_row.get(f, 'N/A')
        change_str = ""
        try:
            fv = float(val)
            # 获取昨日因子值
            if yesterday_row:
                yes_val = yesterday_row.get(f, 'N/A')
                try:
                    yfv = float(yes_val)
                    diff = fv - yfv
                    if diff > 0:
                        change_str = f"⬆️+{diff:.2f}"
                    elif diff < 0:
                        change_str = f"⬇️{diff:.2f}"
                    else:
                        change_str = "➡️0.00"
                except:
                    change_str = ""
            if fv >= 7:
                tag = "🟢强"
            elif fv >= 4:
                tag = "🟡中"
            else:
                tag = "🔴弱"
            val_str = f"{fv:.2f}"
        except:
            tag = "⚪--"
            val_str = "N/A"
            change_str = ""
        lines.append(f"    | {f} | {val_str} | {change_str} | {tag} |")

    # 历史走势（最近10次）
    trend = get_score_trend(code, history)[:10]
    if len(trend) >= 2:
        lines.append(f"    📈 最近{len(trend)}次评分走势:")
        for t in trend:
            lines.append(f"      {t['date']}: {t['score']:.2f}")
        first = trend[-1]["score"]
        last = trend[0]["score"]
        change = last - first
        arrow = "📈 上升" if change > 0 else "📉 下降" if change < 0 else "➡️ 持平"
        lines.append(f"      变化: {arrow} ({change:+.2f})")
    else:
        lines.append(f"    📈 历史数据不足，仅 {len(trend)} 天")

    # 排名
    rank, total = get_latest_rank(code, history)
    if rank:
        lines.append(f"    🏅 全市场排名: 第 {rank} / {total} 名")

    # 综合诊断
    lines.append(f"    💡 综合诊断:")
    weak_factors = []
    strong_factors = []
    for f in FACTOR_LIST:
        try:
            fv = float(today_row.get(f, 0))
            if fv <= 2:
                weak_factors.append(f)
            elif fv >= 7:
                strong_factors.append(f)
        except:
            pass

    if strong_factors:
        lines.append(f"      ✅ 优势因子: {', '.join(strong_factors)}")
    if weak_factors:
        lines.append(f"      ⚠️  弱势因子: {', '.join(weak_factors)}")
    if not strong_factors and not weak_factors:
        lines.append(f"      ➡️  各因子均衡，无明显强弱点")

    # 趋势判断
    if len(trend) >= 2:
        if change > 5:
            lines.append(f"      🚀 评分持续上升，值得重点关注")
        elif change < -5:
            lines.append(f"      📉 评分持续下降，需警惕风险")
        else:
            lines.append(f"      ➡️  评分波动不大，维持观察")

    return lines

# ==================== 报告生成 ====================
def generate_report(today_date, history):
    today_data = history.get(today_date)
    if not today_data:
        return f"❌ 今日({today_date})评分数据不存在"

    yesterday_date = get_last_trading_day(today_date)
    if yesterday_date:
        yesterday_data = history.get(yesterday_date, [])
    else:
        yesterday_data = []
    changes = compare_yesterday(today_data, yesterday_data) if yesterday_data else None

    self_stocks = read_self_stock()
    focus_stocks = read_focus_stock()

    buckets, scores = get_score_distribution(today_data)
    avg_score = sum(scores) / len(scores)
    max_score = max(scores)
    min_score = min(scores)
    median_score = sorted(scores)[len(scores)//2]

    lines = []
    lines.append("=" * 60)
    lines.append(f"📊 每日多因子评分分析报告")
    lines.append(f"📅 日期: {today_date} (截至 {datetime.now().strftime('%Y-%m-%d %H:%M')})")
    lines.append(f"📈 覆盖股票: {len(today_data)} 只")
    lines.append("=" * 60)

    # 一、大盘概览
    lines.append("\n" + "─" * 40)
    lines.append("📈 一、大盘概览")
    lines.append("─" * 40)
    lines.append(f"  最高分: {max_score:.2f}")
    lines.append(f"  最低分: {min_score:.2f}")
    lines.append(f"  平均分: {avg_score:.2f}")
    lines.append(f"  中位数: {median_score:.2f}")
    lines.append(f"\n  📊 评分分布:")
    for name in ['90+', '80-90', '70-80', '60-70', '50-60', '40-50', '30-40', '20-30', '10-20', '10以下']:
        count = buckets[name]
        bar = '█' * max(1, int(count / 10))
        lines.append(f"    {name:>8s}: {count:>4d} ({count/len(scores)*100:5.1f}%) {bar}")

    # 二、TOP榜单
    lines.append("\n" + "─" * 40)
    lines.append("🏆 二、TOP 榜单")
    lines.append("─" * 40)
    lines.append(f"\n  🥇 总分 TOP 10:")
    top10 = get_top_n(today_data, 10)
    for i, r in enumerate(top10, 1):
        medal = ['🥇','🥈','🥉'][i-1] if i <= 3 else f"  {i}."
        lines.append(f"    {medal} {r['code']} {r['name']:<10s} 总分: {float(r['total_score']):>6.2f}")

    lines.append(f"\n  🌟 各因子单项冠军:")
    for factor, name in FACTOR_NAMES.items():
        champions = get_factor_champions(today_data, factor)
        if champions:
            champ = champions[0]
            lines.append(f"    {name}: {champ['code']} {champ['name']} ({champ[factor]})")

    # 三、自选股专区
    lines.append("\n" + "─" * 40)
    lines.append("⭐ 三、自选股专区")
    lines.append("─" * 40)
    self_map = {r['code']: r for r in today_data if r['code'] in self_stocks}
    if not self_map:
        lines.append(f"  ⚠️  自选股文件未找到或为空")
    else:
        self_scores = [float(r['total_score']) for r in self_map.values()]
        self_avg = sum(self_scores) / len(self_scores)
        lines.append(f"  自选股数量: {len(self_map)} 只")
        lines.append(f"  自选股平均分: {self_avg:.2f} (全市场: {avg_score:.2f})")
        diff = self_avg - avg_score
        if diff > 0:
            lines.append(f"  📈 自选股优于市场 {diff:.2f} 分")
        else:
            lines.append(f"  📉 自选股低于市场 {abs(diff):.2f} 分")
        lines.append(f"\n  📋 自选股 TOP 10:")
        self_sorted = sorted(self_map.values(), key=lambda x: float(x['total_score']), reverse=True)
        for i, r in enumerate(self_sorted[:10], 1):
            rank_in_pool = next((j+1 for j, t in enumerate(top10) if t['code'] == r['code']), None)
            tag = f" [全市场TOP{rank_in_pool}]" if rank_in_pool else ""
            lines.append(f"    {i:>2d}. {r['code']} {r['name']:<10s} 总分: {float(r['total_score']):>6.2f}{tag}")

    # ★ 四、特别关注股票分析（核心板块）
    lines.append("\n" + "═" * 60)
    lines.append("🔥 四、特别关注股票分析 ⭐⭐⭐")
    lines.append("═" * 60)

    focus_today = {r['code']: r for r in today_data if r['code'] in focus_stocks}
    focus_avg = []
    focus_ranks = []

    for code, name in focus_stocks.items():
        today_row = focus_today.get(code)
        analysis = analyze_focus_stock(code, name, today_row, history, yesterday_data)
        lines.extend(analysis)
        lines.append("")  # 空行分隔

        if today_row:
            focus_avg.append(float(today_row['total_score']))
            rank, _ = get_latest_rank(code, history)
            if rank:
                focus_ranks.append(rank)

    # 特别关注股票汇总
    lines.append("    " + "─" * 46)
    lines.append("    📊 特别关注股票汇总")
    lines.append("    " + "─" * 46)
    if focus_avg:
        focus_avg_score = sum(focus_avg) / len(focus_avg)
        lines.append(f"    关注股平均分: {focus_avg_score:.2f} (全市场: {avg_score:.2f})")
        diff = focus_avg_score - avg_score
        if diff > 0:
            lines.append(f"    📈 优于市场 {diff:.2f} 分")
        else:
            lines.append(f"    📉 低于市场 {abs(diff):.2f} 分")

        if focus_ranks:
            lines.append(f"    平均排名: 第 {sum(focus_ranks)//len(focus_ranks)} / {len(today_data)} 名")

        # 最佳/最差
        best = max(focus_today.items(), key=lambda x: float(x[1]['total_score']))
        worst = min(focus_today.items(), key=lambda x: float(x[1]['total_score']))
        lines.append(f"    🏆 最佳: {best[0]} {focus_stocks[best[0]]} ({float(best[1]['total_score']):.2f}分)")
        lines.append(f"    ⚠️  最差: {worst[0]} {focus_stocks[worst[0]]} ({float(worst[1]['total_score']):.2f}分)")

        # 不在池中的
        missing = [c for c in focus_stocks if c not in focus_today]
        if missing:
            lines.append(f"    ❌ 不在评分池: {', '.join(missing)}")

    # 五、今日 vs 昨日对比
    lines.append("\n" + "─" * 40)
    lines.append("📊 五、今日 vs 昨日对比")
    lines.append("─" * 40)
    if changes:
        top_gainers = sorted(changes, key=lambda x: x['change'], reverse=True)[:5]
        lines.append(f"\n  📈 评分涨幅最大 TOP 5:")
        for c in top_gainers:
            lines.append(f"    📈 {c['code']} {c['name']}: {c['yesterday']:.2f} → {c['today']:.2f} ({c['change']:+.2f})")
        top_losers = sorted(changes, key=lambda x: x['change'])[:5]
        lines.append(f"\n  📉 评分跌幅最大 TOP 5:")
        for c in top_losers:
            lines.append(f"    📉 {c['code']} {c['name']}: {c['yesterday']:.2f} → {c['today']:.2f} ({c['change']:+.2f})")
    else:
        lines.append(f"  ⚠️  昨日({yesterday_date})数据不存在，无法对比")

    # 六、5日评分走势
    lines.append("\n" + "─" * 40)
    lines.append("📈 六、5日评分走势分析")
    lines.append("─" * 40)
    recent_dates = sorted(history.keys(), reverse=True)[:5]
    if len(recent_dates) >= 2:
        lines.append(f"  可用数据日期: {', '.join(reversed(recent_dates))}")
        trend_map = {}
        for code in set(r['code'] for r in today_data):
            scores_list = []
            for d in sorted(recent_dates):
                for row in history.get(d, []):
                    if row['code'] == code:
                        scores_list.append((d, float(row['total_score'])))
                        break
            if len(scores_list) >= 2:
                change = scores_list[0][1] - scores_list[-1][1]
                trend_map[code] = {'scores': scores_list, 'change': change}

        rising = [(k, v) for k, v in trend_map.items() if v['change'] > 3]
        rising = sorted(rising, key=lambda x: x[1]['change'], reverse=True)[:5]
        if rising:
            lines.append(f"\n  📈 持续上升 (5日涨幅>3分) TOP 5:")
            for code, v in rising:
                name = next((r['name'] for r in today_data if r['code'] == code), '')
                lines.append(f"    📈 {code} {name}: 5日变化 +{v['change']:.2f}")

        falling = [(k, v) for k, v in trend_map.items() if v['change'] < -3]
        falling = sorted(falling, key=lambda x: x[1]['change'])[:5]
        if falling:
            lines.append(f"\n  📉 持续下降 (5日跌幅>3分) TOP 5:")
            for code, v in falling:
                name = next((r['name'] for r in today_data if r['code'] == code), '')
                lines.append(f"    📉 {code} {name}: 5日变化 {v['change']:.2f}")
    else:
        lines.append(f"  ⚠️  历史数据不足，仅 {len(recent_dates)} 天，需要积累更多数据")

    # 七、风险提示
    lines.append("\n" + "─" * 40)
    lines.append("⚠️  七、风险提示")
    lines.append("─" * 40)
    weak_stocks = []
    for r in today_data:
        low_count = sum(1 for f in FACTOR_LIST if float(r.get(f, 0)) <= 2)
        if low_count >= 3:
            weak_stocks.append(r)
    weak_stocks = sorted(weak_stocks, key=lambda x: float(x['total_score']))[:5]
    if weak_stocks:
        lines.append(f"\n  ⚠️  多因子全面走弱 (9因子中≥3个≤2分):")
        for r in weak_stocks:
            lines.append(f"    ⚠️  {r['code']} {r['name']} 总分: {float(r['total_score']):.2f}")
    else:
        lines.append(f"\n  ✅ 暂无多因子全面走弱的股票")

    # 八、投资建议
    lines.append("\n" + "─" * 40)
    lines.append("💡 八、投资建议")
    lines.append("─" * 40)
    if changes:
        gainers = sorted(changes, key=lambda x: x['change'], reverse=True)[:5]
        losers = sorted(changes, key=lambda x: x['change'])[:5]
        
        # 获取涨跌幅
        gainer_codes = [c['code'] for c in gainers]
        loser_codes = [c['code'] for c in losers]
        change_pcts = get_stock_changepct(gainer_codes + loser_codes)
        
        lines.append(f"\n  🎯 值得关注的加分股:")
        for c in gainers:
            pct = change_pcts.get(c['code'], None)
            pct_str = f" (今日{pct:+.2f}%)" if pct is not None else ""
            lines.append(f"    🟢 {c['code']} {c['name']}: 评分 +{c['change']:.2f}{pct_str}")
        
        lines.append(f"\n  🔴 需要警惕的减分股:")
        for c in losers:
            pct = change_pcts.get(c['code'], None)
            pct_str = f" (今日{pct:+.2f}%)" if pct is not None else ""
            lines.append(f"    🔴 {c['code']} {c['name']}: 评分 {c['change']:.2f}{pct_str}")

    lines.append("\n" + "=" * 60)
    lines.append("🔔 报告生成完毕 | 1号自动评分系统")
    lines.append("=" * 60)

    return "\n".join(lines)



# ==================== HTML 报告生成 ====================
def generate_html_report(today_date, history):
    """生成完整的 HTML 格式报告，包含 MD 全部 8 个板块"""
    from datetime import datetime, timedelta
    import csv
    
    today_data = history.get(today_date)
    if not today_data:
        return "<html><body><h1>数据不存在</h1></body></html>"
    
    # 计算统计信息
    scores = [float(r['total_score']) for r in today_data]
    avg_score = sum(scores) / len(scores)
    max_score = max(scores)
    min_score = min(scores)
    median_score = sorted(scores)[len(scores)//2]
    
    # 评分分布
    buckets = {'90+':0, '80-90':0, '70-80':0, '60-70':0, '50-60':0, '40-50':0, '30-40':0, '20-30':0, '10-20':0, '10以下':0}
    for s in scores:
        if s >= 90: buckets['90+'] += 1
        elif s >= 80: buckets['80-90'] += 1
        elif s >= 70: buckets['70-80'] += 1
        elif s >= 60: buckets['60-70'] += 1
        elif s >= 50: buckets['50-60'] += 1
        elif s >= 40: buckets['40-50'] += 1
        elif s >= 30: buckets['30-40'] += 1
        elif s >= 20: buckets['20-30'] += 1
        elif s >= 10: buckets['10-20'] += 1
        else: buckets['10以下'] += 1
    
    # TOP 10
    top10 = sorted(today_data, key=lambda x: float(x['total_score']), reverse=True)[:10]
    
    # 各因子单项冠军
    factor_names = ['关注度', '单日涨跌幅', '股息率', '今年相对大盘强弱', '财报', '5日涨跌幅', '行业相对强弱', '新闻', '资金流向']
    champions = {}
    for f in factor_names:
        best = max(today_data, key=lambda x: float(x.get(f, 0)))
        champions[f] = best
    
    # 自选股专区
    self_stocks = {}
    self_file = '/home/admin/AUTO-STOCK/stock_self_selected.csv'
    if os.path.exists(self_file):
        with open(self_file, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                self_stocks[row['code']] = row['name']
    
    self_today = {r['code']: r for r in today_data if r['code'] in self_stocks}
    self_scores = [float(r['total_score']) for r in self_today.values()]
    self_avg = sum(self_scores)/len(self_scores) if self_scores else 0
    self_top10 = sorted(self_today.values(), key=lambda x: float(x['total_score']), reverse=True)[:10]
    
    # 特别关注股票
    focus_stocks = {}
    focus_file = '/home/admin/AUTO-STOCK/stock_focus.csv'
    if os.path.exists(focus_file):
        with open(focus_file, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                focus_stocks[row['code']] = row['name']
    
    focus_today = {r['code']: r for r in today_data if r['code'] in focus_stocks}
    
    # 对比上一交易日
    yesterday_date = get_last_trading_day(today_date)
    if yesterday_date:
        yesterday_data = history.get(yesterday_date, [])
    else:
        yesterday_data = []
    changes = []
    if yesterday_data:
        y_map = {r['code']: r for r in yesterday_data}
        for r in today_data:
            if r['code'] in y_map:
                change = float(r['total_score']) - float(y_map[r['code']]['total_score'])
                changes.append({'code': r['code'], 'name': r['name'], 'today': float(r['total_score']), 'yesterday': float(y_map[r['code']]['total_score']), 'change': change})
    
    # 5日走势
    recent_dates = sorted(history.keys(), reverse=True)[:5]
    trend_map = {}
    if len(recent_dates) >= 2:
        for code in set(r['code'] for r in today_data):
            scores_list = []
            for d in sorted(recent_dates):
                for row in history.get(d, []):
                    if row['code'] == code:
                        scores_list.append((d, float(row['total_score'])))
                        break
            if len(scores_list) >= 2:
                change = scores_list[0][1] - scores_list[-1][1]
                trend_map[code] = {'scores': scores_list, 'change': change}
    
    rising = sorted([(k,v) for k,v in trend_map.items() if v['change'] > 3], key=lambda x: x[1]['change'], reverse=True)[:5]
    falling = sorted([(k,v) for k,v in trend_map.items() if v['change'] < -3], key=lambda x: x[1]['change'])[:5]
    
    # 风险提示
    weak_stocks = []
    for r in today_data:
        low_count = sum(1 for f in factor_names if float(r.get(f, 0)) <= 2)
        if low_count >= 3:
            weak_stocks.append(r)
    weak_stocks = sorted(weak_stocks, key=lambda x: float(x['total_score']))[:5]
    
    # 构建 HTML
    h = []
    h.append('<!DOCTYPE html>')
    h.append('<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">')
    h.append(f'<title>每日多因子评分分析报告 - {today_date}</title>')
    h.append('<style>')
    h.append('*{margin:0;padding:0;box-sizing:border-box}')
    h.append('body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;padding:16px}')
    h.append('.container{max-width:960px;margin:0 auto;background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.1);overflow:hidden}')
    h.append('.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:28px 20px;text-align:center}')
    h.append('.header h1{font-size:22px;margin-bottom:8px}.header .sub{opacity:.9;font-size:13px}')
    h.append('.section{padding:22px 20px;border-bottom:1px solid #eee}')
    h.append('.section:last-child{border-bottom:none}')
    h.append('.stitle{font-size:17px;font-weight:600;color:#333;margin-bottom:14px;padding-bottom:8px;border-bottom:2px solid #667eea}')
    h.append('table{width:100%;border-collapse:collapse;margin:12px 0}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #eee}')
    h.append('th{background:#f8f9fa;font-weight:600;color:#555;font-size:13px}td{font-size:13px}')
    h.append('tr:hover{background:#f8f9fa}')
    h.append('.gs{color:#22c55e;font-weight:600}.gm{color:#eab308;font-weight:600}.gb{color:#ef4444;font-weight:600}')
    h.append('.sg{background:#dcfce7;color:#166534;padding:2px 8px;border-radius:10px;font-size:11px}')
    h.append('.sm{background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:10px;font-size:11px}')
    h.append('.sb{background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:10px;font-size:11px}')
    h.append('.sgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:12px 0}')
    h.append('.scard{background:#f8f9fa;padding:14px;border-radius:8px;text-align:center}')
    h.append('.scard .v{font-size:22px;font-weight:700;color:#667eea}.scard .l{font-size:11px;color:#666;margin-top:4px}')
    h.append('.bbar{display:flex;align-items:center;gap:8px;margin:6px 0;font-size:13px}')
    h.append('.bbar .bl{width:70px;color:#666}.bbar .bw{flex:1;height:18px;background:#e5e7eb;border-radius:3px;overflow:hidden}')
    h.append('.bbar .bf{height:100%;background:linear-gradient(90deg,#667eea,#764ba2);border-radius:3px}')
    h.append('.bbar .bv{width:80px;color:#666;text-align:right}')
    h.append('.fc{background:#f8f9fa;border-radius:8px;padding:16px;margin:12px 0}')
    h.append('.fh{display:flex;align-items:center;gap:8px;margin-bottom:10px}')
    h.append('.fcode{font-size:16px;font-weight:700;color:#667eea}.fname{font-size:14px;color:#666}')
    h.append('.fscore{font-size:26px;font-weight:700;color:#667eea;text-align:center;margin:8px 0}')
    h.append('.ftable{font-size:12px}.ftable th,.ftable td{padding:6px 8px}')
    h.append('.diag{margin-top:8px;font-size:12px;line-height:1.8}')
    h.append('.diag p{margin:2px 0}')
    h.append('.focus-summary{background:#f0f9ff;border-radius:8px;padding:14px;margin:14px 0;font-size:13px;line-height:1.8}')
    h.append('.search-box{margin:20px 0;text-align:center}')
    h.append('.search-box input{padding:10px 15px;width:300px;border:2px solid #667eea;border-radius:8px;font-size:14px}')
    h.append('.search-box input:focus{outline:none;border-color:#22c55e}')
    h.append('.search-results{margin:10px 0;text-align:center}')
    h.append('.search-results table{display:inline-block;text-align:left}')
    h.append('.search-results td{padding:8px 12px}')
    h.append('.search-hint{color:#999;font-size:12px;margin-top:8px}')
    h.append('.footer{text-align:center;padding:18px;color:#999;font-size:11px}')
    h.append('@media(max-width:600px){.header h1{font-size:17px}.sgrid{grid-template-columns:repeat(2,1fr)}table{font-size:11px}th,td{padding:6px 8px}}')
    h.append('</style></head><body><div class="container">')
    
    # Header
    h.append(f'<div class="header"><h1>📊 每日多因子评分分析报告</h1><div class="sub">📅 {today_date} | 📈 覆盖 {len(today_data)} 只股票<br>(沪深300 + 中证1000 + 自选股 {len(self_stocks)}只)</div></div>')

    # 搜索框
    h.append('<div class="search-box">')
    h.append('  <input type="text" id="stockSearch" placeholder="输入代码或名称搜索 (如: 000858 或 茅台)" onkeyup="searchStock()">')
    h.append('  <div id="searchResults" class="search-results"></div>')
    h.append('  <div id="searchHint" class="search-hint">支持代码或股票名称模糊搜索</div>')
    h.append('</div>')

    # 板块一：大盘概览
    h.append('<div class="section"><div class="stitle">📈 一、大盘概览</div>')
    h.append('<div class="sgrid">')
    h.append(f'<div class="scard"><div class="v">{max_score:.2f}</div><div class="l">最高分</div></div>')
    h.append(f'<div class="scard"><div class="v">{min_score:.2f}</div><div class="l">最低分</div></div>')
    h.append(f'<div class="scard"><div class="v">{avg_score:.2f}</div><div class="l">平均分</div></div>')
    h.append(f'<div class="scard"><div class="v">{median_score:.2f}</div><div class="l">中位数</div></div>')
    h.append('</div>')
    h.append('<div style="margin-top:16px"><div class="stitle" style="font-size:14px">📊 评分分布</div>')
    for name in ['90+','80-90','70-80','60-70','50-60','40-50','30-40','20-30','10-20','10以下']:
        cnt = buckets[name]
        pct = cnt/len(scores)*100
        w = max(1, int(pct*4))
        h.append(f'<div class="bbar"><span class="bl">{name:>7s}</span><div class="bw"><div class="bf" style="width:{w}%"></div></div><span class="bv">{cnt} ({pct:.1f}%)</span></div>')
    h.append('</div></div>')
    
    # 板块二：TOP 榜单
    h.append('<div class="section"><div class="stitle">🏆 二、TOP 榜单</div>')
    h.append('<table><thead><tr><th>排名</th><th>代码</th><th>名称</th><th>总分</th></tr></thead><tbody>')
    medals = ['🥇','🥈','🥉']
    for i, r in enumerate(top10):
        m = medals[i] if i<3 else f'{i+1}.'
        sc = float(r['total_score'])
        cls = 'gs' if sc>=60 else ('gm' if sc>=40 else 'gb')
        h.append(f'<tr><td>{m}</td><td>{r["code"]}</td><td>{r["name"]}</td><td class="{cls}">{sc:.2f}</td></tr>')
    h.append('</tbody></table>')
    
    # 因子单项冠军
    h.append('<div style="margin-top:16px"><div class="stitle" style="font-size:14px">🌟 各因子单项冠军</div><table><thead><tr><th>因子</th><th>代码</th><th>名称</th><th>得分</th></tr></thead><tbody>')
    for f in factor_names:
        c = champions[f]
        h.append(f'<tr><td>{f}</td><td>{c["code"]}</td><td>{c["name"]}</td><td class="gs">{float(c.get(f,0)):.2f}</td></tr>')
    h.append('</tbody></table></div></div>')
    
    # 板块三：自选股专区
    h.append('<div class="section"><div class="stitle">⭐ 三、自选股专区</div>')
    h.append(f'<p style="font-size:13px;color:#666;margin-bottom:10px">自选股数量: {len(self_stocks)} 只 | 平均分: {self_avg:.2f} (全市场: {avg_score:.2f})</p>')
    if self_top10:
        h.append('<table><thead><tr><th>排名</th><th>代码</th><th>名称</th><th>总分</th></tr></thead><tbody>')
        for i, r in enumerate(self_top10):
            sc = float(r['total_score'])
            rank = next((j+1 for j,x in enumerate(top10) if x['code']==r['code']), 0)
            tag = f' [全市场TOP{rank}]' if rank else ''
            h.append(f'<tr><td>{i+1}.</td><td>{r["code"]}</td><td>{r["name"]}</td><td class="gs">{sc:.2f}</td><td style="font-size:11px;color:#999">{tag}</td></tr>')
        h.append('</tbody></table>')
    h.append('</div>')
    
    # 板块四：特别关注股票
    h.append('<div class="section"><div class="stitle">🔥 四、特别关注股票分析 ⭐⭐⭐</div>')
    focus_avg_scores = [float(focus_today[c]['total_score']) for c in focus_today if c in focus_stocks]
    focus_avg_score = sum(focus_avg_scores)/len(focus_avg_scores) if focus_avg_scores else 0
    focus_ranks = []

    # 获取关注股票的价格信息
    focus_codes = list(focus_stocks.keys())
    price_info = get_stock_price_info(focus_codes)

    for code, name in focus_stocks.items():
        row = focus_today.get(code)
        h.append('<div class="fc">')
        h.append(f'<div class="fh"><span class="fcode">{code}</span><span class="fname">{name}</span></div>')

        if row:
            sc = float(row['total_score'])
            h.append(f'<div class="fscore">{sc:.2f}</div>')

            # 显示收盘价和涨跌幅
            pi = price_info.get(code)
            if pi:
                close_str = f"{pi['close']:.2f}"
                pct = pi.get('change_pct')
                if pct is not None:
                    if pct > 0:
                        pct_str = f'<span style="color:#22c55e;font-weight:600">+{pct:.2f}%</span>'
                    elif pct < 0:
                        pct_str = f'<span style="color:#ef4444;font-weight:600">{pct:.2f}%</span>'
                    else:
                        pct_str = f'<span style="color:#999">0.00%</span>'
                else:
                    pct_str = '<span style="color:#999">--</span>'
                h.append(f'<div style="text-align:center;font-size:13px;color:#666;margin:4px 0">收盘: {close_str} | 涨跌幅: {pct_str}</div>')

            # 获取昨日数据
            yesterday_map = {r["code"]: r for r in yesterday_data} if yesterday_data else {}
            yesterday_row = yesterday_map.get(code)
            
            h.append('<table class="ftable"><thead><tr><th>因子</th><th>今日</th><th>变化</th><th>状态</th></tr></thead><tbody>')
            for f in factor_names:
                val = row.get(f, 'N/A')
                change_str = ""
                try:
                    fv = float(val)
                    # 计算变化
                    if yesterday_row:
                        yes_val = yesterday_row.get(f, 'N/A')
                        try:
                            yfv = float(yes_val)
                            diff = fv - yfv
                            if diff > 0:
                                change_str = f'<span style="color:#22c55e">⬆️+{diff:.2f}</span>'
                            elif diff < 0:
                                change_str = f'<span style="color:#ef4444">⬇️{diff:.2f}</span>'
                            else:
                                change_str = '<span style="color:#999">➡️0.00</span>'
                        except:
                            pass
                    if fv >= 7: tag = '<span class="sg">🟢强</span>'
                    elif fv >= 4: tag = '<span class="sm">🟡中</span>'
                    else: tag = '<span class="sb">🔴弱</span>'
                    vs = f'{fv:.2f}'
                except:
                    tag = '<span class="sb">⚪--</span>'
                    vs = 'N/A'
                h.append(f'<tr><td>{f}</td><td>{vs}</td><td>{change_str}</td><td>{tag}</td></tr>')
            h.append('</tbody></table>')
            
            # 历史走势（最近10次）
            trend = get_score_trend(code, history)[:10]
            if trend and len(trend) >= 2:
                h.append(f'<div style="margin-top:8px;font-size:12px"><strong>📈 最近{len(trend)}次评分走势:</strong><br>')
                for t in trend:
                    h.append(f'  {t["date"]}: {t["score"]:.2f}<br>')
                change = trend[0]["score"] - trend[-1]["score"]
                h.append(f'  变化: {"📈 上升" if change > 0 else ("📉 下降" if change < 0 else "➡️ 持平")} ({change:+.2f})</div>')
            elif trend:
                h.append('<div style="font-size:12px;margin-top:8px">📈 历史数据不足，仅 1 天</div>')
            
            # 排名
            rank = get_latest_rank(code, history)
            if rank:
                h.append(f'<div style="font-size:12px;margin-top:4px"><strong>🏅 全市场排名:</strong> 第 {rank[0]} / {rank[1]} 名</div>')
            
            # 综合诊断
            strong_f = [f for f in factor_names if float(row.get(f,0))>=7]
            weak_f = [f for f in factor_names if float(row.get(f,0))<=2]
            h.append('<div class="diag">')
            if strong_f:
                h.append(f'<p>✅ 优势因子: {", ".join(strong_f)}</p>')
            if weak_f:
                h.append(f'<p>⚠️ 弱势因子: {", ".join(weak_f)}</p>')
            if trend and len(trend)>=2:
                diff = abs(trend[-1]["score"]-trend[0]["score"])
                if diff > 3: h.append('<p>🚀 评分变化明显，值得重点关注</p>')
                else: h.append('<p>➡️ 评分波动不大，维持观察</p>')
            else:
                h.append('<p>➡️ 数据不足，继续观察</p>')
            h.append('</div>')
        else:
            h.append('<p style="color:#ef4444;text-align:center;padding:10px">⚠️ 不在评分池中</p>')
        h.append('</div>')
    
    # 关注股汇总
    if focus_avg_scores:
        best = max(focus_today.items(), key=lambda x: float(x[1]['total_score']))
        worst = min(focus_today.items(), key=lambda x: float(x[1]['total_score']))
        avg_rank = sum(focus_ranks)//len(focus_ranks) if focus_ranks else 0
        # 修复汇总部分中的 best/worst 访问
        h.append(f'<div class="focus-summary"><p><strong>📊 特别关注股票汇总</strong></p>')
        h.append(f'<p>关注股平均分: {focus_avg_score:.2f} (全市场: {avg_score:.2f})</p>')
        h.append(f'<p>📉 低于市场 {abs(focus_avg_score-avg_score):.2f} 分 | 🏆 最佳: {best[0]} {focus_stocks[best[0]]} ({float(best[1]["total_score"]):.2f}分) | ⚠️ 最差: {worst[0]} {focus_stocks[worst[0]]} ({float(worst[1]["total_score"]):.2f}分)</p></div>')
    h.append('</div>')
    
    # 板块五：今日 vs 昨日对比
    h.append('<div class="section"><div class="stitle">📊 五、今日 vs 昨日对比</div>')
    if changes:
        gainers = sorted(changes, key=lambda x: x['change'], reverse=True)[:5]
        losers = sorted(changes, key=lambda x: x['change'])[:5]
        h.append('<table><thead><tr><th></th><th>代码</th><th>名称</th><th>昨日</th><th>今日</th><th>变化</th></tr></thead><tbody>')
        h.append('<tr><td colspan="6" style="background:#f0fdf4;font-weight:600">📈 评分涨幅最大 TOP 5</td></tr>')
        for c in gainers:
            h.append(f'<tr><td>📈</td><td>{c["code"]}</td><td>{c["name"]}</td><td>{c["yesterday"]:.2f}</td><td>{c["today"]:.2f}</td><td class="gs">{c["change"]:+.2f}</td></tr>')
        h.append('<tr><td colspan="6" style="background:#fef2f2;font-weight:600">📉 评分跌幅最大 TOP 5</td></tr>')
        for c in losers:
            h.append(f'<tr><td>📉</td><td>{c["code"]}</td><td>{c["name"]}</td><td>{c["yesterday"]:.2f}</td><td>{c["today"]:.2f}</td><td class="gb">{c["change"]:+.2f}</td></tr>')
        h.append('</tbody></table>')
    else:
        h.append(f'<p style="color:#999">⚠️ 昨日({yesterday_date})数据不存在，无法对比</p>')
    h.append('</div>')
    
    # 板块六：5日评分走势
    h.append('<div class="section"><div class="stitle">📈 六、5日评分走势分析</div>')
    h.append(f'<p style="font-size:13px;color:#666;margin-bottom:10px">可用数据日期: {", ".join(reversed(recent_dates))}</p>')
    if rising:
        h.append('<table><thead><tr><th></th><th>代码</th><th>名称</th><th>5日变化</th></tr></thead><tbody>')
        h.append('<tr><td colspan="4" style="background:#f0fdf4;font-weight:600">📈 持续上升 (涨幅>3分) TOP 5</td></tr>')
        for code, v in rising:
            name = next((r['name'] for r in today_data if r['code']==code), '')
            h.append(f'<tr><td>📈</td><td>{code}</td><td>{name}</td><td class="gs">+{v["change"]:.2f}</td></tr>')
        h.append('</tbody></table>')
    if falling:
        h.append('<table><thead><tr><th></th><th>代码</th><th>名称</th><th>5日变化</th></tr></thead><tbody>')
        h.append('<tr><td colspan="4" style="background:#fef2f2;font-weight:600">📉 持续下降 (跌幅>3分) TOP 5</td></tr>')
        for code, v in falling:
            name = next((r['name'] for r in today_data if r['code']==code), '')
            h.append(f'<tr><td>📉</td><td>{code}</td><td>{name}</td><td class="gb">{v["change"]:.2f}</td></tr>')
        h.append('</tbody></table>')
    if not rising and not falling:
        h.append('<p style="color:#999">⚠️ 历史数据不足，需要积累更多数据</p>')
    h.append('</div>')
    
    # 板块七：风险提示
    h.append('<div class="section"><div class="stitle">⚠️ 七、风险提示</div>')
    if weak_stocks:
        h.append('<table><thead><tr><th></th><th>代码</th><th>名称</th><th>总分</th></tr></thead><tbody>')
        for r in weak_stocks:
            h.append(f'<tr><td>⚠️</td><td>{r["code"]}</td><td>{r["name"]}</td><td class="gb">{float(r["total_score"]):.2f}</td></tr>')
        h.append('</tbody></table>')
        h.append('<p style="font-size:12px;color:#999;margin-top:8px">多因子全面走弱 (9因子中≥3个≤2分)</p>')
    else:
        h.append('<p style="color:#22c55e">✅ 暂无多因子全面走弱的股票</p>')
    h.append('</div>')
    
    # 板块八：投资建议
    h.append('<div class="section"><div class="stitle">💡 八、投资建议</div>')
    if changes:
        gainers = sorted(changes, key=lambda x: x['change'], reverse=True)[:5]
        losers = sorted(changes, key=lambda x: x['change'])[:5]
        
        # 获取涨跌幅
        gainer_codes = [c['code'] for c in gainers]
        loser_codes = [c['code'] for c in losers]
        change_pcts = get_stock_changepct(gainer_codes + loser_codes)
        
        h.append('<table><thead><tr><th></th><th>代码</th><th>名称</th><th>评分变化</th><th>今日涨跌幅</th></tr></thead><tbody>')
        h.append('<tr><td colspan="5" style="background:#f0fdf4;font-weight:600">🎯 值得关注的加分股</td></tr>')
        for c in gainers:
            pct = change_pcts.get(c['code'], None)
            if pct is None:
                pct_str = "-"
            elif pct > 0:
                pct_str = f'<span style="color:#22c55e">{pct:+.2f}%</span>'
            elif pct < 0:
                pct_str = f'<span style="color:#ef4444">{pct:+.2f}%</span>'
            else:
                pct_str = f'<span style="color:#999">{pct:+.2f}%</span>'
            h.append(f'<tr><td>🟢</td><td>{c["code"]}</td><td>{c["name"]}</td><td class="gs">+{c["change"]:.2f}</td><td>{pct_str}</td></tr>')
        h.append('<tr><td colspan="5" style="background:#fef2f2;font-weight:600">🔴 需要警惕的减分股</td></tr>')
        for c in losers:
            pct = change_pcts.get(c['code'], None)
            if pct is None:
                pct_str = "-"
            elif pct > 0:
                pct_str = f'<span style="color:#22c55e">{pct:+.2f}%</span>'
            elif pct < 0:
                pct_str = f'<span style="color:#ef4444">{pct:+.2f}%</span>'
            else:
                pct_str = f'<span style="color:#999">{pct:+.2f}%</span>'
            h.append(f'<tr><td>🔴</td><td>{c["code"]}</td><td>{c["name"]}</td><td class="gb">{c["change"]:+.2f}</td><td>{pct_str}</td></tr>')
        h.append('</tbody></table>')
    h.append('</div>')

    # 搜索功能 JS
    stock_data_js = str(today_data).replace("'score'", "'total_score'")
    h.append('<script>const stockData = ' + stock_data_js + ';')
    h.append("""
  function searchStock() {
    const input = document.getElementById('stockSearch').value.trim().toLowerCase();
    const resultsDiv = document.getElementById('searchResults');
    const hintDiv = document.getElementById('searchHint');
    if (input.length < 2) { resultsDiv.innerHTML = ''; hintDiv.style.display = 'block'; return; }
    const matches = stockData.filter(s => s.code.includes(input) || s.name.toLowerCase().includes(input)).slice(0, 10);
    if (matches.length === 0) { resultsDiv.innerHTML = '<table><tr><td style="color:#ef4444;">未找到匹配的股票</td></tr></table>'; hintDiv.style.display = 'none'; }
    else {
      let html = '<table><thead><tr><th>代码</th><th>名称</th><th>评分</th></tr></thead><tbody>';
      matches.forEach(s => {
        const score = Number(s.total_score);
        const sc = score >= 60 ? 'gs' : (score >= 40 ? 'gm' : 'gb');
        const onclick = "viewStock('" + s.code + "')";
        html += '<tr><td style="cursor:pointer;" onclick="' + onclick + '">' + s.code + '</td><td style="cursor:pointer;" onclick="' + onclick + '">' + s.name + '</td><td class="' + sc + '" style="cursor:pointer;" onclick="' + onclick + '">' + score.toFixed(2) + '</td></tr>';
      });
      html += '</tbody></table>';
      resultsDiv.innerHTML = html;
      hintDiv.style.display = 'none';
    }
  }
  function viewStock(code) {
    // 先查询缓存状态
    fetch('/api/generate_report?code=' + code)
      .then(r => r.json())
      .then(data => {
        if (data.status === 'exists') {
          // 缓存新鲜，直接跳转
          window.location.href = '/reports/individual/stock_analysis_' + code + '.html';
        } else {
          // 缓存过期或不存在，显示生成进度
          showGenerating(code);
        }
      })
      .catch(() => showGenerating(code));
  }
  function showGenerating(code) {
    const resultsDiv = document.getElementById('searchResults');
    let progress = 0;
    const bar = '<div style="padding:20px;text-align:center;"><div style="margin-bottom:10px;">🔄 正在生成 ' + code + ' 详细报告</div><div style="width:200px;height:12px;background:#e5e7eb;border-radius:6px;margin:0 auto;overflow:hidden;"><div id="prog" style="height:100%;width:0%;background:#667eea;border-radius:6px;transition:width 1s;"></div></div><div id="pct" style="margin-top:8px;font-size:13px;color:#666;">0%</div></div>';
    resultsDiv.innerHTML = bar;
    fetch('/api/generate_report?code=' + code);
    const prog = () => {
      progress += 5;
      const p = Math.min(progress, 100);
      document.getElementById('prog').style.width = p + '%';
      document.getElementById('pct').textContent = p + '%';
      if (p < 100) setTimeout(prog, 1000);
    };
    setTimeout(prog, 100);
    const waitForReport = () => {
      fetch('/api/generate_report?code=' + code)
        .then(r => r.json())
        .then(data => {
          if (data.status === 'exists') {
            // 文件存在且缓存新鲜，生成完成了
            resultsDiv.innerHTML = '<div style="padding:20px;text-align:center;">✅ 报告生成完成，正在跳转...</div>';
            setTimeout(() => window.location.href = '/reports/individual/stock_analysis_' + code + '.html', 300);
          } else {
            // 还在生成中，继续轮询
            setTimeout(waitForReport, 2000);
          }
        })
        .catch(() => setTimeout(waitForReport, 2000));
    };
    setTimeout(waitForReport, 2000);
  }
  window.addEventListener('pageshow', function() {
    document.getElementById('searchResults').innerHTML = '';
    document.getElementById('searchHint').style.display = 'block';
  });
</script>""")

    # Footer
    h.append(f'<div class="footer">🔔 报告生成完毕 | 1号自动评分系统<br>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>')
    h.append('</div></body></html>')

    return "\n".join(h)

# ==================== 主程序 ====================
if __name__ == "__main__":
    today_date = "20260512"
    if len(sys.argv) > 1:
        today_date = sys.argv[1]

    print(f"📊 正在生成 {today_date} 的评分报告...\n")

    history = read_all_history()
    
    # 生成 Markdown 报告
    report = generate_report(today_date, history)
    print(report)
    
    # 生成 HTML 报告
    html_report = generate_html_report(today_date, history)

    report_dir = "/home/admin/AUTO-STOCK/reports"
    os.makedirs(report_dir, exist_ok=True)
    
    # 保存 Markdown
    md_file = os.path.join(report_dir, f"daily_report_{today_date}.md")
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n💾 Markdown 报告已保存: {md_file}")
    
    # 保存 HTML
    html_file = os.path.join(report_dir, f"daily_report_{today_date}.html")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_report)
    print(f"💾 HTML 报告已保存: {html_file}")
    print(f"🌐 用浏览器打开 HTML 文件查看完整表格效果")
