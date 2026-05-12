"""
行业数据批量构建脚本（使用同花顺+申万接口）

功能：
1. 构建行业成分股映射表（使用申万接口）
2. 批量获取所有行业的涨跌幅数据（使用同花顺接口）
3. 支持分批执行、中断恢复
4. 带请求延时和错误重试，避免被封

使用方法：
    python -m src.datafactory.build_industry_data --full       # 完整构建
    python -m src.datafactory.build_industry_data --industry   # 只构建行业映射
    python -m src.datafactory.build_industry_data --changes    # 只构建行业涨跌幅
"""
import os
import sys
import time
import argparse
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.datafactory.data_manager import (
    INDUSTRY_PATH, _read_csv_if_exists
)

# 配置
INDUSTRY_PATH = "data/industry"
MAX_RETRIES = 3
REQUEST_DELAY = 2.0  # 请求间隔（秒）
BATCH_SIZE = 10  # 每批处理行业数

# 同花顺行业名称 → 申万行业代码 的映射
# 部分常用行业映射（可以在运行过程中补充）
THS_TO_SW = {
    '银行': '801780',
    '证券': '801790',
    '保险': '801790',
    '非银金融': '801790',
    '房地产': '801720',
    '农林牧渔': '801010',
    '农业': '801010',
    '牧业': '801010',
    '化工': '801030',
    '化学制品': '801030',
    '钢铁': '801020',
    '有色金属': '801050',
    '有色': '801050',
    '建筑材料': '801050',
    '建筑装饰': '801720',
    '装修装饰': '801720',
    '电气设备': '801730',
    '电力设备': '801730',
    '机械设备': '801730',
    '工程机械设备': '801730',
    '汽车': '801880',
    '汽车整车': '801880',
    '汽车零部件': '801880',
    '轻工制造': '801110',
    '纺织服装': '801110',
    '服装家纺': '801110',
    '家用电器': '801130',
    '白色家电': '801130',
    '食品饮料': '801150',
    '白酒': '801150',
    '休闲服务': '801210',
    '旅游': '801210',
    '商业贸易': '801200',
    '零售': '801200',
    '医药生物': '801150',
    '医疗器械': '801150',
    '中药': '801150',
    '化学制药': '801150',
    '生物制品': '801150',
    '电子': '801080',
    '半导体': '801080',
    '计算机': '801750',
    '软件开发': '801750',
    '传媒': '801760',
    '游戏': '801760',
    '通信': '801770',
    '通信设备': '801770',
    '公用事业': '801210',
    '电力': '801210',
    '交通运输': '801020',
    '物流': '801020',
    '采掘': '801020',
    '煤炭': '801020',
    '石油开采': '801020',
    '综合': '801010',
    '国防军工': '801660',
    '军工': '801660',
    '航空装备': '801660',
    '船舶制造': '801660',
}

