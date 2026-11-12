#!/usr/bin/env python3
"""An educational, *non-trading* historical price-pair inspection.

Uses only the book's locally saved actual A-share daily OHLC CSVs.
The standard mode needs no third-party packages. --test additionally needs
statsmodels and displays exploratory Engle-Granger/ADF results. This is NOT
a calibrated trading strategy or a claim that either stock pair is cointegrated.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from math import isfinite, sqrt
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "300750": "宁德时代",
    "002594": "比亚迪",
}
TRAIN_DAYS = 80
EXPECTED_DAYS = 117


def read_close(symbol: str, root: Path = ROOT) -> dict[str, float]:
    path = root / "data" / "real_a_share" / f"{symbol}.csv"
    values: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            day = row["trade_date"]
            close = float(row["close"])
            if day in values or not isfinite(close) or close <= 0:
                raise ValueError(f"Invalid/duplicate close: {symbol}, {day}")
            values[day] = close
    return values


def paired_closes(root: Path = ROOT) -> list[tuple[str, float, float]]:
    """Each row is (date, CATL close, BYD close) at a COMMON trading date."""
    catl = read_close("300750", root)
    byd = read_close("002594", root)
    dates = sorted(set(catl) & set(byd))
    if len(dates) != EXPECTED_DAYS:
        raise ValueError(f"Expected {EXPECTED_DAYS} common trading days; got {len(dates)}")
    return [(day, catl[day], byd[day]) for day in dates]


def mean(values: list[float]) -> float:
    if not values:
        raise ValueError("Need at least one observation")
    return sum(values) / len(values)


def sample_sd(values: list[float]) -> float:
    if len(values) <= 1:
        raise ValueError("Need at least two observations")
    m = mean(values)
    return sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def correlation(x: list[float], y: list[float]) -> float:
    """Pearson correlation of two equal-length numerical samples."""
    if len(x) != len(y) or len(x) < 3:
        raise ValueError("Correlation samples must be equal in length (>=3)")
    mx, my = mean(x), mean(y)
    numerator = sum((a - mx) * (b - my) for a, b in zip(x, y))
    denom = sqrt(
        sum((a - mx) ** 2 for a in x) *
        sum((b - my) ** 2 for b in y)
    )
    if denom == 0:
        raise ValueError("Cannot correlate constant series")
    return numerator / denom


@dataclass(frozen=True)
class FittedRelationship:
    intercept: float
    beta: float
    spread_mean: float
    spread_sd: float
    return_corr: float
    train_end: str
    future_start: str


def fit_training(rows: list[tuple[str, float, float]]) -> FittedRelationship:
    if len(rows) <= TRAIN_DAYS:
        raise ValueError("Need a subsequent observation period")
    # Estimate relationship ONLY with first 80 days, never refit on holdout.
    training = rows[:TRAIN_DAYS]
    y = [r[1] for r in training]  # CATL stock price
    x = [r[2] for r in training]  # BYD stock price
    mx, my = mean(x), mean(y)
    denom = sum((v - mx) ** 2 for v in x)
    if denom == 0:
        raise ValueError("Cannot fit regression on constant stock prices")
    beta = sum((a - mx) * (b - my) for a, b in zip(x, y)) / denom
    alpha = my - beta * mx
    spreads = [stock - alpha - beta * other for _, stock, other in training]
    spread_sd = sample_sd(spreads)
    if spread_sd == 0:
        raise ValueError("Zero training spread dispersion")
    returns_y = [y[i] / y[i - 1] - 1 for i in range(1, len(y))]
    returns_x = [x[i] / x[i - 1] - 1 for i in range(1, len(x))]
    return FittedRelationship(
        intercept=alpha,
        beta=beta,
        spread_mean=mean(spreads),
        spread_sd=spread_sd,
        return_corr=correlation(returns_y, returns_x),
        train_end=rows[TRAIN_DAYS - 1][0],
        future_start=rows[TRAIN_DAYS][0],
    )


def spread_z(row: tuple[str, float, float], model: FittedRelationship) -> float:
    _, catl_close, byd_close = row
    spread = catl_close - model.intercept - model.beta * byd_close
    return (spread - model.spread_mean) / model.spread_sd


def describe(rows: list[tuple[str, float, float]], model: FittedRelationship) -> str:
    lines = [
        "真实 A 股历史日线｜协整与配对交易的入门观察（不代表检验通过）",
        "股票：宁德时代（300750）、比亚迪（002594）",
        f"日期：{rows[0][0]} 至 {rows[-1][0]}，共 {len(rows)} 个对齐交易日",
        f"前 {TRAIN_DAYS} 日建立参考关系：{rows[0][0]} 至 {model.train_end}",
        f"后 {len(rows) - TRAIN_DAYS} 日独立观察：{model.future_start} 至 {rows[-1][0]}",
        f"训练期日收益相关系数（只衡量同涨同跌）：{model.return_corr:+.3f}",
        f"训练期价格线性参考：宁德时代 ≈ {model.intercept:+.3f} + {model.beta:.3f} × 比亚迪",
        f"训练期价差标准差：{model.spread_sd:.3f} 元",
        "",
        "实际历史收盘价与相对训练期的偏离（Z）：",
    ]
    for index in [0, TRAIN_DAYS - 1, TRAIN_DAYS, len(rows) - 1]:
        day, catl, byd = rows[index]
        lines.append(
            f"{day}：宁德时代 {catl:.2f} 元，比亚迪 {byd:.2f} 元，"
            f"Z={spread_z(rows[index], model):+.2f}"
        )
    lines.extend([
        "",
        "这只是用训练期确定的价格关系来观察后续偏离。",
        "相关系数不等于协整；大幅偏离也可能是长期关系已经改变，不能当作必然回归的买卖信号。",
        "价格为不复权日线，未核实分红送转与真实融券成交，因此没有计算套利收益。",
    ])
    return "\n".join(lines)


def exploratory_tests(rows: list[tuple[str, float, float]]) -> str:
    try:
        from statsmodels.tsa.stattools import adfuller, coint
    except ImportError as error:
        raise RuntimeError(
            "可选统计检验需要额外安装 statsmodels；不安装也能运行前面的真实价格练习。"
        ) from error

    training = rows[:TRAIN_DAYS]
    y = [r[1] for r in training]
    x = [r[2] for r in training]
    lines = [
        "\n选读｜仅使用前80天，做探索性单位根与 Engle–Granger 检验",
        "ADF 原假设是存在单位根；协整检验的原假设是“不协整”。",
    ]
    for label, prices in (("宁德时代", y), ("比亚迪", x)):
        levels = adfuller(prices, autolag="AIC")
        differences = adfuller(
            [prices[i] - prices[i - 1] for i in range(1, len(prices))],
            autolag="AIC",
        )
        lines.append(
            f"{label}：价格序列 ADF p≈{levels[1]:.4f}；"
            f"一阶差分 ADF p≈{differences[1]:.4f}"
        )
    statistic, pvalue, _ = coint(y, x, trend="c", autolag="aic")
    lines.append(f"Engle–Granger 的训练期统计量 {statistic:.3f}，p≈{pvalue:.4f}")
    lines.append(
        "p 值不能单独证明价格关系稳定、会回归或可以交易。"
        "先检查序列阶数、公司行为、样本长度、结构变化和多重选对偏差。"
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test", action="store_true",
        help="额外运行探索性 ADF/Engle–Granger 检验（需要 statsmodels）",
    )
    args = parser.parse_args()
    rows = paired_closes()
    model = fit_training(rows)
    print(describe(rows, model))
    if args.test:
        print(exploratory_tests(rows))


if __name__ == "__main__":
    main()
