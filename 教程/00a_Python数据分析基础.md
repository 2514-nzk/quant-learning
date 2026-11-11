# Python 数据分析基础｜从股票表格开始

**只炒过股、还没用过 Python 也可以读。** 这一页的第一段先让你用三只股票的价格算涨跌幅；如果看懂了，后面的表格操作可以等需要时再学。

## 第一次读这里：把 pandas 想成会算数的 Excel 表格

**不需要先弄懂 DataFrame 这个英文词。** 想象 Excel 里有三行：

| 股票 | 昨日收盘 | 今日收盘 |
|---|---:|---:|
| A | 10 元 | 11 元 |
| B | 20 元 | 19 元 |
| C | 8 元 | 8 元 |

你想新增一列“今天涨跌多少”：A 是 +10%、B 是 -5%、C 是 0%。用 Python 的 pandas，只是告诉电脑**对表格每一行都做一遍相同的计算**。

~~~python
import pandas as pd

df = pd.DataFrame({
    "股票": ["A", "B", "C"],
    "昨日": [10, 20, 8],
    "今日": [11, 19, 8],
})
df["涨跌幅"] = df["今日"] / df["昨日"] - 1
print(df[["股票", "涨跌幅"]])
~~~

你应该看到 A 的 0.10、B 的 -0.05、C 的 0.00。**今天第一次只需要看懂这一段**：一列是一个名字，一行是一只股票，新增列就是新增一个计算结果。后面的时间序列、合并、窗口运算可等到第 5 章学过涨幅和均线后再查。

<details>
<summary>小练习：B 的今日价格从 19 改成 22，涨跌幅会是多少？</summary>

22/20−1 = **10%**；只需改“今日”这一格，程序便会重新计算那一列。

</details>

<details>
<summary>选读｜开始独立做项目时，才需要看字段和约定</summary>

本手册供处理股票表格时按问题查阅。刚接触代码时，也可以先读[第一段量化代码](00g_读懂第一段量化代码.md)；理解表格和时间窗口后，继续看[量化数据处理工具](00d_量化Python实战.md)。

后面的正式示例默认你大致理解 Python 的变量、循环、函数；如果还不会，可以暂时只读上面的 Excel 表格例子。示例有时用 `date` 表示日期，课程统一用 `trade_date`；需要放进同一份程序时要先统一名字。

教学工程的字段包括 `trade_date`、`code`、`open`、`high`、`low`、`close`、`volume`、`amount`、`market_cap`；常见特征包括 `mom_5`、`mom_20`、`reversal_3`、`vol_20`、`range_1d`、`amount_chg_5`、`log_mkt_cap`。未来收益标签与其它字段的对接约定在真实项目阶段再查即可。

</details>

## 1. DataFrame：金融数据的天然容器

量化研究中的数据通常是**面板数据**（Panel Data）：多只股票 × 多个日期 × 多个字段。

```python
import pandas as pd  # 导入表格工具，后面简称 pd。
import numpy as np  # 导入数值计算工具，后面简称 np。

# 创建一个简单的股票数据
data = {
    'date': ['2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02'],
    'code': ['000001', '000002', '000001', '000002'],
    'close': [10.5, 20.3, 10.8, 20.1],
    'volume': [1000000, 800000, 1200000, 750000]
}
df = pd.DataFrame(data)  # 把字典转成表格：每个字段是一列，每个列表项对应一行。
print(df)
```

输出：
```
         date    code  close   volume
0  2024-01-01  000001   10.5  1000000
1  2024-01-01  000002   20.3   800000
2  2024-01-02  000001   10.8  1200000
3  2024-01-02  000002   20.1   750000
```

## 2. 时间序列索引

量化研究中日期是核心维度，必须正确处理：

```python
# 将字符串转为日期类型
df['date'] = pd.to_datetime(df['date'])

# 查看数据类型
print(df.dtypes)

# 按日期排序（极其重要！）
# 依次按股票、日期排序；reset_index(drop=True) 重新生成连续行号。
df = df.sort_values(['code', 'date']).reset_index(drop=True)

# 筛选日期范围
mask = (df['date'] >= '2024-01-02')  # 比较后得到一列 True/False，表示哪些行符合日期条件。
recent_data = df[mask]  # 只保留 mask 为 True 的行。
```

**为什么排序重要？** 因为后面计算收益率、滑动窗口时，如果数据乱序会得到错误结果。

## 3. 分组操作：按股票计算指标

这是量化分析的核心操作。每只股票都要单独计算收益、移动平均等。

```python
# 计算每只股票的收益率（当前价格/前一日价格 - 1）
# groupby 先按股票分堆，避免用另一只股票的价格算收益。
df['return'] = df.groupby('code')['close'].pct_change(fill_method=None)

# 计算每只股票的5日移动平均
# transform 将各股票算出的结果放回对应的原始行。
df['ma5'] = df.groupby('code')['close'].transform(
    lambda x: x.rolling(window=5, min_periods=1).mean()  # lambda 把每组价格临时叫 x；最近五行不足五行时也允许求均值。
)

# 正向 shift：获取同一股票前一行的值；市场交易日语义需要完整日历
df['prev_close'] = df.groupby('code')['close'].shift(1)

# 负向 shift：示范获取未来第 5 行；严格 T+5 标签应按市场日历连接
df['next_5d_close'] = df.groupby('code')['close'].shift(-5)

print(df)
```

**关键概念：**
- `groupby('code')` 确保每只股票独立计算
- `shift(1)` 取前一行，`shift(-5)` 取后五行；只有股票已对齐完整市场日历时才能对应交易日期，不能将稀疏行号当作天数
- `transform` 保持原DataFrame形状，`apply` 可能改变形状

## 4. 横截面操作：每天对比所有股票

量化选股本质是"每天在所有股票中排名"。

```python
# 每天对收益率排名（从小到大，返回排名）
df['return_rank'] = df.groupby('date')['return'].rank()

# 每天计算百分位排名（0-1之间）
# pct=True 表示用名次除以当日有效数量，并不是上涨概率。
df['return_pct_rank'] = df.groupby('date')['return'].rank(pct=True)

# 每天标准化（减去均值，除以标准差）
# 对每个日期的小组执行同一段标准化计算。
df['return_zscore'] = df.groupby('date')['return'].transform(
    lambda x: (x - x.mean()) / x.std()
)

# 每天选出收益率最高的前10%
df['top_decile'] = df.groupby('date')['return'].transform(
    lambda x: x >= x.quantile(0.9)  # quantile(0.9) 求九成分位的数值，再逐行比较是否达到。
)
```