# 申万二级行业代码列表（共131个）
SW_CODES = [
    ('801016', '种植业', '农林牧渔'),
    ('801015', '渔业', '农林牧渔'),
    ('801011', '林业Ⅱ', '农林牧渔'),
    ('801014', '饲料', '农林牧渔'),
    ('801012', '农产品加工', '农林牧渔'),
    ('801017', '养殖业', '农林牧渔'),
    ('801018', '动物保健Ⅱ', '农林牧渔'),
    ('801019', '农业综合Ⅱ', '农林牧渔'),
    ('801033', '化学原料', '基础化工'),
    ('801034', '化学制品', '基础化工'),
    ('801032', '化学纤维', '基础化工'),
    ('801036', '塑料', '基础化工'),
    ('801037', '橡胶', '基础化工'),
    ('801038', '农化制品', '基础化工'),
    ('801039', '非金属材料Ⅱ', '基础化工'),
    ('801043', '冶钢原料', '钢铁'),
    ('801044', '普钢', '钢铁'),
    ('801045', '特钢Ⅱ', '钢铁'),
    ('801051', '金属新材料', '有色金属'),
    ('801055', '工业金属', '有色金属'),
    ('801053', '贵金属', '有色金属'),
    ('801054', '小金属', '有色金属'),
    ('801056', '能源金属', '有色金属'),
    ('801081', '半导体', '电子'),
    ('801083', '元件', '电子'),
    ('801084', '光学光电子', '电子'),
    ('801082', '其他电子Ⅱ', '电子'),
    ('801085', '消费电子', '电子'),
    ('801086', '电子化学品Ⅱ', '电子'),
    ('801093', '汽车零部件', '汽车'),
    ('801092', '汽车服务', '汽车'),
    ('801881', '摩托车及其他', '汽车'),
    ('801095', '乘用车', '汽车'),
    ('801096', '商用车', '汽车'),
    ('801111', '白色家电', '家用电器'),
    ('801112', '黑色家电', '家用电器'),
    ('801113', '小家电', '家用电器'),
    ('801114', '厨卫电器', '家用电器'),
    ('801115', '照明设备Ⅱ', '家用电器'),
    ('801116', '家电零部件Ⅱ', '家用电器'),
    ('801117', '其他家电Ⅱ', '家用电器'),
    ('801124', '食品加工', '食品饮料'),
    ('801125', '白酒Ⅱ', '食品饮料'),
    ('801126', '非白酒', '食品饮料'),
    ('801127', '饮料乳品', '食品饮料'),
    ('801128', '休闲食品', '食品饮料'),
    ('801129', '调味发酵品Ⅱ', '食品饮料'),
    ('801131', '纺织制造', '纺织服饰'),
    ('801132', '服装家纺', '纺织服饰'),
    ('801133', '饰品', '纺织服饰'),
    ('801143', '造纸', '轻工制造'),
    ('801141', '包装印刷', '轻工制造'),
    ('801142', '家居用品', '轻工制造'),
    ('801145', '文娱用品', '轻工制造'),
    ('801151', '化学制药', '医药生物'),
    ('801155', '中药Ⅱ', '医药生物'),
    ('801152', '生物制品', '医药生物'),
    ('801154', '医药商业', '医药生物'),
    ('801153', '医疗器械', '医药生物'),
    ('801156', '医疗服务', '医药生物'),
    ('801161', '电力', '公用事业'),
    ('801163', '燃气Ⅱ', '公用事业'),
    ('801178', '物流', '交通运输'),
    ('801179', '铁路公路', '交通运输'),
    ('801991', '航空机场', '交通运输'),
    ('801992', '航运港口', '交通运输'),
    ('801181', '房地产开发', '房地产'),
    ('801183', '房地产服务', '房地产'),
    ('801202', '贸易Ⅱ', '商贸零售'),
    ('801203', '一般零售', '商贸零售'),
    ('801204', '专业连锁Ⅱ', '商贸零售'),
    ('801206', '互联网电商', '商贸零售'),
    ('801207', '旅游零售Ⅱ', '商贸零售'),
    ('801216', '体育Ⅱ', '社会服务'),
    ('801218', '专业服务', '社会服务'),
    ('801219', '酒店餐饮', '社会服务'),
    ('801993', '旅游及景区', '社会服务'),
    ('801994', '教育', '社会服务'),
    ('801782', '国有大型银行Ⅱ', '银行'),
    ('801783', '股份制银行Ⅱ', '银行'),
    ('801784', '城商行Ⅱ', '银行'),
    ('801785', '农商行Ⅱ', '银行'),
    ('801193', '证券Ⅱ', '非银金融'),
    ('801194', '保险Ⅱ', '非银金融'),
    ('801191', '多元金融', '非银金融'),
    ('801231', '综合Ⅱ', '综合'),
    ('801711', '水泥', '建筑材料'),
    ('801712', '玻璃玻纤', '建筑材料'),
    ('801713', '装修建材', '建筑材料'),
    ('801721', '房屋建设Ⅱ', '建筑装饰'),
    ('801722', '装修装饰Ⅱ', '建筑装饰'),
    ('801723', '基础建设', '建筑装饰'),
    ('801724', '专业工程', '建筑装饰'),
    ('801726', '工程咨询服务Ⅱ', '建筑装饰'),
    ('801731', '电机Ⅱ', '电力设备'),
    ('801733', '其他电源设备Ⅱ', '电力设备'),
    ('801735', '光伏设备', '电力设备'),
    ('801736', '风电设备', '电力设备'),
    ('801737', '电池', '电力设备'),
    ('801738', '电网设备', '电力设备'),
    ('801072', '通用设备', '机械设备'),
    ('801074', '专用设备', '机械设备'),
    ('801076', '轨交设备Ⅱ', '机械设备'),
    ('801077', '工程机械', '机械设备'),
    ('801078', '自动化设备', '机械设备'),
    ('801741', '航天装备Ⅱ', '国防军工'),
    ('801742', '航空装备Ⅱ', '国防军工'),
    ('801743', '地面兵装Ⅱ', '国防军工'),
    ('801744', '航海装备Ⅱ', '国防军工'),
    ('801745', '军工电子Ⅱ', '国防军工'),
    ('801101', '计算机设备', '计算机'),
    ('801103', 'IT服务Ⅱ', '计算机'),
    ('801104', '软件开发', '计算机'),
    ('801764', '游戏Ⅱ', '传媒'),
    ('801765', '广告营销', '传媒'),
    ('801766', '影视院线', '传媒'),
    ('801767', '数字媒体', '传媒'),
    ('801769', '出版', '传媒'),
    ('801995', '电视广播Ⅱ', '传媒'),
    ('801223', '通信服务', '通信'),
    ('801102', '通信设备', '通信'),
    ('801951', '煤炭开采', '煤炭'),
    ('801952', '焦炭Ⅱ', '煤炭'),
    ('801961', '油气开采Ⅱ', '石油石化'),
    ('801962', '油服工程', '石油石化'),
    ('801963', '炼化及贸易', '石油石化'),
    ('801971', '环境治理', '环保'),
    ('801972', '环保设备Ⅱ', '环保'),
    ('801981', '个护用品', '美容护理'),
    ('801982', '化妆品', '美容护理'),
    ('801983', '医疗美容', '美容护理'),
]


