import pkgutil
import importlib
from typing import List, Dict
from pathlib import Path

FACTORS_PACKAGE = "src.factors"


def discover_and_run(code: str) -> List[Dict]:
    """动态发现 src/factors 下的因子模块并执行 calculate，返回因子结果列表。"""
    results = []
    package_dir = Path(__file__).resolve().parents[1] / "factors"
    for finder, name, ispkg in pkgutil.iter_modules([str(package_dir)]):
        module_name = f"src.factors.{name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            # 如果某个因子加载失败，打印错误但继续
            print(f"加载因子 {module_name} 失败: {e}")
            continue

        # 在模块内查找所有继承 BaseFactor 的类并执行
        for attr in dir(module):
            cls = getattr(module, attr)
            try:
                # 判断是否为类且有 calculate 方法
                if isinstance(cls, type) and hasattr(cls, 'calculate'):
                    inst = cls(code)
                    results.append(inst.calculate())
            except Exception as e:
                print(f"执行因子 {module_name}.{attr} 失败: {e}")
    return results
