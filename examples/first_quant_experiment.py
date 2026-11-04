"""用四只虚构股票演示先选股、再计算组合收益和期末资金；只依赖 Python 标准功能。"""

# 决策时已经知道的表：选股函数只读取这里的过去涨幅。
# 列表里的每个字典是一只股票；0.08 就是 8%。
known_stocks = [
    {"code": "A", "past_return": 0.08},
    {"code": "B", "past_return": -0.01},
    {"code": "C", "past_return": 0.04},
    {"code": "D", "past_return": 0.02},
]


# def 定义函数；stock 是传进来的一条股票记录。
def read_score(stock):
    return stock["past_return"]  # 用字段名取出过去涨幅，并交回给排序工具。


ranked = sorted(known_stocks, key=read_score, reverse=True)  # key 指定按哪个数排序；reverse=True 表示从大到小。
selected = ranked[:2]  # [:2] 取前两条记录，也就是本次要选的两只。

# 事后才知道的表：完成选股之后，用它计算这次实验的成绩。
# 外层按股票名字查，内层分别保存买入价 entry 和卖出价 exit。
future_prices = {
    "A": {"entry": 10.00, "exit": 10.50},
    "B": {"entry": 20.00, "exit": 20.20},
    "C": {"entry": 8.00, "exit": 8.24},
    "D": {"entry": 15.00, "exit": 14.70},
}


# 接收股票名字，例如 "A"，返回这只股票的收益率。
def calculate_return(code):
    prices = future_prices[code]  # 先找到这只股票对应的两项价格。
    return prices["exit"] / prices["entry"] - 1  # 卖出价除以买入价再减 1；0.05 表示赚了 5%。


selected_total = 0.0  # 从零开始累加入选股票的收益率。
selected_codes = []  # 准备一个空列表，收集入选股票的名字。
# 每次拿出一只入选股票，执行下面缩进的两行。
for stock in selected:
    selected_codes.append(stock["code"])  # append 把名字追加到列表末尾。
    selected_total = selected_total + calculate_return(stock["code"])  # 把当前这只股票的收益加到已有合计中。
portfolio_return = selected_total / len(selected)  # len 统计入选数量；等权时，用合计除以数量得到平均收益。

initial_money = 8000.0  # 保存初始本金，单位是元。
final_money = initial_money * (1 + portfolio_return)  # 本金乘以 1 加收益率，得到期末金额。

print("入选股票：" + "、".join(selected_codes))  # join 用顿号把名字连起来；print 把结果显示在终端。
print(f"组合毛收益：{portfolio_return:.2%}")  # f 字符串把变量填入花括号；.2% 按百分数保留两位小数。
print(f"8000 元期末变为：{final_money:.2f} 元（未扣费用）")
