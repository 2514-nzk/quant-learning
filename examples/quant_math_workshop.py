"""量化数学小实验：收益、回撤、组合、相关、回归和不确定性。

运行 python examples/quant_math_workshop.py。仅输出教学计算，不读写数据文件。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# 这个函数输入一串收益，返回净值与回撤两串结果。
def wealth_and_drawdown(returns: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(returns, dtype=float)  # 转成小数数组，方便逐项计算和检查。
    if values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("收益必须是非空、有限的一维数组，缺失不能自动补零")
    if (values < -1).any():
        raise ValueError("本无杠杆教学净值不接受低于 -100% 的单期收益")
    wealth = np.r_[1.0, np.cumprod(1 + values)]  # cumprod 连乘各期的 1+收益；最前面补初始净值 1。
    # maximum.accumulate 记录历史最高净值，再算当前离高点跌了多少。
    drawdown = wealth / np.maximum.accumulate(wealth) - 1
    return wealth, drawdown


def rank_ic(factor: np.ndarray, future_return: np.ndarray) -> float:
    # 把因子和未来收益并排成表，让它们按样本一一对应。
    paired = pd.DataFrame({"factor": factor, "future_return": future_return})
    paired = paired.replace([np.inf, -np.inf], np.nan).dropna()  # 无穷值转成缺失，再删去不能成对评价的行。
    if len(paired) < 3 or (paired.nunique() < 2).any():
        return float("nan")
    # 两列先排名，再比较名次的相关性；float 转成普通小数。
    return float(paired["factor"].rank().corr(paired["future_return"].rank()))


def moving_block_mean_interval(
    values: np.ndarray, block_length: int = 10, repeats: int = 2000, seed: int = 123,
) -> np.ndarray:
    """重采样连续时间块的均值区间；示范依赖性，不替代完整显著性检验。"""
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all() or not 1 <= block_length <= len(x):
        raise ValueError("输入或时间块长度无效")
    if repeats < 2:
        raise ValueError("重采样次数至少为 2")
    rng = np.random.default_rng(seed)  # 创建固定种子的随机数工具，方便重复相同抽样。
    blocks_needed = int(np.ceil(len(x) / block_length))  # 向上取整，算出至少要抽多少个时间块才能凑够原来的长度。
    means = np.empty(repeats)  # 预留一个数组，后面逐次填入每次重采样得到的均值。
    # 重复抽样，每次结果放到第 i 个位置。
    for i in range(repeats):
        # 随机挑各个连续块的起点，同一个起点可以重复抽中。
        starts = rng.integers(0, len(x) - block_length + 1, size=blocks_needed)
        # 把各块接起来，再截取到原序列长度。
        resampled = np.concatenate([x[start:start + block_length] for start in starts])[:len(x)]
        means[i] = resampled.mean()
    return np.quantile(means, [0.025, 0.975])  # 取重复均值的 2.5% 和 97.5% 分位值，作为区间两端。


def main() -> None:
    returns = np.array([0.10, -0.10])
    wealth, drawdown = wealth_and_drawdown(returns)  # 同时接收函数返回的净值和回撤。
    assert np.isclose(wealth[-1] - 1, -0.01)  # 把计算出的累计收益与手算 -1% 作近似比较。
    assert np.isclose(drawdown.min(), -0.10)
    _, first_loss_drawdown = wealth_and_drawdown(np.array([-0.10, 0.05]))  # 下划线表示这里不使用第一个返回值，只看回撤。
    assert np.isclose(first_loss_drawdown.min(), -0.10)
    try:
        wealth_and_drawdown(np.array([0.01, np.nan]))
    except ValueError:
        pass
    else:
        raise AssertionError("收益缺失应先核查，不能自动当作零")
    print("1. 复利与回撤")
    print(f"算术平均={returns.mean():.2%}，累计收益={wealth[-1]-1:.2%}，最大回撤={drawdown.min():.2%}")
    print("初始净值包含在序列内：", wealth)

    x = np.array([1., 2., 3., 4., 100.])
    median = np.median(x)
    mad = np.median(abs(x - median))  # 每个数先减中位数、取绝对值，再求一次中位数。
    upper = median + 3 * 1.4826 * mad
    assert np.isclose(upper, 7.4478)
    sample_values = np.array([0.01, -0.01, 0.02, 0.00])
    sample_std = sample_values.std(ddof=1)  # ddof=1 使用样本标准差的计算约定。
    assert np.isclose(sample_std, np.sqrt(0.0005 / 3))
    print("\n2. 分布与离群点")
    print(f"均值={x.mean():.1f}，中位数={median:.1f}，MAD 上界={upper:.4f}")
    print(f"[1%,-1%,2%,0%] 的样本标准差={sample_std:.4%}")

    factor = np.array([1., 2., 3., 4.])
    future = np.array([0.01, 0.03, 0.02, 0.04])
    ic = rank_ic(factor, future)  # 把四个因子值和各自未来收益配对，检查排序一致性。
    assert np.isclose(ic, 0.8)
    assert np.isnan(rank_ic(np.ones(4), future))
    assert np.isclose(rank_ic(np.array([1., 2., 2., 4.]), future), np.sqrt(0.9))
    print("\n3. 排序关系")
    print(f"四股票 RankIC={ic:.3f}；常数因子的 RankIC 无定义。")

    weights = np.array([0.5, 0.5])
    sigma = np.array([0.02, 0.03])
    corr = np.array([[1., 0.2], [0.2, 1.]])
    covariance = np.outer(sigma, sigma) * corr  # outer 把两两波动率相乘，再乘对应相关性，得到协方差矩阵。
    portfolio_std = np.sqrt(weights @ covariance @ weights)  # @ 做矩阵乘法，先算组合方差再开平方，得到组合波动。
    assert np.isclose(portfolio_std**2, 0.000385)
    print("\n4. 组合风险")
    print(f"等权组合日波动={portfolio_std:.4%}，不是两只股票波动率的简单平均。")

    exposure = np.array([-2., -1., 0., 1., 2.])
    noise = np.array([0.001, -0.002, 0.002, -0.002, 0.001])
    response = 0.01 + 0.02 * exposure + noise
    design = np.column_stack([np.ones(len(exposure)), exposure])  # 并排放一列全 1 和输入数据，分别用于估计截距和斜率。
    # 接收最小二乘的返回值，下划线项本次不用。
    coefficients, _, matrix_rank, _ = np.linalg.lstsq(design, response, rcond=None)
    residual = response - design @ coefficients  # 答案减去模型给出的预测，剩下的差值叫残差。
    assert matrix_rank == 2
    assert np.allclose(coefficients, [0.01, 0.02])
    assert np.allclose(design.T @ residual, 0, atol=1e-12)
    print("\n5. 最小二乘")
    print(f"截距={coefficients[0]:.3f}，斜率={coefficients[1]:.3f}，残差={residual}")

    mean_return, std_return, periods_per_year = 0.003, 0.01, 252/5
    sharpe = np.sqrt(periods_per_year) * mean_return / std_return  # 用一年对应多少期作年化换算；这里每期为非重叠五日。
    assert np.isclose(sharpe, 2.1297887219)
    print("\n6. 单位与评价周期")
    print(f"等长非重叠 5 日收益，假设无风险收益为零，近似年化 Sharpe={sharpe:.4f}")
    print(f"20 个相互独立的无效检验各以 5% 假阳性率筛选，至少一次假阳性概率={1-0.95**20:.2%}")

    rng = np.random.default_rng(42)
    innovations = rng.normal(0, 0.03, size=120)  # 生成虚构的随机扰动，用来演示前后相关的时间序列。
    serial = np.empty(120)
    serial[0] = 0.01 + innovations[0]
    # 从第二项开始，让当前值也受到上一期的影响。
    for i in range(1, len(serial)):
        serial[i] = 0.01 + 0.65 * (serial[i-1] - 0.01) + innovations[i]
    naive_se = serial.std(ddof=1) / np.sqrt(len(serial))  # 这个均值标准误是假定各期独立时的近似，用来与时间块方法对照。
    interval = moving_block_mean_interval(serial)  # 调用上面的连续时间块重采样函数，得到均值区间。
    assert interval.shape == (2,) and np.isfinite(interval).all() and interval[0] <= interval[1]
    print("\n7. 均值的不确定性（合成自相关序列，不是市场结果）")
    print(f"均值={serial.mean():.4f}，假定独立的 SE={naive_se:.4f}")
    print(f"长度 10 的移动时间块重采样，均值 95% 百分位区间={interval.round(4)}")
    print("时间块长度、平稳性和多重检验仍需另行审计，不能仅凭该区间判定策略有效。")
    print("\n手算与边界核对全部通过。")


# 只有直接运行这个文件，才执行下面的完整教学流程。
if __name__ == "__main__":
    main()
