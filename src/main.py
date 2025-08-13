from src.selectors import filter_stocks

if __name__ == "__main__":
    print("=== 按条件筛选股票 ===")
    selected = filter_stocks()
    print(selected[['ts_code', 'name', 'pb', 'roe']])
    print(f"\n共筛选出 {len(selected)} 只股票")

print('Hello, Stock Picker')

