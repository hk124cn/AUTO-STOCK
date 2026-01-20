import importlib
import pkgutil
from src.factors import *
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


def main():
    code = input("请输入股票代码：").strip()
    name = code  # 你也可以用 ak 获取名称

    print(f"\n=== {code} 多因子评分系统 ===")
    factor_classes = load_factors()
    total_score = 0
    total_weight = 0
    s_score = 0

    for cls in factor_classes:
        factor = cls(code, name)
        result = factor.calculate()
        weight = getattr(factor, 'weight', 0)
        sum_score = result.get('sum_score', 10)
        score = result.get('score', 0)
        total_score += score
        total_weight += weight
        s_score += sum_score
        print(f"📊 {result['name']} => {score:.2f}")

    print(f"\n总得分: {total_score:.2f} / {s_score}")
    print("（每个因子已按权重比例自动加载）")


if __name__ == "__main__":
    main()
