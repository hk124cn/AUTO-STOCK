import importlib
import pkgutil
import pandas as pd
import sys

from src.core.base_factor import BaseFactor


def load_factors():
    factors = []
    for _, module_name, _ in pkgutil.iter_modules(['src/factors']):
        module = importlib.import_module(f"src.factors.{module_name}")
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, BaseFactor) and obj is not BaseFactor:
                factors.append(obj)
    return factors


def run_single(code):
    name = code

    print(f"\n=== {code} 多因子评分系统 ===")

    factor_classes = load_factors()
    total_score = 0
    s_score = 0
    single_result = {}
    for cls in factor_classes:
        factor = cls(code, name)
        result = factor.calculate()

        factor_name = result.get('name', '因子X')
        factor_score = result.get('score', 0)
        sum_score = result.get('sum_score', 10)
        single_result.update({factor_name:factor_score})

        total_score += factor_score
        s_score += sum_score

        print(f"📊 {factor_name} => {factor_score:.2f}")

    print(f"\n总得分: {total_score:.2f} / {s_score}")
    single_result.update({'total_score':total_score})
    return single_result 


def run_batch(csv_file):
    df = pd.read_csv(csv_file)

    if "code" not in df.columns:
        print("CSV必须包含 code 列")
        return

    results = []

    for code,name in zip(df["code"],df["name"]):
        code = str(code).zfill(6)   # 自动补齐6位
        print(f"\n====== 正在计算 {code} ======")
        single_result = run_single(str(code))
        single_result.update({"code": code, "name": name})
        results.append(single_result)
        #results.append({"code": code, "name": name, "score": score})

    result_df = pd.DataFrame(results)
    # 调整列顺序：code, name 放前面
    cols = ["code", "name"] + [c for c in result_df.columns if c not in ["code", "name"]]
    result_df = result_df[cols]
    result_df = result_df.sort_values(by="total_score", ascending=False)

    result_df.to_csv("batch_result.csv", index=False)
    print("\n批量评分完成，结果已保存 batch_result.csv")


def main():
    print("选择模式:")
    print("1. 单股评分")
    print("2. 批量评分")

    mode = input("请输入模式编号: ").strip()

    if mode == "1":
        code = input("请输入股票代码: ").strip()
        run_single(code)

    elif mode == "2":
        file = input("请输入股票池CSV路径: ").strip()
        run_batch(file)

    else:
        print("无效输入")


if __name__ == "__main__":
    main()