**时间序列 vs 横截面：**
- `groupby('code')` → 纵向（时间序列）：同一股票不同日期
- `groupby('date')` → 横向（横截面）：同一天不同股票

## 5. 合并数据：join和merge

真实项目中数据来自多张表，需要合并。

```python
# 假设有基本面数据
fundamental = pd.DataFrame({
    'code': ['000001', '000002'],
    'industry': ['银行', '房地产'],
    'market_cap': [500, 300]  # 亿元
})

# 左连接：保留df的所有行
df_merged = df.merge(fundamental, on='code', how='left')  # 按 code 对齐；how=left 保留左表的行，未匹配到的字段留空。

# 时间+股票双键连接
daily_basic = pd.DataFrame({
    'date': ['2024-01-01', '2024-01-01'],
    'code': ['000001', '000002'],
    'pe_ttm': [8.5, 12.3]
})
daily_basic['date'] = pd.to_datetime(daily_basic['date'])

df_full = df.merge(daily_basic, on=['date', 'code'], how='left')  # 股票和日期都相同才连接，避免把另一日的数据接进来。
```

**常见错误：**
- 忘记将日期转为datetime类型就merge，导致匹配失败
- 用`how='inner'`导致数据丢失却不知道

## 6. 缺失值处理

金融数据必然有缺失（停牌、新上市、数据源问题）。

```python
# 检查缺失
print(df.isnull().sum())  # isnull 标出缺失值；sum 按列统计缺失数量。

# 填充缺失（分组填充）
df['close_filled'] = df.groupby('code')['close'].ffill()  # 前向填充；仅在语义允许时使用

# 删除缺失
df_clean = df.dropna(subset=['close', 'volume'])  # 只删除 close 或 volume 缺失的行，其他列不参与这次筛选。

# 标记缺失
df['is_missing'] = df['close'].isnull()
```

**警告：** 在训练集上填充时，不能偷看测试集的值！应该只用训练期的统计量。

## 7. 向量化计算：避免循环

Python循环很慢，pandas操作是向量化的，快得多。

```python
# 慢：循环
returns = []  # 本段仅演示单只股票、已按日期排序的数据；股票面板需先分组。
# range 生成行位置，循环每次向后走一行。
for i in range(len(df)):
    if i == 0:
        returns.append(np.nan)  # 第一行没有上一行价格，用 NaN 表示缺失。
    else:
        ret = df.loc[i, 'close'] / df.loc[i-1, 'close'] - 1
        returns.append(ret)

# 快：向量化
df['return'] = df['close'].pct_change()

# 条件赋值：用np.where
df['signal'] = np.where(df['return'] > 0.05, 1, 0)  # np.where 按条件逐项选择：满足写 1，否则写 0。

# 多条件：用np.select
conditions = [
    df['return'] > 0.05,
    df['return'] < -0.05,
]
choices = ['强势', '弱势']
df['label'] = np.select(conditions, choices, default='中性')  # 按 conditions 的先后次序匹配，不满足时使用 default。
```

## 8. 实战练习：计算股票池

这是量化研究的第一步。

```python
# 假设股票池要求：
# 1. 上市超过250个交易日
# 2. 过去20日平均成交额 > 5000万
# 3. 当天不停牌

# 先计算上市天数
df['days_since_list'] = df.groupby('code').cumcount() + 1  # cumcount 数已有记录的行数；真实上市天数应另查上市日期和日历。

# 计算过去20日平均成交额（假设已有amount字段）
df['avg_amount_20d'] = df.groupby('code')['amount'].transform(
    lambda x: x.rolling(20, min_periods=20).mean()
)

# 标记股票池
# & 表示各个条件必须同时成立，每个比较都放在括号里。
df['in_universe'] = (
    (df['days_since_list'] >= 250) &
    (df['avg_amount_20d'] > 50_000_000) &
    (df['is_tradeable'] == True)
)

# 每天有多少只股票符合条件
universe_size = df[df['in_universe']].groupby('date').size()  # 先筛出合格行，再按日期数记录条数。
print(universe_size)
```

## 9. 常见陷阱

### 陷阱1：未排序就shift
```python
# 错误：数据乱序
df['prev'] = df['close'].shift(1)  # 可能拿到别的股票的值！

# 正确：先排序，再分组shift
df = df.sort_values(['code', 'date'])  # 先确保同一股票的日期由早到晚，之后才能安全取前一行。
df['prev'] = df.groupby('code')['close'].shift(1)
```

### 陷阱2：链式赋值警告
```python
# 可能出问题
df[df['code'] == '000001']['close'] = 999

# 推荐写法
df.loc[df['code'] == '000001', 'close'] = 999  # loc[行条件, 列名] 明确指定要修改原表的哪些单元格。
```

### 陷阱3：分组后索引混乱
```python
# groupby后索引可能不连续
grouped = df.groupby('code').apply(some_function)  # apply 把每组交给自定义函数 some_function，结果索引可能改变。
# 这里只重排行号，不能靠它修复已经发生的数据错位。
grouped = grouped.reset_index(drop=True)  # 重置索引
```

## 10. 下一步

完成以下练习后进入研究问题、数据时点与单因子章节：

1. 读取一份CSV股票数据，计算5日、10日、20日收益率
2. 计算每只股票的20日滚动波动率（收益率标准差）
3. 每天对所有股票按市值排名，标记市值最大的前100只
4. 合并两张表：日线价格表 + 每日指标表
5. 标记连续缺失行情，核对停牌或数据源原因，并报告标签覆盖；不能把已有持仓直接删除

**检验标准：** 能够写出"每天选出过去20日收益率前10%且成交额>1亿的股票"这类筛选逻辑。

---

## 11. 扩展模块：从“会调用函数”到“能检查结果”

前面的内容已经覆盖了常用语法，下面按“概念直觉 → 公式/规则 → 小例子或代码 → 常见错误 → 练习 → 答案框架”的顺序，把量化新手最容易混淆的部分串起来。示例中的字段和标签口径以当前项目的 `src/dataset.py`、`src/synthetic_data.py`、`src/duckdb_data.py` 为准。

### 11.1 一行金融数据到底表示什么

#### 概念直觉

量化研究最常见的面板表中，一行表示“某个 `trade_date`，某个 `code` 的一次日频观测”。可以把它想成很多条股票时间序列叠在一起：