def get_with_retry(func, *args, **kwargs):
    """带重试的请求"""
    for i in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"    重试 {i+1}/{MAX_RETRIES}: {e}")
            time.sleep(3)
    return None


def build_industry_mapping(force=False):
    """构建行业成分股映射表（使用申万接口）

    防封策略：
    - 使用申万接口获取成分股（更稳定）
    - 每处理一个行业后延时 REQUEST_DELAY 秒
    - 每批处理 BATCH_SIZE 个行业后延时更长时间
    - 支持中断恢复（已有数据跳过）
    """
    os.makedirs(INDUSTRY_PATH, exist_ok=True)
    mapping_file = os.path.join(INDUSTRY_PATH, "stock_industry_mapping.csv")

    existing = _read_csv_if_exists(mapping_file)
    if existing is not None and not existing.empty and not force:
        print(f"行业映射已存在，共 {len(existing)} 条记录")
        return existing

    print("=" * 50)
    print("开始构建行业成分股映射表（申万接口）...")
    print("=" * 50)

    try:
        # 加载已处理的行业（支持中断恢复）
        processed_file = os.path.join(INDUSTRY_PATH, "processed_sw_industries.txt")
        if force:
            processed = set()
        else:
            try:
                with open(processed_file, 'r') as f:
                    processed = set(line.strip() for line in f if line.strip())
            except FileNotFoundError:
                processed = set()

        print(f"已处理: {len(processed)} 个行业")

        all_mappings = []

        # 遍历申万行业，获取成分股
        for idx, item in enumerate(SW_CODES):
            sw_code = item[0]
            sw_name = item[1]  # 二级行业名称
            if sw_code in processed:
                continue

            print(f"  [{idx+1}/{len(SW_CODES)}] 处理: {sw_name}({sw_code})...", end=" ")

            try:
                # 获取该行业的成分股
                cons_df = get_with_retry(ak.index_component_sw, symbol=sw_code)
                if cons_df is None or cons_df.empty:
                    print("无数据")
                    processed.add(sw_code)
                    time.sleep(REQUEST_DELAY)
                    continue

                # 提取股票代码
                count = 0
                for _, cons_row in cons_df.iterrows():
                    code = str(cons_row.get('证券代码', ''))
                    if code and code != 'nan':
                        code = code.zfill(6)
                        all_mappings.append({
                            '股票代码': code,
                            '行业名称': sw_name,
                            '行业代码': sw_code
                        })
                        count += 1

                print(f"获取 {count} 只股票")
                processed.add(sw_code)

                # 保存已处理进度
                with open(processed_file, 'w') as f:
                    f.write('\n'.join(processed))

                # 每批处理后延时
                if (idx + 1) % BATCH_SIZE == 0:
                    print(f"\n  ---- 已处理 {idx+1} 个行业，延时 10 秒 ----")
                    time.sleep(10)

                time.sleep(REQUEST_DELAY)

            except Exception as e:
                print(f"失败: {e}")
                time.sleep(2)
                continue

        # 保存结果
        if all_mappings:
            mapping_df = pd.DataFrame(all_mappings)
            # 按行业代码排序，使更细分的行业（如汽车801880）优先保留
            mapping_df = mapping_df.sort_values('行业代码', ascending=False)
            # 去重，保留排序后的第一条（即更细分的行业）
            mapping_df = mapping_df.drop_duplicates(subset=['股票代码'], keep='first')
            mapping_df.to_csv(mapping_file, index=False)
            print(f"\n映射构建完成，共 {len(mapping_df)} 只股票")

            # 清理进度文件
            if os.path.exists(processed_file):
                os.remove(processed_file)

            return mapping_df

        # 如果全部跳过
        if existing is not None and not existing.empty:
            print(f"使用已有数据，共 {len(existing)} 只股票")
            return existing

        return None

    except Exception as e:
        print(f"构建行业映射失败: {e}")
        return existing


