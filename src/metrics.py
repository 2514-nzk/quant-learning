"""预测和组合评价指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rank_ic(predictions: pd.DataFrame, pred_col: str = "prediction", label_col: str = "label_rank") -> pd.Series:
    usable = predictions.dropna(subset=[pred_col, label_col])
    return usable.groupby("trade_date")[[pred_col, label_col]].apply(
        lambda x: x[pred_col].corr(x[label_col], method="spearman")
        if x[pred_col].nunique() > 1 and x[label_col].nunique() > 1
        else np.nan
    ).dropna().rename("rank_ic")


def grouped_returns(predictions: pd.DataFrame, n_groups: int = 5) -> pd.DataFrame:
    rows = []
    for date, group in predictions.groupby("trade_date"):
        group = group.dropna(subset=["prediction", "fwd_return"])
        if len(group) < n_groups:
            continue
        rank = group["prediction"].rank(method="first")
        group = group.assign(group=((rank - 1) * n_groups / len(group)).astype(int).clip(0, n_groups - 1))
        means = group.groupby("group")["fwd_return"].mean()
        rows.extend({"trade_date": date, "group": int(bucket), "fwd_return": float(value)} for bucket, value in means.items())
    return pd.DataFrame(rows)


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float((equity / peak - 1).min())


def summarize_backtest(bt: pd.DataFrame) -> dict[str, float]:
    if bt.empty:
        return {}
    daily = bt["net_return"]
    equity = (1 + daily.fillna(0)).cumprod()
    benchmark_equity = (1 + bt["benchmark_return"].fillna(0)).cumprod()
    active = bt["active_return"]
    period_days = float(bt["period_days"].median()) if "period_days" in bt else 1.0
    ann = 252 / period_days
    sharpe = float(np.sqrt(ann) * daily.mean() / daily.std()) if daily.std() else 0.0
    active_sharpe = float(np.sqrt(ann) * active.mean() / active.std()) if active.std() else 0.0
    return {
        "total_return": float(equity.iloc[-1] - 1),
        "benchmark_total_return": float(benchmark_equity.iloc[-1] - 1),
        "excess_total_return": float(equity.iloc[-1] / benchmark_equity.iloc[-1] - 1),
        "annualized_return": float(equity.iloc[-1] ** (ann / max(len(equity), 1)) - 1),
        "sharpe": sharpe,
        "active_sharpe": active_sharpe,
        "max_drawdown": max_drawdown(equity),
        "avg_turnover": float(bt["turnover"].mean()),
        "avg_cost": float(bt["cost"].mean()),
        "delayed_exit_rate": float(bt["n_delayed_exits"].sum() / bt["n_holdings"].sum())
        if "n_delayed_exits" in bt and bt["n_holdings"].sum()
        else 0.0,
    }


def yearly_backtest_summary(bt: pd.DataFrame) -> list[dict[str, float | int]]:
    if bt.empty:
        return []
    frame = bt.copy()
    frame["year"] = pd.to_datetime(frame["trade_date"]).dt.year
    rows = []
    for year, group in frame.groupby("year"):
        summary = summarize_backtest(group)
        rows.append({"year": int(year), **summary})
    return rows
