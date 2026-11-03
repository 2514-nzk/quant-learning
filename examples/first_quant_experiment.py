"""用四只虚构股票演示先选股、后计算结果；只依赖 Python 标准功能。"""

# 决策时已经知道的表：选股函数只读取这里的过去涨幅。
known_stocks = [
    {"code": "A", "past_return": 0.08},
    {"code": "B", "past_return": -0.01},
    {"code": "C", "past_return": 0.04},
    {"code": "D", "past_return": 0.02},
]


def read_score(stock):
    return stock["past_return"]


ranked = sorted(known_stocks, key=read_score, reverse=True)
selected = ranked[:2]

# 事后才知道的表：完成选股之后，用它计算这次实验的成绩。
future_prices = {
    "A": {"entry": 10.00, "exit": 10.50},
    "B": {"entry": 20.00, "exit": 20.20},
    "C": {"entry": 8.00, "exit": 8.24},
    "D": {"entry": 15.00, "exit": 14.70},
}


def calculate_return(code):
    prices = future_prices[code]
    return prices["exit"] / prices["entry"] - 1


selected_total = 0.0
selected_codes = []
for stock in selected:
    selected_codes.append(stock["code"])
    selected_total = selected_total + calculate_return(stock["code"])
portfolio_return = selected_total / len(selected)

all_total = 0.0
for stock in known_stocks:
    all_total = all_total + calculate_return(stock["code"])
benchmark_return = all_total / len(known_stocks)

initial_money = 8000.0
final_money = initial_money * (1 + portfolio_return)

print("入选股票：" + "、".join(selected_codes))
print(f"组合毛收益：{portfolio_return:.2%}")
print(f"候选股票等权平均：{benchmark_return:.2%}")
print(f"比基准多：{(portfolio_return - benchmark_return) * 100:.2f} 个百分点")
print(f"8000 元期末变为：{final_money:.2f} 元（未扣费用）")