```text
code=000001:  T1 → T2 → T3 → …
code=000002:  T1 → T2 → T3 → …
code=000003:  T1 → T2 → T3 → …
```

因此，`(code, trade_date)` 通常应该是业务唯一键。`groupby("code")` 是沿着一只股票的时间方向计算，`groupby("trade_date")` 是在同一天横向比较股票。

#### 公式与规则

当前项目的核心字段如下：

| 字段 | 含义和注意点 |
|---|---|
| `trade_date` | 交易日，应转为 pandas 日期类型；不是自然日计数 |
| `code` | 统一后的证券代码；原始 DuckDB 的 `ts_code` 会被映射为它 |
| `open/high/low/close` | 价格字段，当前真实示例来自 `adj_*` 复权字段 |
| `volume/amount` | 成交量和成交额，单位必须查数据字典，不能猜 |
| `market_cap` | 市值；当前特征使用 `log(max(market_cap, 1))` |
| `can_buy/can_sell` | 入场、退出成交资格 |
| `signal_eligible` | T 日是否在可用研究股票池内 |

当前教学标签的时间轴是：

```text
T 日收盘形成特征 → T+1 开盘入场 → T+5 收盘计划退出
```

理想计划收益的公式为：

\[
fwd\_return_T=\frac{scheduled\_exit\_price_T}{entry\_price_T}-1
\]

在实现中，`entry_date` 和 `scheduled_exit_date` 依据全市场交易日历生成，不是简单地把自然日加 1 或加 5。若计划退出不能成交，代码还会记录 `actual_exit_date` 和 `realized_return`；这两个字段不能混为一谈。

#### 小例子或代码

```python
import numpy as np
import pandas as pd

# 创建三只股票、三个日期的虚构行情表。
raw = pd.DataFrame(
    {
        "trade_date": [
            "2024-01-02", "2024-01-02", "2024-01-02",
            "2024-01-03", "2024-01-03", "2024-01-03",
            "2024-01-04", "2024-01-04", "2024-01-04",
        ],
        "code": ["000001", "000002", "000003"] * 3,
        "open": [10.0, 20.0, 8.0, 10.4, 19.7, 8.1, 10.2, 20.1, 8.0],
        "high": [10.2, 20.3, 8.2, 10.6, 20.0, 8.3, 10.4, 20.4, 8.2],
        "low": [9.9, 19.8, 7.9, 10.1, 19.5, 8.0, 10.0, 19.9, 7.8],
        "close": [10.2, 19.8, 8.1, 10.5, 19.9, 8.2, 10.1, 20.3, 8.0],
        "volume": [1000, 800, 1200, 1100, 900, 1300, 950, 1000, 1250],
        "amount": [10200, 15840, 9720, 11550, 17910, 10660, 9595, 20300, 10000],
        "market_cap": [5e9, 8e9, 3e9] * 3,
        "can_buy": [True] * 9,
        "can_sell": [True] * 9,
        "signal_eligible": [True] * 9,
    }
)

df = (
    # assign 新增或替换一列；这里把日期文字转成日期类型。
    raw.assign(trade_date=lambda x: pd.to_datetime(x["trade_date"]))
       .sort_values(["code", "trade_date"])
       .reset_index(drop=True)
)

print(df.head())  # head() 默认只看前五行，避免整张表输出太长。
print(df.dtypes)
print(df.duplicated(["code", "trade_date"]).sum())  # 以股票加日期识别重复记录，再数出重复数量。
```

这些数值只是教学数据；不能从几行样本推断真实市场规律，也不能把 `amount` 的单位当成已经确定。

#### 常见错误

- 一边的日期是字符串，另一边是 `Timestamp`，合并后指标全部为空。
- 把自然日 `2024-01-06` 当成交易日，或用 `Timedelta(days=5)` 代替 T+5 交易日。
- 同一 `(code, trade_date)` 有多行，却直接 `drop_duplicates`，没有查清重复来源。
- 使用 `ts_code`、`code`、`symbol` 混合命名，后续 `merge` 或分组时发生静默丢失。

#### 练习

对上面的 `df` 完成以下检查：

1. 列出所有重复的 `(code, trade_date)` 键。
2. 输出每列的缺失数量。
3. 检查每只股票是否按 `trade_date` 升序。

#### 答案框架

```python
keys = ["code", "trade_date"]
# keep=False 把同一重复组里的全部行都标出来，便于检查。
duplicates = df.loc[df.duplicated(keys, keep=False)].sort_values(keys)
missing = df.isna().sum().sort_values(ascending=False)  # 逐列数缺失，ascending=False 把缺得最多的放前面。
ordered = df.sort_values(keys)

assert not ordered.duplicated(keys).any()  # any() 问是否至少有一个重复；not 要求答案为否。
assert ordered["trade_date"].dtype == "datetime64[ns]"
```

如果 `duplicates` 非空，答案还应记录重复行的来源：重复下载、不同复权版本、同一日多条行情，还是日线和分钟线误合并。

### 11.2 NumPy：数组运算、广播和缺失值

#### 概念直觉

NumPy 的 `ndarray` 是同质数组，适合做数字运算；pandas 的 `Series` 和 `DataFrame` 在此基础上增加了索引、列名和自动对齐。量化代码常见的分工是：pandas 负责“这条数据属于哪只股票、哪一天”，NumPy 负责“这些数字如何快速变换”。

#### 公式与规则

单日收益：

\[
r_t=\frac{P_t}{P_{t-1}}-1
\]

样本波动率：

\[
s=\sqrt{\frac{1}{n-1}\sum_{i=1}^{n}(r_i-\bar r)^2}
\]

`np.std(x, ddof=1)` 与 pandas `Series.std()` 的默认口径一致；`ddof=0` 是另一种总体标准差口径，不能混用后不做说明。`np.nan` 会让普通的 `mean`、`std` 传播出 `NaN`，如果要忽略缺失，要显式使用 `np.nanmean`、`np.nanstd`。

#### 小例子或代码

```python
close = np.array([10.0, 10.5, 10.2])
returns = close[1:] / close[:-1] - 1  # [1:] 去掉第一项，[:-1] 去掉最后一项，让相邻价格一一对应。
print(returns)
print(np.mean(returns))
print(np.std(returns, ddof=1))  # ddof=1 使用样本标准差的分母约定。

market_cap = np.array([5e9, 8e9, 3e9])
log_market_cap = np.log(np.clip(market_cap, 1, None))  # clip 先把过小市值截到 1，再取自然对数。

signal = np.where(returns > 0.03, 1, 0)
# 按条件选对应文字；都不满足就用 default。
label = np.select(
    [returns > 0.03, returns < -0.03],
    ["上涨较多", "下跌较多"],
    default="其他",
)
```

