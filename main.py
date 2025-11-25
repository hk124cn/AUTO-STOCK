# main.py
from src.factors.financial_factor import FinancialFactor

def main():
    code = input("请输入股票代码：").strip()
    name = "股票名"

    f = FinancialFactor(code, name)
    result = f.calculate()

    print(f"\n=== {code} 财报因子 ===")
    print(f"得分: {result['score']}/{result['max_score']}")
    print(f"详细: {result['meta']}")

if __name__ == "__main__":
    main()
