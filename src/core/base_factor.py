from typing import Dict

class BaseFactor:
    """因子基类：所有因子应继承并实现 calculate() 方法。

    calculate() 应返回一个 dict，至少包含：
      - name: str
      - score: float (该因子得分，0~max)
      - weight: float (该因子占比, 例如 0.1 表示10%)
      - meta: dict (可选，附加信息用于展示)
    """
    def __init__(self, code, name=None):
        self.code = code
        self.name = name or ""

    def calculate(self) -> Dict:
        raise NotImplementedError("子类必须实现 calculate 方法")
