#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动信号分析脚本
分析股票启动前的评分规律，找启动信号阈值

用法：
  python scripts/launch_analysis.py --year 2022
  python scripts/launch_analysis.py --year 2022 --window 20 --threshold 15 --pre-days 7
"""

import argparse
import os
import sys
import glob
import numpy as np
import pandas as pd
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent


def load_stock_pool(pool_path):
    """加载股票池"""
    df = pd.read_csv(pool_path, dtype={"code": str})
    df["code"] = df["code"].str.zfill(6)
    return df


def load_price_data(code, year):
    """加载股票价格数据"""
    price_file = ROOT_DIR / "data" / "price" / f"{code}.csv"
    if not price_file.exists():
        return None

    df = pd.read_csv(price_file, dtype=str)
    # 中文列名：日期,收盘,成交额,开盘,最高,最低
    df = df.rename(columns={"日期": "date", "收盘": "close"})
    df["date"] = df["date"].str.strip()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"])

    # 筛选年份
    year_str = str(year)
    df = df[df["date"].str.startswith(year_str)].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df


def load_all_scores(year):
    """加载全年评分数据，返回 {date: {code: score}} 字典"""
    # 尝试多种目录名格式
    possible_dirs = [
        ROOT_DIR / "result" / "backtest" / str(year) / f"{year}_每日_5534_score",
        ROOT_DIR / "result" / "backtest" / str(year) / f"{year}_每日_200_score",
        ROOT_DIR / "result" / "backtest" / str(year) / f"{year}_1385_score",
    ]
    score_dir = None
    for d in possible_dirs:
        if d.exists():
            score_dir = d
            break
    if score_dir is None:
        print(f"错误：找不到 {year} 年评分数据目录")
        print(f"  尝试过：{[str(d.name) for d in possible_dirs]}")
        sys.exit(1)

    score_files = sorted(glob.glob(str(score_dir / "scores_*.csv")))
    if not score_files:
        print(f"错误：{score_dir} 下没有评分文件")
        sys.exit(1)

    print(f"加载评分数据：{len(score_files)} 天")
    scores = {}  # {date_str: {code: total_score}}
    for f in score_files:
        df = pd.read_csv(f, dtype={"code": str})
        df["code"] = df["code"].str.zfill(6)
        date_str = df["date"].iloc[0] if "date" in df.columns else Path(f).stem.replace("scores_", "")
        date_str = str(date_str).strip()
        scores[date_str] = dict(zip(df["code"], df["total_score"]))

    print(f"评分数据加载完成：{len(scores)} 天")
    return scores


def find_launch_point(price_df, window, threshold):
    """
    用滑动窗口找启动点
    返回：(launch_date, window_return, max_return_after) 或 None
    """
    if len(price_df) < window + 1:
        return None

    closes = price_df["close"].values
    dates = price_df["date"].values

    for i in range(window, len(closes)):
        # 过去window天的累计涨幅
        window_return = (closes[i] / closes[i - window] - 1) * 100
        if window_return >= threshold:
            # 计算启动后的最大涨幅（到年末）
            max_return_after = 0
            for j in range(i + 1, len(closes)):
                ret = (closes[j] / closes[i] - 1) * 100
                if ret > max_return_after:
                    max_return_after = ret
            return (dates[i], window_return, max_return_after)

    return None


def get_pre_launch_scores(launch_date, code, scores, pre_days):
    """获取启动前N天的平均评分"""
    # 按日期排序
    all_dates = sorted(scores.keys())
    # 找到launch_date的索引
    try:
        idx = all_dates.index(launch_date)
    except ValueError:
        # launch_date不在评分数据中，找最近的
        for i, d in enumerate(all_dates):
            if d >= launch_date:
                idx = i
                break
        else:
            return None, []

    # 取前pre_days天
    start_idx = max(0, idx - pre_days)
    pre_dates = all_dates[start_idx:idx]

    if not pre_dates:
        return None, []

    # 收集评分
    score_list = []
    for d in pre_dates:
        if code in scores.get(d, {}):
            score_list.append(scores[d][code])

    if not score_list:
        return None, []

    return np.mean(score_list), score_list


def get_random_scores(code, scores, pre_days, n_samples=10, exclude_range=None):
    """
    随机采样N组连续pre_days天的平均评分
    exclude_range: (start_idx, end_idx) 排除启动前后的日期，避免污染
    返回：(总体平均分, 所有采样组的平均分列表)
    """
    all_dates = sorted(scores.keys())
    total_days = len(all_dates)

    if total_days < pre_days + 10:
        return None, []

    # 找到该股票有评分的日期索引
    valid_indices = []
    for i, d in enumerate(all_dates):
        if code in scores.get(d, {}):
            valid_indices.append(i)

    if len(valid_indices) < pre_days + 10:
        return None, []

    # 排除启动前后的日期（避免污染）
    if exclude_range:
        ex_start, ex_end = exclude_range
        valid_indices = [i for i in valid_indices if i < ex_start - pre_days or i > ex_end + pre_days]

    if len(valid_indices) < pre_days + 5:
        return None, []

    # 随机采样
    np.random.seed(42)  # 可复现
    sample_avgs = []
    attempts = 0
    while len(sample_avgs) < n_samples and attempts < 100:
        # 随机选一个起始点
        start_idx = np.random.choice(valid_indices[:-pre_days])
        # 取连续pre_days天
        sample_dates = all_dates[start_idx:start_idx + pre_days]
        # 计算平均分
        day_scores = []
        for d in sample_dates:
            if code in scores.get(d, {}):
                day_scores.append(scores[d][code])
        if len(day_scores) >= pre_days * 0.7:  # 至少70%的天有数据
            sample_avgs.append(np.mean(day_scores))
        attempts += 1

    if not sample_avgs:
        return None, []

    return np.mean(sample_avgs), sample_avgs


def main():
    parser = argparse.ArgumentParser(description="启动信号分析")
    parser.add_argument("--year", type=int, required=True, help="分析年份")
    parser.add_argument("--pool", default="stock_self_selected.csv", help="股票池文件")
    parser.add_argument("--window", type=int, default=20, help="滑动窗口天数")
    parser.add_argument("--threshold", type=float, default=15, help="涨幅阈值%%")
    parser.add_argument("--pre-days", type=int, default=7, help="看启动前N天评分")
    parser.add_argument("--output", default=None, help="输出目录（默认result/backtest/YEAR/）")
    args = parser.parse_args()

    # 确定输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = ROOT_DIR / "result" / "backtest" / str(args.year)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"  {args.year}年 启动信号分析")
    print("=" * 60)
    print(f"窗口：{args.window}天内涨幅≥{args.threshold}%")
    print(f"看启动前：{args.pre_days}天评分")
    print()

    # 加载股票池
    pool_path = ROOT_DIR / args.pool
    if not pool_path.exists():
        pool_path = Path(args.pool)
    pool_df = load_stock_pool(pool_path)
    stock_codes = pool_df["code"].tolist()
    stock_names = dict(zip(pool_df["code"], pool_df["name"]))
    print(f"股票池：{len(stock_codes)} 只")

    # 加载全年评分
    scores = load_all_scores(args.year)

    # 分析每只股票
    results = []
    no_launch = []
    no_score = []

    for code in stock_codes:
        price_df = load_price_data(code, args.year)
        if price_df is None or len(price_df) < args.window + 1:
            no_launch.append(code)
            continue

        launch = find_launch_point(price_df, args.window, args.threshold)
        if launch is None:
            no_launch.append(code)
            continue

        launch_date, window_return, max_return_after = launch

        avg_score, score_list = get_pre_launch_scores(
            launch_date, code, scores, args.pre_days
        )

        if avg_score is None:
            no_score.append(code)
            continue

        # 获取前前7天（启动前14天到前7天）的平均分
        all_dates_sorted = sorted(scores.keys())
        try:
            launch_idx = all_dates_sorted.index(launch_date)
        except ValueError:
            for di, d in enumerate(all_dates_sorted):
                if d >= launch_date:
                    launch_idx = di
                    break
            else:
                launch_idx = len(all_dates_sorted)

        # 前前7天：第-14天到第-8天
        pre2_start = max(0, launch_idx - 14)
        pre2_end = max(0, launch_idx - 7)
        pre2_dates = all_dates_sorted[pre2_start:pre2_end]

        pre2_score_list = []
        for d in pre2_dates:
            if code in scores.get(d, {}):
                pre2_score_list.append(scores[d][code])

        pre2_avg = np.mean(pre2_score_list) if pre2_score_list else None

        # 加速度 = 前7天均分 - 前前7天均分
        acceleration = None
        if pre2_avg is not None and avg_score is not None:
            acceleration = round(avg_score - pre2_avg, 2)

        results.append({
            "股票代码": code,
            "股票名称": stock_names.get(code, ""),
            "启动日期": launch_date,
            "前前7天平均分": round(pre2_avg, 2) if pre2_avg else None,
            "前7天平均分": round(avg_score, 2),
            "加速度": acceleration,
            "前前7天分数": [round(s, 2) for s in pre2_score_list],
            "前7天分数": [round(s, 2) for s in score_list],
            "窗口涨幅": round(window_return, 2),
            "启动后最大涨幅": round(max_return_after, 2),
        })

    print(f"\n分析完成：")
    print(f"  有启动点：{len(results)} 只")
    print(f"  无启动点：{len(no_launch)} 只")
    print(f"  无评分数据：{len(no_score)} 只")

    if not results:
        print("没有找到任何启动点，分析结束。")
        return

    # === 输出详情CSV ===
    detail_df = pd.DataFrame(results)
    # 把分数列表转成字符串方便CSV存储
    detail_df["前前7天分数"] = detail_df["前前7天分数"].apply(lambda x: str(x))
    detail_df["前7天分数"] = detail_df["前7天分数"].apply(lambda x: str(x))
    detail_path = output_dir / "launch_detail.csv"
    detail_df.to_csv(detail_path, index=False, encoding="utf-8-sig")
    print(f"\n详情已保存：{detail_path}")

    # === 统计分析 ===
    pre7_list = [r["前7天平均分"] for r in results]
    pre7_arr = np.array(pre7_list)

    pre2_list = [r["前前7天平均分"] for r in results if r["前前7天平均分"] is not None]
    pre2_arr = np.array(pre2_list) if pre2_list else np.array([])

    accel_list = [r["加速度"] for r in results if r["加速度"] is not None]
    accel_arr = np.array(accel_list) if accel_list else np.array([])

    print("\n" + "=" * 60)
    print(f"  {args.year}年 启动信号分析报告")
    print("=" * 60)
    print(f"窗口：{args.window}天内涨幅≥{args.threshold}%")
    print(f"分析股票：{len(stock_codes)} 只自选股")
    print(f"找到启动点：{len(results)} 只")
    print()

    # 前前7天 vs 前7天 对比
    print("【前前7天 vs 前7天】加速分析：")
    print("-" * 60)
    print(f"{'指标':<12}{'前前7天':<15}{'前7天':<15}{'加速度':<12}")
    print("-" * 60)
    if len(pre2_arr) > 0:
        print(f"{'平均值':<12}{np.mean(pre2_arr):<15.2f}{np.mean(pre7_arr):<15.2f}{np.mean(accel_arr):<12.2f}")
        print(f"{'中位数':<12}{np.median(pre2_arr):<15.2f}{np.median(pre7_arr):<15.2f}{np.median(accel_arr):<12.2f}")
        print(f"{'25%分位':<12}{np.percentile(pre2_arr, 25):<15.2f}{np.percentile(pre7_arr, 25):<15.2f}{np.percentile(accel_arr, 25):<12.2f}")
        print(f"{'75%分位':<12}{np.percentile(pre2_arr, 75):<15.2f}{np.percentile(pre7_arr, 75):<15.2f}{np.percentile(accel_arr, 75):<12.2f}")
    print()

    # 加速度分布
    if len(accel_arr) > 0:
        print("加速度分布（前7天 - 前前7天）：")
        print(f"  加速上升（>0）：{np.sum(accel_arr > 0)} 只（{np.sum(accel_arr > 0)/len(accel_arr)*100:.1f}%）")
        print(f"  加速上升 > 3分：{np.sum(accel_arr > 3)} 只（{np.sum(accel_arr > 3)/len(accel_arr)*100:.1f}%）")
        print(f"  加速上升 > 5分：{np.sum(accel_arr > 5)} 只（{np.sum(accel_arr > 5)/len(accel_arr)*100:.1f}%）")
        print(f"  基本持平（±2）：{np.sum(np.abs(accel_arr) <= 2)} 只（{np.sum(np.abs(accel_arr) <= 2)/len(accel_arr)*100:.1f}%）")
        print(f"  减速下降（<0）：{np.sum(accel_arr < 0)} 只（{np.sum(accel_arr < 0)/len(accel_arr)*100:.1f}%）")
        print()

    print("前7天平均分分布：")
    print(f"  最小值：  {np.min(pre7_arr):.2f} 分")
    print(f"  25%分位：{np.percentile(pre7_arr, 25):.2f} 分")
    print(f"  中位数：  {np.median(pre7_arr):.2f} 分")
    print(f"  75%分位：{np.percentile(pre7_arr, 75):.2f} 分")
    print(f"  最大值：  {np.max(pre7_arr):.2f} 分")
    print(f"  平均值：  {np.mean(pre7_arr):.2f} 分")
    print(f"  标准差：  {np.std(pre7_arr):.2f} 分")
    print()

    print("阈值建议（不同阈值下的命中率）：")
    print("-" * 50)
    for threshold in [25, 30, 35, 40, 45, 50]:
        count = np.sum(pre7_arr >= threshold)
        pct = count / len(pre7_arr) * 100
        print(f"  阈值 ≥ {threshold:2d}分 → {count:3d} 只触发（命中率 {pct:.1f}%）")
    print()

    # === 保存汇总报告 ===
    summary_path = output_dir / "launch_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"{args.year}年 启动信号分析报告\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"窗口：{args.window}天内涨幅≥{args.threshold}%\n")
        f.write(f"看启动前：{args.pre_days}天评分\n")
        f.write(f"分析股票：{len(stock_codes)} 只自选股\n")
        f.write(f"找到启动点：{len(results)} 只\n")
        f.write(f"无启动点：{len(no_launch)} 只\n\n")

        # 加速分析
        f.write("【前前7天 vs 前7天】加速分析：\n")
        f.write("-" * 60 + "\n")
        if len(pre2_arr) > 0:
            f.write(f"{'指标':<12}{'前前7天':<15}{'前7天':<15}{'加速度':<12}\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'平均值':<12}{np.mean(pre2_arr):<15.2f}{np.mean(pre7_arr):<15.2f}{np.mean(accel_arr):<12.2f}\n")
            f.write(f"{'中位数':<12}{np.median(pre2_arr):<15.2f}{np.median(pre7_arr):<15.2f}{np.median(accel_arr):<12.2f}\n")
            f.write(f"{'25%分位':<12}{np.percentile(pre2_arr, 25):<15.2f}{np.percentile(pre7_arr, 25):<15.2f}{np.percentile(accel_arr, 25):<12.2f}\n")
            f.write(f"{'75%分位':<12}{np.percentile(pre2_arr, 75):<15.2f}{np.percentile(pre7_arr, 75):<15.2f}{np.percentile(accel_arr, 75):<12.2f}\n")
        f.write("\n")

        if len(accel_arr) > 0:
            f.write("加速度分布（前7天 - 前前7天）：\n")
            f.write(f"  加速上升（>0）：{np.sum(accel_arr > 0)} 只（{np.sum(accel_arr > 0)/len(accel_arr)*100:.1f}%）\n")
            f.write(f"  加速上升 > 3分：{np.sum(accel_arr > 3)} 只（{np.sum(accel_arr > 3)/len(accel_arr)*100:.1f}%）\n")
            f.write(f"  加速上升 > 5分：{np.sum(accel_arr > 5)} 只（{np.sum(accel_arr > 5)/len(accel_arr)*100:.1f}%）\n")
            f.write(f"  基本持平（±2）：{np.sum(np.abs(accel_arr) <= 2)} 只（{np.sum(np.abs(accel_arr) <= 2)/len(accel_arr)*100:.1f}%）\n")
            f.write(f"  减速下降（<0）：{np.sum(accel_arr < 0)} 只（{np.sum(accel_arr < 0)/len(accel_arr)*100:.1f}%）\n")
            f.write("\n")

        f.write("前7天平均分分布：\n")
        f.write(f"  最小值：  {np.min(pre7_arr):.2f} 分\n")
        f.write(f"  25%分位：{np.percentile(pre7_arr, 25):.2f} 分\n")
        f.write(f"  中位数：  {np.median(pre7_arr):.2f} 分\n")
        f.write(f"  75%分位：{np.percentile(pre7_arr, 75):.2f} 分\n")
        f.write(f"  最大值：  {np.max(pre7_arr):.2f} 分\n")
        f.write(f"  平均值：  {np.mean(pre7_arr):.2f} 分\n")
        f.write(f"  标准差：  {np.std(pre7_arr):.2f} 分\n\n")

        f.write("阈值建议（不同阈值下的命中率）：\n")
        f.write("-" * 50 + "\n")
        for threshold in [25, 30, 35, 40, 45, 50]:
            count = np.sum(pre7_arr >= threshold)
            pct = count / len(pre7_arr) * 100
            f.write(f"  阈值 ≥ {threshold:2d}分 → {count:3d} 只触发（命中率 {pct:.1f}%）\n")
        f.write("\n")

        # 列出所有启动股票详情
        f.write("启动股票详情：\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'股票代码':<10}{'股票名称':<12}{'启动日期':<12}{'前前7天均分':<12}{'前7天均分':<12}{'加速度':<10}{'窗口涨幅':<12}{'启动后最大涨幅':<12}\n")
        for r in sorted(results, key=lambda x: x["前7天平均分"]):
            f.write(f"{r['股票代码']:<10}{r['股票名称']:<12}{r['启动日期']:<12}"
                    f"{str(r['前前7天平均分']):<12}{r['前7天平均分']:<12}"
                    f"{str(r['加速度']):<10}{r['窗口涨幅']:<12}{r['启动后最大涨幅']:<12}\n")

    print(f"汇总报告已保存：{summary_path}")


if __name__ == "__main__":
    main()