广播可以避免逐行循环：

```python
prices = np.array([[10.0, 20.0], [10.5, 19.0], [10.2, 19.5]])  # 二维数组中，每行是一天，每列是一只股票。
first_day = prices[0]  # [0] 取第一行，也就是两只股票第一天的价格。
change_from_first = prices / first_day - 1  # NumPy 自动把第一行与每一行按列相除，算各自相对首日的涨幅。
print(change_from_first)
```

`prices` 的形状是 `(3, 2)`，`first_day` 的形状是 `(2,)`，NumPy 会把它沿行方向广播。广播前必须确认列顺序相同；两个数组形状相同，并不代表两个代码顺序一定相同。

#### 常见错误

- 用 `np.mean` 处理带 `NaN` 的收益数组，结果全为空；先决定缺失是忽略、保留还是剔除。
- 对非正市值直接 `np.log`，产生运行时警告；应先检查数据质量，必要时按项目规则 `clip`。
- 对两个没有相同代码顺序的数组做位置相除，得到数值但语义错位。
- 用 Python 循环计算本可向量化的收益，增加边界错误和性能开销。

#### 练习

1. 计算价格 `[10, 10.2, 10.1, 10.5]` 的收益数组。
2. 计算忽略缺失值的平均收益和样本标准差。
3. 将 `market_cap <= 0` 的记录标记成缺失，而不是把它们当成有效市值。

#### 答案框架

```python
prices = np.array([10.0, 10.2, 10.1, 10.5])
returns = prices[1:] / prices[:-1] - 1  # 两组切片对齐相邻价格，逐项相除得到单期收益。
mean_return = np.nanmean(returns)  # nanmean 求均值时跳过缺失；是否允许缺失需按研究规则决定。
std_return = np.nanstd(returns, ddof=1)

market_cap = np.array([5e9, 0, -1, np.nan])
valid = market_cap > 0
safe_cap = np.where(valid, market_cap, 1.0)  # 有效市值保留原数，无效位置先放 1，避免直接对零或负数取对数。
log_market_cap = np.where(valid, np.log(safe_cap), np.nan)  # 最后把原来无效的位置还原为缺失值。
```

这里的“安全值 1.0”只是避免 `log` 对无效数报警，最终仍把无效位置设回 `NaN`；它不是对异常市值的业务修复。

### 11.3 pandas 对齐、筛选和赋值

#### 概念直觉

pandas 不只是“带列名的二维数组”，它会按索引标签对齐。按标签对齐可以避免许多错位，但也意味着你必须理解索引。筛选出一个子表后，它可能是视图，也可能是副本；为了明确地修改结果，使用 `.loc[...]` 和 `.copy()`。

#### 公式与规则

- 单列：`df["close"]`；多列：`df[["close", "amount"]]`。
- 按条件选取和赋值：`df.loc[condition, column]`。
- 按位置选取：`df.iloc[row_position, column_position]`。
- Series 布尔条件使用 `&`、`|`、`~`，每个条件加括号；不能使用 `and`、`or`。
- `assign` 返回新表，适合链式计算；不要忘记接收返回值。

#### 小例子或代码

```python
# 行条件选股票，列列表选两列；copy 得到独立的小表。
one_stock = df.loc[df["code"] == "000001", ["trade_date", "close"]].copy()

df.loc[df["close"] > 20, "price_level"] = "高"
df.loc[df["close"] <= 20, "price_level"] = "低"

# 一次给表新增两列；replace(0, NaN) 避免直接除以零。
df = df.assign(
    close_open_return=df["close"] / df["open"].replace(0, np.nan) - 1,
    range_1d=(df["high"] - df["low"]) / df["close"].replace(0, np.nan),
)

# 三个布尔条件用 & 连接，全部为 True 才保留。
tradable = df.loc[
    df["can_buy"] & df["can_sell"] & df["signal_eligible"],
].copy()
```

#### 常见错误

```python
# 错误或有歧义：在筛选产生的临时对象上赋值
df[df["code"] == "000001"]["close"] = 999

# 正确：明确在原表的哪些行、哪一列赋值
df.loc[df["code"] == "000001", "close"] = 999  # 在原表中直接修改，避免“先切一张临时表再赋值”的歧义。
```

另一个常见错误是只调用排序而不保存结果：

```python
df.sort_values(["code", "trade_date"])  # df 没有改变
df = df.sort_values(["code", "trade_date"]).reset_index(drop=True)  # 把排序结果重新赋给 df，排序才会保留下来。
```

#### 练习

1. 选出 `amount > 10000` 且 `can_buy` 为真的样本。
2. 增加收盘相对开盘收益列，并避免开盘价为 0 时除零。
3. 找出 `close <= 0` 的行，按 `code` 统计样本数量。

#### 答案框架

```python
selected = df.loc[(df["amount"] > 10_000) & df["can_buy"]].copy()  # 括号内的两个条件逐行同时判断，copy 保存独立的筛选结果。
df["close_open_return"] = df["close"] / df["open"].replace(0, np.nan) - 1
bad_price = df.loc[df["close"] <= 0, ["code", "trade_date", "close"]]  # 找收盘价非正的行，只显示便于定位问题的三列。
counts = df.groupby("code").size().sort_values()  # 按股票统计行数，再从少到多排列。
```

### 11.4 时间序列：排序、shift 和交易日历

#### 概念直觉

时间序列计算首先要回答：“当前行的上一行是谁？”对面板数据，上一行必须是**同一只股票**的上一条观测。还要注意，证券市场有周末、节假日、停牌和新上市，单只股票的第 5 行不必然是全市场日历上的 T+5。

#### 公式与规则

当前实现使用：

```python
# 每只股票只和自己的前一行比较；fill_method=None 禁止先填缺失。
df["ret_1d"] = df.groupby("code")["close"].pct_change(fill_method=None)
```

`shift(1)` 是上一条同组观测，`shift(-5)` 是下一条同组观测。前者可构造滞后特征，后者可以帮助理解未来标签，但不能把未来值放入 T 日特征。

