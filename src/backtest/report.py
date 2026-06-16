"""
回测报告生成器

输出形式：
1. 终端格式化文本
2. HTML 报告（ECharts 图表）
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult

RESULT_DIR = Path(__file__).resolve().parent.parent.parent / "result"


# ============================================================
# 终端报告
# ============================================================


def print_report(result: BacktestResult):
    """终端打印回测报告"""
    print()
    print("=" * 60)
    print("                    📈 回测报告")
    print("=" * 60)

    cfg = result.config
    print(f"  回测区间: {cfg.start_date or '自动'} ~ {cfg.end_date or '自动'}")
    print(f"  选股策略: Top-{cfg.top_n} 等权, 持仓 {cfg.hold_days} 天")
    print(f"  交易成本: {cfg.cost_rate*100:.2f}% (双边)")
    print()

    # 收益指标
    print("─" * 40)
    print("  📊 收益指标")
    print("─" * 40)
    print(f"  总收益率:     {result.total_return*100:>8.2f}%")
    print(f"  年化收益率:   {result.annual_return*100:>8.2f}%")
    print(f"  基准收益率:   {result.benchmark_return*100:>8.2f}%")
    print(f"  超额收益:     {result.excess_return*100:>8.2f}%")
    print()

    # 风险指标
    print("─" * 40)
    print("  📉 风险指标")
    print("─" * 40)
    print(f"  夏普比率:     {result.sharpe_ratio:>8.2f}")
    print(f"  最大回撤:     {result.max_drawdown*100:>8.2f}%")
    print()

    # 交易统计
    print("─" * 40)
    print("  🔄 交易统计")
    print("─" * 40)
    print(f"  调仓次数:     {result.turnover_count:>8d}")
    print(f"  总交易笔数:   {result.total_trades:>8d}")
    print(f"  胜率:         {result.win_rate*100:>8.2f}%")
    print(f"  平均盈利:     {result.avg_win*100:>8.2f}%")
    print(f"  平均亏损:     {result.avg_loss*100:>8.2f}%")
    print(f"  盈亏比:       {result.profit_loss_ratio:>8.2f}")
    print()

    # 因子分析
    if result.factor_ic:
        print("─" * 60)
        print("  🔍 因子分析 (IC)")
        print("─" * 60)
        print(f"  {'因子':<16} {'IC均值':>8} {'IC标准差':>8} {'IC_IR':>8} {'期数':>6}")
        print(f"  {'─'*16} {'─'*8} {'─'*8} {'─'*8} {'─'*6}")

        for factor_name, ic_list in result.factor_ic.items():
            if len(ic_list) < 1:
                continue
            ic_arr = np.array(ic_list)
            ic_mean = np.nanmean(ic_arr)
            ic_std = np.nanstd(ic_arr, ddof=1) if len(ic_arr) > 1 else 0
            ic_ir = ic_mean / ic_std if ic_std > 0 else 0
            print(
                f"  {factor_name:<16} {ic_mean:>8.4f} {ic_std:>8.4f} {ic_ir:>8.4f} {len(ic_list):>6d}"
            )
        print()

    # 分位收益
    if result.quintile_returns:
        print("─" * 60)
        print("  📊 分位收益 (5档, Q1=低分, Q5=高分)")
        print("─" * 60)
        header = f"  {'因子':<16}" + "".join(f"{'Q'+str(i+1):>10}" for i in range(5))
        print(header)
        print(f"  {'─'*16}" + "─" * 50)
        for factor_name, q_rets in result.quintile_returns.items():
            if len(q_rets) < 2:
                continue
            row = f"  {factor_name:<16}" + "".join(f"{r*100:>9.2f}%" for r in q_rets)
            print(row)
        print()

    # 净值曲线
    if result.daily_nav:
        print("─" * 40)
        print("  📈 净值曲线")
        print("─" * 40)
        for date, nav in result.daily_nav:
            bar_len = max(0, int((nav - 0.9) * 50))
            bar = "█" * bar_len
            print(f"  {date}  {nav:.4f}  {bar}")
        print()

    print("=" * 60)


# ============================================================
# HTML 报告
# ============================================================


def generate_html_report(
    result: BacktestResult,
    factor_analysis: Dict[str, Dict] = None,
    output_path: str = "",
) -> str:
    """生成 HTML 回测报告

    Args:
        result: 回测结果
        factor_analysis: run_factor_analysis() 的输出（可选）
        output_path: 输出路径，空=自动生成

    Returns:
        生成的 HTML 文件路径
    """
    if not output_path:
        date_str = datetime.now().strftime('%Y%m%d_%H%M')
        output_path = str(RESULT_DIR / f"backtest_report_{date_str}.html")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cfg = result.config

    # 净值数据
    nav_dates = [d for d, _ in result.daily_nav]
    nav_values = [round(v, 4) for _, v in result.daily_nav]
    bench_values = [round(v, 4) for _, v in result.benchmark_nav]

    # 因子IC数据
    ic_labels = []
    ic_means = []
    ic_irs = []
    if result.factor_ic:
        for name, ic_list in result.factor_ic.items():
            if len(ic_list) >= 2:
                ic_arr = np.array(ic_list)
                ic_labels.append(name)
                ic_means.append(round(float(np.nanmean(ic_arr)), 4))
                std = float(np.nanstd(ic_arr, ddof=1))
                ic_irs.append(round(float(np.nanmean(ic_arr)) / std, 4) if std > 0 else 0)

    # 分位收益数据
    quintile_labels = []
    quintile_data = []
    if result.quintile_returns:
        for name, q_rets in result.quintile_returns.items():
            if len(q_rets) >= 2:
                quintile_labels.append(name)
                quintile_data.append([round(r * 100, 2) for r in q_rets])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>回测报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
h1 {{ text-align: center; color: #1a1a1a; }}
h2 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 8px; }}
.metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
.metric {{ text-align: center; padding: 16px; background: #f8f9fa; border-radius: 8px; }}
.metric .label {{ color: #666; font-size: 14px; }}
.metric .value {{ font-size: 28px; font-weight: bold; margin-top: 4px; }}
.metric .value.positive {{ color: #e53935; }}
.metric .value.negative {{ color: #43a047; }}
.chart {{ width: 100%; height: 400px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px 12px; text-align: right; border-bottom: 1px solid #eee; }}
th {{ background: #f8f9fa; font-weight: 600; }}
td:first-child, th:first-child {{ text-align: left; }}
tr:hover {{ background: #f8f9fa; }}
</style>
</head>
<body>
<div class="container">
<h1>📈 回测报告</h1>
<p style="text-align:center;color:#666;">
  {cfg.start_date or '自动'} ~ {cfg.end_date or '自动'} |
  Top-{cfg.top_n} 等权 | 持仓 {cfg.hold_days} 天 | 成本 {cfg.cost_rate*100:.2f}%
</p>

<div class="card">
<h2>📊 收益指标</h2>
<div class="metrics">
  <div class="metric">
    <div class="label">总收益率</div>
    <div class="value {'positive' if result.total_return>0 else 'negative'}">{result.total_return*100:+.2f}%</div>
  </div>
  <div class="metric">
    <div class="label">年化收益率</div>
    <div class="value {'positive' if result.annual_return>0 else 'negative'}">{result.annual_return*100:+.2f}%</div>
  </div>
  <div class="metric">
    <div class="label">基准收益率</div>
    <div class="value {'positive' if result.benchmark_return>0 else 'negative'}">{result.benchmark_return*100:+.2f}%</div>
  </div>
  <div class="metric">
    <div class="label">超额收益</div>
    <div class="value {'positive' if result.excess_return>0 else 'negative'}">{result.excess_return*100:+.2f}%</div>
  </div>
  <div class="metric">
    <div class="label">夏普比率</div>
    <div class="value">{result.sharpe_ratio:.2f}</div>
  </div>
  <div class="metric">
    <div class="label">最大回撤</div>
    <div class="value negative">{result.max_drawdown*100:.2f}%</div>
  </div>
  <div class="metric">
    <div class="label">胜率</div>
    <div class="value">{result.win_rate*100:.1f}%</div>
  </div>
  <div class="metric">
    <div class="label">盈亏比</div>
    <div class="value">{result.profit_loss_ratio:.2f}</div>
  </div>
</div>
</div>

<div class="card">
<h2>📈 净值曲线</h2>
<div id="navChart" class="chart"></div>
</div>

<div class="card">
<h2>🔍 因子IC分析</h2>
<div id="icChart" class="chart"></div>
</div>

<div class="card">
<h2>📊 分位收益</h2>
<div id="quintileChart" class="chart"></div>
</div>

<div class="card">
<h2>📋 交易明细 (最近20笔)</h2>
<table>
<tr><th>买入日</th><th>卖出日</th><th>代码</th><th>名称</th><th>评分</th><th>排名</th><th>收益率</th></tr>
"""

    # 交易明细（最近20笔）
    for t in result.trades[-20:]:
        ret_class = 'positive' if t.net_return > 0 else 'negative'
        html += f"""<tr>
<td>{t.entry_date}</td><td>{t.exit_date}</td>
<td>{t.code}</td><td>{t.name}</td>
<td>{t.score:.1f}</td><td>#{t.rank}</td>
<td class="{ret_class}">{t.net_return*100:+.2f}%</td>
</tr>"""

    html += f"""
</table>
</div>

</div>

<script>
// 净值曲线
var navChart = echarts.init(document.getElementById('navChart'));
navChart.setOption({{
  tooltip: {{ trigger: 'axis' }},
  legend: {{ data: ['策略净值', '基准净值'] }},
  xAxis: {{ type: 'category', data: {json.dumps(nav_dates)} }},
  yAxis: {{ type: 'value', name: '净值', min: function(v){{ return (v.min - 0.02).toFixed(2); }} }},
  series: [
    {{ name: '策略净值', type: 'line', data: {json.dumps(nav_values)}, smooth: true, lineStyle: {{width: 2}} }},
    {{ name: '基准净值', type: 'line', data: {json.dumps(bench_values)}, smooth: true, lineStyle: {{width: 2, type: 'dashed'}} }}
  ]
}});

// 因子IC
var icChart = echarts.init(document.getElementById('icChart'));
icChart.setOption({{
  tooltip: {{ trigger: 'axis' }},
  xAxis: {{ type: 'category', data: {json.dumps(ic_labels)}, axisLabel: {{ rotate: 30 }} }},
  yAxis: {{ type: 'value', name: 'IC / IC_IR' }},
  series: [
    {{ name: 'IC均值', type: 'bar', data: {json.dumps(ic_means)}, itemStyle: {{ color: '#4CAF50' }} }},
    {{ name: 'IC_IR', type: 'bar', data: {json.dumps(ic_irs)}, itemStyle: {{ color: '#FF9800' }} }}
  ]
}});

// 分位收益
var qChart = echarts.init(document.getElementById('quintileChart'));
qChart.setOption({{
  tooltip: {{ trigger: 'axis' }},
  legend: {{ data: {json.dumps(quintile_labels)} }},
  xAxis: {{ type: 'category', data: ['Q1(低)', 'Q2', 'Q3', 'Q4', 'Q5(高)'] }},
  yAxis: {{ type: 'value', name: '平均收益率(%)' }},
  series: {json.dumps([
      {'name': name, 'type': 'bar', 'data': data}
      for name, data in zip(quintile_labels, quintile_data)
  ])}
}});

window.addEventListener('resize', function() {{
  navChart.resize();
  icChart.resize();
  qChart.resize();
}});
</script>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n✅ HTML报告已生成: {output_path}")
    return output_path


# ============================================================
# 导出交易明细
# ============================================================


def export_trades_csv(result: BacktestResult, output_path: str = "") -> str:
    """导出交易明细到 CSV"""
    if not output_path:
        date_str = datetime.now().strftime('%Y%m%d_%H%M')
        output_path = str(RESULT_DIR / f"backtest_trades_{date_str}.csv")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    rows = []
    for t in result.trades:
        rows.append({
            'entry_date': t.entry_date,
            'exit_date': t.exit_date,
            'code': t.code,
            'name': t.name,
            'score': t.score,
            'rank': t.rank,
            'return_pct': round(t.return_rate * 100, 2),
            'net_return_pct': round(t.net_return * 100, 2),
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"✅ 交易明细已导出: {output_path}")
    return output_path