def build_all_industry_changes(days=20):
    """批量获取所有行业的涨跌幅数据（使用申万指数接口）

    防封策略：
    - 使用申万指数接口获取行业涨跌幅（数据最新）
    - 本地缓存，已有数据跳过
    - 带请求延时
    """
    os.makedirs(INDUSTRY_PATH, exist_ok=True)

    # 使用申万行业代码列表
    industries = SW_CODES
    print(f"共 {len(industries)} 个申万行业需要获取涨跌幅")

    # 2. 批量获取每个行业的涨跌幅
    processed_file = os.path.join(INDUSTRY_PATH, "processed_sw_changes.txt")
    try:
        with open(processed_file, 'r') as f:
            processed = set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        processed = set()

    print(f"已处理: {len(processed)} 个行业")

    success_count = 0
    for idx, item in enumerate(industries):
        sw_code = item[0]
        sw_name = item[1]
        cache_key = f"{sw_code}_{days}"
        if cache_key in processed:
            continue

        print(f"  [{idx+1}/{len(industries)}] 获取 {sw_name}({sw_code}) 涨跌幅...", end=" ")

        file_path = os.path.join(INDUSTRY_PATH, f"change_{sw_code}_{days}d.csv")

        # 检查本地是否已有
        local = _read_csv_if_exists(file_path)
        if local is not None and not local.empty:
            print("已有缓存")
            processed.add(cache_key)
            continue

        try:
            # 使用申万指数接口（数据最新）
            remote = get_with_retry(
                ak.index_hist_sw,
                symbol=sw_code,
                period="day"
            )

            if remote is None or remote.empty:
                print("无数据")
                time.sleep(REQUEST_DELAY)
                continue

            # 处理数据
            if '日期' in remote.columns:
                remote['日期'] = pd.to_datetime(remote['日期'])
            elif 'date' in remote.columns:
                remote['日期'] = pd.to_datetime(remote['date'])
            else:
                print("无日期列")
                time.sleep(REQUEST_DELAY)
                continue

            # sort by date, calculate from latest date
            remote = remote.sort_values('日期')
            end_date = remote['日期'].max()
            start_date = end_date - timedelta(days=days)
            remote = remote[remote['日期'] >= start_date]

            if len(remote) >= 2:
                start_price = remote.iloc[0]['收盘']
                end_price = remote.iloc[-1]['收盘']
                change_pct = (end_price - start_price) / start_price * 100

                result = pd.DataFrame({
                    'industry': [sw_name],
                    'industry_code': [sw_code],
                    'change_pct': [round(change_pct, 2)],
                    'days': [days],
                    'update_time': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                })
                result.to_csv(file_path, index=False)
                print(f"+{change_pct:.2f}%")
                success_count += 1
            else:
                print("数据不足")

            processed.add(cache_key)
            time.sleep(REQUEST_DELAY)

            # 每批处理后延时
            if (idx + 1) % BATCH_SIZE == 0:
                print(f"\n  ---- 已处理 {idx+1} 个行业，延时 10 秒 ----")
                time.sleep(10)

        except Exception as e:
            print(f"失败: {e}")
            time.sleep(2)
            continue

    # 保存进度
    with open(processed_file, 'w') as f:
        f.write('\n'.join(processed))

    print(f"\n行业涨跌幅构建完成，成功 {success_count} 个")