课程代码的理想标签不是 T 日收盘到 T+5 收盘，而是：

\[
fwd\_return_T=\frac{close_{T+5}}{open_{T+1}}-1
\]

`src/dataset.py` 通过交易日历生成 `entry_date` 和 `scheduled_exit_date`，然后合并对应价格。因此，用简化的 `shift(-5)` 讲解概念可以，但复现课程结果必须调用 `build_features_and_labels`。

#### 小例子或代码

```python
df["trade_date"] = pd.to_datetime(df["trade_date"], errors="raise")
df = df.sort_values(["code", "trade_date"]).reset_index(drop=True)

by_code = df.groupby("code", group_keys=False)  # 保存按股票分组的对象，后续重复使用它。
df["ret_1d"] = by_code["close"].pct_change(fill_method=None)
df["prev_close"] = by_code["close"].shift(1)
df["next_close_demo"] = by_code["close"].shift(-1)  # 负向 shift 取未来一行，只能做未来标签的示范。

# between 选择日期区间；默认包含两端。
period = df.loc[df["trade_date"].between("2024-01-02", "2024-01-04")].copy()
```

如果需要检查自然日和交易日的差异：

```python
one_stock = df.loc[df["code"] == "000001"].set_index("trade_date")  # 先取一只股票，再让日期成为索引，供时间重采样使用。
print(one_stock["close"].resample("D").last())  # resample("D") 按自然日取最后一个值，真实交易日仍需查市场日历。
```

`resample("D")` 会创建周末等自然日桶，适合观察日历频率，不适合直接替代交易日历。

#### 常见错误

- 未排序就计算 `shift` 或 `rolling`。
- 直接对整个 `df["close"]` 做 `shift`，上一行可能来自另一只股票。
- 用 `date + Timedelta(days=5)` 代替五个交易日。
- 把 `next_close_demo`、`fwd_return`、`label_rank` 留在模型特征列中。
- 只看计划退出价格，不检查 `can_buy`、`can_exit_on_schedule` 和 `actual_exit_date`。

#### 练习

1. 计算 `mom_3`：当前收盘相对同一股票 3 条观测之前的收益。
2. 写出当前课程 `entry_price`、`scheduled_exit_price` 和 `fwd_return` 的含义。
3. 说明为什么停牌会使“第 5 行”与“T+5 交易日”不同。

#### 答案框架

```python
# 按股票计算相隔三行的价格变化；要称三交易日需先对齐日历。
df["mom_3"] = df.groupby("code")["close"].pct_change(3, fill_method=None)

# 课程标签口径：
# entry_price = T+1 交易日的 open
# scheduled_exit_price = T+5 交易日的 close
# fwd_return = scheduled_exit_price / entry_price - 1
```

课程接口的最小检查示例：

```python
from src.synthetic_data import build_features_and_labels, make_synthetic_panel

# 生成四只虚构股票；seed 固定随机种子，方便重做相同练习。
panel = make_synthetic_panel(
    n_stocks=4, start="2024-01-02", end="2024-03-29", seed=42
)
# 生成特征和五日标签；min_history 指定最低历史记录要求。
sample = build_features_and_labels(panel, horizon=5, min_history=1)
print(sample[["trade_date", "code", "entry_date", "scheduled_exit_date", "fwd_return"]].head())
```

### 11.5 分组与窗口：时间序列特征的主力工具

#### 概念直觉

`groupby("code")` 把面板拆成多条独立的股票时间序列，再分别计算窗口；`groupby("trade_date")` 把同一天的股票放在一起做横截面排名。方向弄反，是量化初学者最常见的逻辑错误之一。

#### 公式与规则

当前代码中的特征公式为：

\[
\begin{aligned}
mom\_5 &= close_t/close_{t-5}-1 \\
mom\_20 &= close_t/close_{t-20}-1 \\
reversal\_3 &= -(close_t/close_{t-3}-1) \\
vol\_20 &= std(ret\_{1d,t-19:t}) \\
range\_1d &= (high_t-low_t)/close_t \\
amount\_chg\_5 &= amount_t/amount_{t-5}-1 \\
log\_mkt\_cap &= log(max(market\_cap,1))
\end{aligned}
\]

`rolling(20)` 是 20 条观测，不是自动识别的 20 个自然日；`min_periods=15` 表示至少需要 15 个有效值。`transform` 保持原表长度，`agg` 把每组压缩成一行，`apply` 更灵活但索引更难控制。

#### 小例子或代码

```python
df = df.sort_values(["code", "trade_date"]).reset_index(drop=True)
by_code = df.groupby("code", group_keys=False)  # 分组后再算各股票自己的历史变化。

df["ret_1d"] = by_code["close"].pct_change(fill_method=None)
df["mom_5"] = by_code["close"].pct_change(5, fill_method=None)
df["mom_20"] = by_code["close"].pct_change(20, fill_method=None)
df["reversal_3"] = -by_code["close"].pct_change(3, fill_method=None)  # 前面的负号把三期涨幅反过来，当作反转分数。
# 最近 20 行收益中，至少有 15 个有效值才计算标准差。
df["vol_20"] = (
    by_code["ret_1d"].rolling(20, min_periods=15).std()
    .reset_index(level=0, drop=True)  # 移除滚动结果多出的股票索引层，让它按原行标签对齐。
)
df["range_1d"] = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
df["amount_chg_5"] = by_code["amount"].pct_change(5, fill_method=None)  # 成交额与自己五行前相比，仍需检查前值是否为零。
df["log_mkt_cap"] = np.log(df["market_cap"].clip(lower=1))
```

分组汇总和原表回填：

```python
# agg 把每个日期压成一行，分别统计不同股票数和总成交额。
daily_summary = df.groupby("trade_date").agg(
    stock_count=("code", "nunique"),
    total_amount=("amount", "sum"),
)
# transform 把当日均值写回每只股票对应的原行。
df["daily_mean_amount"] = df.groupby("trade_date")["amount"].transform("mean")
# 把每天的一行汇总信息，按日期接回原来的多行明细。
df = df.merge(
    daily_summary["total_amount"],
    left_on="trade_date",
    right_index=True,
    how="left",
    validate="many_to_one",  # 要求右表每个日期至多一行，防止连接后行数意外膨胀。
)
```

#### 常见错误

