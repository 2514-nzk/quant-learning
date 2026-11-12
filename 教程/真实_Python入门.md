# 起步第二课｜让 Python 重做真实股票的选股题

上一课已经算出：2024 年 6 月 21 日收盘后，按五日涨幅选出的前两只股票是**寒武纪、宁德时代**。现在让电脑重复相同的动作。

## 1. 一张表，在程序里还是一张表

在交易软件里，每一行是一只股票，每一列是涨幅或价格。Python 也用相同思路处理：

~~~python
stocks = [
    {"name": "寒武纪", "past_return": 7.64},
    {"name": "宁德时代", "past_return": 0.15},
    {"name": "比亚迪", "past_return": -0.94},
    {"name": "贵州茅台", "past_return": -5.40},
]
~~~

这里四个百分数是**四舍五入后的真实历史涨幅**，仅为学语法；真正计算时要使用完整价格，不要先把涨幅截断再当原始数据。**列表**就是按顺序放在一起的多条记录；每条记录用“股票名、涨幅”这样的键和值描述一只股票。

方括号是一张记录列表；花括号是一行记录；每行的 name 是股票名字，past_return 是过去五日涨幅。

## 2. 电脑怎样排队？

~~~python
ranked = sorted(stocks, key=lambda row: row["past_return"], reverse=True)
selected = ranked[:2]
for item in selected:
    print(item["name"])
~~~

输出：

~~~text
寒武纪
宁德时代
~~~

- sorted 就是排序；reverse=True 是从大到小。
- row["past_return"] 是取每行的涨幅，lambda 是临时写一条“取哪列”的规则。
- [:2] 是取前两名；for 是把入选股票逐个打印。

<details>
<summary>练习：如果改成选前三只，会多出哪只？</summary>

会多出**比亚迪**。因为前三名按涨幅从高到低分别是寒武纪、宁德时代和比亚迪。

</details>

## 3. 真正的数据不用手抄

这本书还有一份可运行的 Python 练习，直接读取四只股票的真实日 K 线计算结果，而不是从上面四个手抄百分数出发。

~~~powershell
python examples/real_stock_learner.py
~~~

你会看到每只股票的过去五日涨幅、之后的区间收益，以及两只股票组合和四只等权组合的期末金额。

第一次学习的目标是弄懂 **stocks 是表、sorted 是排序、selected 是取前几名**。下一章先比较选股组合和一个简单对照组合，随后才会学更复杂的数据处理。

[下一章：怎样判断选股是否比不选更好](真实_01_收益与基准.md)