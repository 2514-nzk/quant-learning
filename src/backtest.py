"""把样本外预测转为一个透明的 Top-N 教学组合。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def top_n_backtest(
    predictions: pd.DataFrame,
    top_n: int = 10,
    holding_days: int = 5,
    cost_bps: float = 8,
) -> pd.DataFrame:
    df = predictions.sort_values(["trade_date", "code"]).copy()
    dates = list(df["trade_date"].drop_duplicates())
    previous: set[str] = set()
    rows: list[dict] = []
    previous_exit_date = pd.NaT
    for i, date in enumerate(dates):
        if i % holding_days != 0:
            continue
        day = df[df["trade_date"] == date]
        if "can_enter" in day:
            day = day[day["can_enter"].fillna(False)]
        if day.empty:
            continue
        entry_date = day["entry_date"].dropna().min() if "entry_date" in day else date
        if pd.notna(previous_exit_date) and pd.notna(entry_date) and entry_date <= previous_exit_date:
            continue

        selected = day.nlargest(min(top_n, len(day)), "prediction").copy()
        held = set(selected["code"])
        if not held:
            continue
        return_col = "realized_return" if "realized_return" in selected else "fwd_return"
        realized = selected[return_col].dropna()
        if realized.empty:
            continue
        gross = float(realized.mean()) if len(realized) else 0.0
        benchmark = float(day["fwd_return"].mean()) if day["fwd_return"].notna().any() else 0.0
        buys = len(held - previous)
        sells = len(previous - held)
        traded_fraction = (buys + sells) / max(len(held), 1) if previous else 1.0
        cost = traded_fraction * cost_bps / 10000
        net = gross - cost
        actual_exit = selected["actual_exit_date"].max() if "actual_exit_date" in selected else pd.NaT
        scheduled_exit = selected["scheduled_exit_date"].max() if "scheduled_exit_date" in selected else pd.NaT
        delayed = int((selected.get("exit_delay_days", pd.Series(dtype=float)).fillna(0) > 0).sum())
        rows.append(
            {
                "trade_date": date,
                "entry_date": entry_date,
                "scheduled_exit_date": scheduled_exit,
                "actual_exit_date": actual_exit,
                "period_days": holding_days,
                "gross_return": gross,
                "benchmark_return": benchmark,
                "turnover": traded_fraction,
                "cost": cost,
                "net_return": net,
                "active_return": net - benchmark,
                "n_holdings": len(held),
                "n_realized": int(len(realized)),
                "n_delayed_exits": delayed,
            }
        )
        previous = held
        if pd.notna(actual_exit):
            previous_exit_date = actual_exit
    result = pd.DataFrame(rows)
    if not result.empty:
        result["equity"] = (1 + result["net_return"]).cumprod()
        result["benchmark_equity"] = (1 + result["benchmark_return"]).cumprod()
        result["relative_equity"] = result["equity"] / result["benchmark_equity"]
    return result