- 在排序前做滚动计算，窗口顺序可能颠倒。
- `min_periods=1` 让窗口很早产生数字，却没有在报告中说明早期历史不足。
- `groupby().apply()` 返回多层索引，直接赋值回原表造成错位。
- 用 `agg` 结果当成和原表等长的列，或把 `transform` 误解成每组一行。

#### 练习

1. 为每只股票计算 `ret_1d` 的 5 条观测滚动标准差，至少需要 3 个有效值。
2. 统计每天的证券数量和成交额总和，并把总成交额回填原表。
3. 找出每只股票的最后一个交易日收盘价。

#### 答案框架

```python
# 分股票计算五行窗口，至少三个有效收益才算标准差。
df["vol_5_demo"] = (
    df.groupby("code")["ret_1d"]
      .rolling(5, min_periods=3)
      .std()
      .reset_index(level=0, drop=True)
)

# 每个日期汇总成一行；nunique 统计不同股票名字的数量。
daily = df.groupby("trade_date").agg(
    stock_count=("code", "nunique"),
    total_amount=("amount", "sum"),
)
df = df.merge(daily["total_amount"], left_on="trade_date", right_index=True, how="left")
last_rows = df.sort_values(["code", "trade_date"]).groupby("code").tail(1)  # 先按日期排好，再从每只股票中取最后一行。
```

### 11.6 横截面排名与标签

#### 概念直觉

动量、波动率等特征可以沿着一只股票的历史计算；选股排名则通常是“同一天哪只股票更高”。因此，排名必须按 `trade_date` 分组。训练标签也要在 T 日当时可用的股票池内计算，不能用当前成分股回填历史。

#### 公式与规则

`rank(pct=True)` 将组内排序缩放到 0 到 1 附近，并列值通常取平均排名。当前实现的标签为：

```python
eligible = df["signal_eligible"] & df["fwd_return"].notna()  # & 要求信号合格且未来收益已知，notna 表示不是缺失。
eligible_returns = df.loc[eligible, ["trade_date", "fwd_return"]]
# 同一日期的有效股票一起计算未来收益的名次占比。
label_rank = eligible_returns.groupby("trade_date")["fwd_return"].rank(pct=True)
# transform 让当日每条记录都附上同一个收益中位数。
daily_median = eligible_returns.groupby("trade_date")["fwd_return"].transform("median")
excess_return = eligible_returns["fwd_return"] - daily_median  # 每只股票的未来收益减去它所在日期的收益中位数。
```

这不是行业中性收益。当前真实数据示例中的历史行业快照不足以做多年严格行业中性，所以课程把 `excess_return` 定义为横截面中位数超额收益。

#### 小例子或代码

```python
df["return_pct_rank"] = df.groupby("trade_date")["ret_1d"].rank(pct=True)
# lambda 对每个日期单独计算，x 是该日的一组收益。
df["return_zscore"] = df.groupby("trade_date")["ret_1d"].transform(
    lambda x: (x - x.mean()) / x.std()
)

eligible = df["signal_eligible"] & df["fwd_return"].notna()
eligible_returns = df.loc[eligible, ["trade_date", "fwd_return"]]
daily_median = eligible_returns.groupby("trade_date")["fwd_return"].transform("median")
# 只给条件成立的行写入结果，其他行不动。
df.loc[eligible, "excess_return"] = eligible_returns["fwd_return"] - daily_median
df.loc[eligible, "label_rank"] = eligible_returns.groupby("trade_date")["fwd_return"].rank(pct=True)

# 预测值选 Top-N 时，给并列值一个确定的顺序
df["prediction_rank"] = df.groupby("trade_date")["prediction"].rank(
    ascending=False, method="first"  # 从高到低排；同分按当前行顺序区分，需先固定排序规则。
)
top_n = df.loc[df["prediction_rank"] <= 10]  # 只留下预测名次不大于 10 的行。
```

#### 常见错误

- 对全表直接 `rank()`，把不同日期的股票放在同一个横截面。
- 没有先按 `signal_eligible` 过滤就计算标签，使不可用证券影响排名。
- Top-N 边界出现并列，却没有定义 `method` 或稳定的代码排序规则。
- 把 `fwd_return` 和 `label_rank` 作为模型输入，造成明显前视。

#### 练习

1. 每天选出 `amount` 最大的前 2 只股票。
2. 计算每只股票相对当日中位数成交额的比例。
3. 解释为什么不同日期的 `label_rank` 可用数量和具体数值范围会变化。

#### 答案框架

```python
# 每个日期分别按成交额排名。
df["amount_rank"] = df.groupby("trade_date")["amount"].rank(
    ascending=False, method="first"
)
top_amount = df.loc[df["amount_rank"] <= 2].copy()  # 保留每天成交额排名前两名的记录。

median_amount = df.groupby("trade_date")["amount"].transform("median")
df["amount_vs_median"] = df["amount"] / median_amount.replace(0, np.nan)  # 成交额除以当日中位数，分母为零时先保留缺失。
```

### 11.7 合并、缺失值和数据质量

#### 概念直觉

合并的本质是按键匹配；缺失值的本质是“这里为什么没有观测”。二者都不能只看代码是否运行。连接前要知道右表键是否唯一，填充前要知道缺失是窗口不足、停牌、新股，还是数据源故障。

#### 公式与规则

合并关系要符合事实：

- 日线主表和每只股票的静态信息：通常是 `many_to_one`。
- 日线主表和每日指标：通常是 `(trade_date, code)` 上的 `one_to_one` 或 `many_to_one`。
- `left` 保留主表，`inner` 可能丢行；必须比较连接前后的行数。

缺失值处理的优先级是：先标记和统计，再根据原因选择保留、剔除或有限填充。当前 `src/dataset.py` 使用 `pct_change(fill_method=None)` 保留缺失；布尔成交资格缺失按不可用处理；最终删除仍缺失的特征行。不要把这套规则改写成“所有缺失填 0”。

#### 小例子或代码

```python
fundamental = pd.DataFrame(
    {
        "code": ["000001", "000002", "000003"],
        "industry": ["银行", "房地产", "制造"],
        "market_cap": [5e9, 8e9, 3e9],
    }
)
df = df.merge(fundamental, on="code", how="left", validate="many_to_one")  # 按股票连接，并检查右表每只股票至多一条。

daily_basic["trade_date"] = pd.to_datetime(daily_basic["trade_date"])
before = len(df)  # 连接前先记住行数，连接后再对照检查。
df = df.merge(
    daily_basic,
    on=["trade_date", "code"],
    how="left",
    validate="one_to_one",  # 要求连接键在左右两表都唯一。
)
assert len(df) == before

df["close_missing"] = df["close"].isna()  # 新增布尔列，记下哪些价格原本就是缺失。
# 仅用于展示：只在同一股票内向前填充，不能跨股票
df["close_ffill_demo"] = df.groupby("code")["close"].ffill()
```

