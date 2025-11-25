import importlib
import pkgutil
from factors import *
from base_factor import BaseFactor

def load_factors():
    factors = []
    for _, module_name, _ in pkgutil.iter_modules(['factors']):
        module = importlib.import_module(f"factors.{module_name}")
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

    for cls in factor_classes:
        factor = cls(code, name)
        result = factor.calculate()
        weight = getattr(factor, 'weight', 0)
        score = result.get('score', 0)
        total_score += score
        total_weight += weight
        print(f"📊 {result['name']} => {score:.2f}")

    print(f"\n总得分: {total_score:.2f} / {len(factor_classes) * 10:.0f}")
    print("（每个因子已按权重比例自动加载）")


if __name__ == "__main__":
    main()