def clear_cache():
    """清理行业数据缓存（重新构建）"""
    import shutil

    if os.path.exists(INDUSTRY_PATH):
        # 备份旧数据
        backup_dir = f"{INDUSTRY_PATH}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.move(INDUSTRY_PATH, backup_dir)
        print(f"旧数据已备份到: {backup_dir}")

    os.makedirs(INDUSTRY_PATH, exist_ok=True)
    print("缓存已清理")


def main():
    parser = argparse.ArgumentParser(description='行业数据构建工具（同花顺+申万）')
    parser.add_argument('--full', action='store_true', help='完整构建（行业映射 + 涨跌幅）')
    parser.add_argument('--industry', action='store_true', help='只构建行业成分股映射（申万）')
    parser.add_argument('--changes', action='store_true', help='只构建行业涨跌幅（同花顺）')
    parser.add_argument('--clear', action='store_true', help='清理缓存重新构建')
    parser.add_argument('--days', type=int, default=20, help='涨跌幅统计天数（默认20天）')

    args = parser.parse_args()

    if args.clear:
        clear_cache()

    if args.full or args.industry:
        print("\n" + "=" * 50)
        print("步骤1: 构建行业成分股映射（申万接口）")
        print("=" * 50)
        build_industry_mapping()

    if args.full or args.changes:
        print("\n" + "=" * 50)
        print(f"步骤2: 构建行业涨跌幅（同花顺接口，最近{args.days}天）")
        print("=" * 50)
        build_all_industry_changes(days=args.days)

    if not (args.full or args.industry or args.changes):
        parser.print_help()
        print("\n示例:")
        print("  python -m src.datafactory.build_industry_data --full       # 完整构建")
        print("  python -m src.datafactory.build_industry_data --industry   # 只构建行业映射")
        print("  python -m src.datafactory.build_industry_data --changes    # 只构建行业涨跌幅")
        print("  python -m src.datafactory.build_industry_data --clear      # 清理缓存")


if __name__ == "__main__":
    main()