训练期填充参数只能来自训练期：

```python
train = df.loc[df["trade_date"] < "2024-01-04"].copy()  # 按日期把较早的记录放进训练集。
test = df.loc[df["trade_date"] >= "2024-01-04"].copy()
train_median = train["mom_5"].median()  # 填充值只由训练集计算。
train["mom_5"] = train["mom_5"].fillna(train_median)
test["mom_5"] = test["mom_5"].fillna(train_median)  # 测试集沿用训练中位数，避免未来分布参与估计。
```

#### 常见错误

- 只用 `code` 合并每日指标，把别的日期的值复制过来。
- 右表有重复键导致合并后行数倍增，随后滚动和排名被重复样本污染。
- 用 `bfill` 把未来数据填到过去。
- 停牌期间前向填充价格，并把它当成可买或可卖价格。
- 在全量样本上计算填充值、均值或标准化参数，再切分训练测试。

#### 练习

1. 检查一张每日指标表的 `(trade_date, code)` 是否唯一，并在不唯一时让 `merge` 报错。
2. 统计每只股票的 `close` 缺失数，找出曾经缺失的股票。
3. 给 `amount` 增加缺失标记，再决定是剔除还是用训练期统计量填充。

#### 答案框架

```python
keys = ["trade_date", "code"]
assert not daily_basic.duplicated(keys).any()  # 连接前核对右表的日期加股票没有重复。
merged = df.merge(daily_basic, on=keys, how="left", validate="one_to_one")

# 按股票分别统计缺失价格数；lambda s 里的 s 是这一组价格。
missing_by_code = df.groupby("code")["close"].apply(lambda s: s.isna().sum())
codes_with_missing = missing_by_code[missing_by_code > 0].index  # 只取缺失数大于零的股票名字。
df["amount_missing"] = df["amount"].isna()
```

`mom_20` 的早期缺失通常是历史窗口尚未形成，不应简单当成收益为 0；答案需要说明 `min_history` 或 `dropna(subset=["mom_20"])` 的选择理由。

### 11.8 调试：先查形状、键、排序和时点

#### 概念直觉

量化数据最危险的错误往往不会抛异常：列名正确、计算完成，但行已经错配或未来信息已经进入特征。调试时先验证中间表的形状、键、日期范围、缺失分布和可得时点，再看最终收益或模型分数。

#### 规则

建议固定执行以下检查顺序：

1. `shape`：行数是否符合预期。
2. `head()`、`tail()`：日期和代码范围是否正确。
3. `dtypes`：日期、布尔和数值列类型是否正确。
4. `(code, trade_date)` 唯一性。
5. 每只股票的日期排序。
6. 非正价格、无穷成交额、异常市值。
7. 每列缺失率以及缺失集中在哪些日期或股票。
8. 特征时点不晚于 T，标签时点在 T 之后。

#### 小例子或代码

```python
# 定义检查函数；frame 是传入的表，类型标注帮助阅读。
def inspect_panel(frame: pd.DataFrame) -> None:
    required = {"trade_date", "code", "close", "amount"}
    missing_columns = sorted(required - set(frame.columns))  # 集合相减，找出必需列中哪些没有出现在表里。
    if missing_columns:
        raise ValueError(f"缺少字段: {missing_columns}")

    print("shape:", frame.shape)  # shape 是行数和列数组成的一对数字。
    print("date range:", frame["trade_date"].min(), "to", frame["trade_date"].max())
    print("code count:", frame["code"].nunique())
    print("missing:")
    print(frame.isna().sum().sort_values(ascending=False).head())

    duplicate_count = frame.duplicated(["code", "trade_date"]).sum()  # 用股票加日期识别重复，再累计它们的数量。
    if duplicate_count:
        raise ValueError(f"存在 {duplicate_count} 行重复键")
    if (frame["close"] <= 0).any():
        raise ValueError("发现非正收盘价")
    # dropna 先排除缺失；再检查剩下的成交额有没有无穷值。
    if not np.isfinite(frame["amount"].dropna()).all():
        raise ValueError("成交额存在无穷值")

inspect_panel(df)
```

合并和滚动都应保留中间检查：

```python
before = len(df)
joined = df.merge(daily_basic, on=["trade_date", "code"], how="left")
print({"before": before, "after": len(joined)})  # 用一个小字典并排显示连接前后的行数。

single = (
    # 只抽一只股票的几个关键字段，方便按日期追踪。
    joined.loc[joined["code"] == "000001", ["trade_date", "close", "ret_1d", "mom_5"]]
    .sort_values("trade_date")
)
print(single.head(10))
```

#### 常见错误

| 现象 | 可能原因 | 首先检查 |
|---|---|---|
| `KeyError: close` | 字段名或层级不一致 | `df.columns.tolist()` |
| 合并后行数暴增 | 右表键重复 | `duplicated(keys).sum()` |
| 所有滚动值为空 | 窗口太长、有效值不足或排序错 | 单只股票前 25 行 |
| `SettingWithCopyWarning` | 在临时筛选结果上赋值 | `.loc[...] .copy()` |
| Series 条件报错 | 使用 `and/or` | 改成带括号的 `&/|` |
| 结果异常好 | 未来标签、全样本标准化或当前成分股回填 | 检查字段时点和切分边界 |

#### 练习

找出下面代码的至少四个问题，并改写：

```python
subset = df[df["code"] == "000001"]  # 下面是错误对照：筛选后赋值、跨股票 shift 等写法需分别修正。
subset["ret"] = subset["close"].pct_change()
df["prev"] = df["close"].shift(1)  # 未按股票分组，可能把另一只股票的价格当作前值。
df["selected"] = (df["amount"] > 10000) and (df["close"] > 10)  # Python 的 and 不能逐行组合两列条件，表格条件要用 &。
joined = df.merge(daily_basic, on="code", how="inner")  # 只按股票连接会把不同日期混在一起，可能造成多对多膨胀。
```

#### 答案框架

```python
subset = df.loc[df["code"] == "000001"].copy()  # 显式复制筛选结果，后续修改的是这张独立小表。
subset = subset.sort_values("trade_date")
subset["ret"] = subset["close"].pct_change(fill_method=None)

df = df.sort_values(["code", "trade_date"]).reset_index(drop=True)
df["prev"] = df.groupby("code")["close"].shift(1)
df["selected"] = (df["amount"] > 10000) & (df["close"] > 10)  # & 按行合并条件，每项比较分别加括号。

joined = df.merge(
    daily_basic,
    on=["trade_date", "code"],  # 日期和股票两项都相同才匹配。
    how="left",
    validate="one_to_one",
)
```

完整答案还应说明：`subset` 需要副本、收益需要按日期排序、`prev` 需要按股票分组、Series 条件要用 `&`，每日指标不能只用 `code` 合并。

## 12. 综合练习与答案框架

这些练习只要求正确处理数据，不要求给出投资建议或收益结论。

### 练习一：复现课程特征

给定包含 `trade_date`、`code`、`high`、`low`、`close`、`amount`、`market_cap` 的面板，构造课程的 7 个特征，并报告删除缺失特征行前后的样本数。

**答案框架：**

```python
df["trade_date"] = pd.to_datetime(df["trade_date"], errors="raise")
df = df.sort_values(["code", "trade_date"]).reset_index(drop=True)
by_code = df.groupby("code", group_keys=False)  # 把每只股票各自的时间序列分开处理。
df["ret_1d"] = by_code["close"].pct_change(fill_method=None)
df["mom_5"] = by_code["close"].pct_change(5, fill_method=None)
df["mom_20"] = by_code["close"].pct_change(20, fill_method=None)
df["reversal_3"] = -by_code["close"].pct_change(3, fill_method=None)  # 对三期收益取负号，让下跌较多的股票反转分数更高。
# 滚动标准差按股票计算，结果稍后按原行标签对齐。
df["vol_20"] = (
    by_code["ret_1d"].rolling(20, min_periods=15).std()
    .reset_index(level=0, drop=True)
)
df["range_1d"] = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
df["amount_chg_5"] = by_code["amount"].pct_change(5, fill_method=None)
df["log_mkt_cap"] = np.log(df["market_cap"].clip(lower=1))

# 把后面必须具备的特征列名放到一个列表里。
features = [
    "mom_5", "mom_20", "reversal_3",
    "vol_20", "range_1d", "amount_chg_5", "log_mkt_cap",
]
before = len(df)
df = df.dropna(subset=features).copy()  # 删除特征不齐的行后记录前后数量，明确样本少了多少。
print({"before": before, "after": len(df)})
```

### 练习二：每天按成交额选 Top-N

只保留 `signal_eligible` 的样本，每天按 `amount` 选前 2 只，并定义并列处理规则。

**答案框架：**

```python
eligible = df.loc[df["signal_eligible"]].copy()  # 先筛出当时有信号资格的记录，独立保存。
eligible["amount_rank"] = eligible.groupby("trade_date")["amount"].rank(
    ascending=False, method="first"
)
top_2 = eligible.loc[eligible["amount_rank"] <= 2].copy()  # 每个日期保留成交额名次前两名。
```

### 练习三：构造并检查标签

使用当前项目接口生成 `fwd_return` 和 `label_rank`，检查 `label_rank` 只在有未来收益的样本上出现，并手算一行标签。

**答案框架：**

```python
from src.synthetic_data import build_features_and_labels, make_synthetic_panel

panel = make_synthetic_panel(
    n_stocks=5, start="2024-01-02", end="2024-06-28", seed=42
)
sample = build_features_and_labels(panel, horizon=5, min_history=20)

assert sample.loc[sample["fwd_return"].isna(), "label_rank"].isna().all()  # 未来收益缺失的行，其排名标签也应该缺失。
# 先去掉缺少两个价格端点的行，再取第一条做手算。
one = sample.dropna(subset=["entry_price", "scheduled_exit_price"]).iloc[0]
manual = one["scheduled_exit_price"] / one["entry_price"] - 1
assert np.isclose(manual, one["fwd_return"])  # 用浮点近似比较，检查手算收益是否与生成的标签一致。
```

注意：`min_history=20` 只控制最少历史观测，特征本身仍可能因为窗口和停牌产生缺失；`fwd_return` 是计划退出口径，`realized_return` 还要考虑实际成交资格。

### 练习四：最小数据审计报告

输出日期范围、证券数量、重复键、非正收盘价、各特征缺失率和标签可用率。

**答案框架：**

```python
features = [
    "mom_5", "mom_20", "reversal_3",
    "vol_20", "range_1d", "amount_chg_5", "log_mkt_cap",
]
# 用字典收集一份数据概况，字段名对应检查项目。
report = {
    "date_min": str(sample["trade_date"].min()),
    "date_max": str(sample["trade_date"].max()),
    "codes": int(sample["code"].nunique()),
    "duplicate_keys": int(sample.duplicated(["code", "trade_date"]).sum()),
    "non_positive_close": int((sample["close"] <= 0).sum()),
    # notna 得到是否有标签，求均值就是有标签样本的比例。
    "label_available_rate": float(sample["fwd_return"].notna().mean()),
}
print(report)
print(sample[features].isna().mean().sort_values(ascending=False))  # 逐个特征统计缺失比例，并把最高的排在前面。
```

### 自检清单

- [ ] 能解释 `DataFrame`、`Series` 和 NumPy `ndarray` 的区别。
- [ ] 能把日期转成 `datetime`，并按 `code, trade_date` 排序。
- [ ] 能使用 `groupby("code")` 计算收益、动量和滚动波动率。
- [ ] 能使用 `groupby("trade_date")` 做横截面排名。
- [ ] 理解 `shift(1)`、未来标签和全市场交易日历的区别。
- [ ] 能在 `merge` 前检查键唯一性，并解释行数变化。
- [ ] 能区分窗口不足、停牌、标签不可得和数据源故障造成的缺失。
- [ ] 能用 `.loc`、`&`、括号和 `.copy()` 避免常见 pandas 错误。
- [ ] 能写出形状、重复键、日期范围、数值范围和缺失率检查。
- [ ] 清楚当前 `fwd_return` 是 T+1 开盘到 T+5 收盘，`label_rank` 是 T 日可用股票池内的直接收益百分位排名。

本章供遇到 pandas 和 NumPy 语法问题时查阅。正式阅读请从[阅读指南](00_学习路线.md)开始，五编主线和完整顺序见[教材目录](README.md)。
