"""共享的特征、交易日历标签和成交资格构造。"""

from __future__ import annotations

import numpy as np
import pandas as pd


FEATURES = ["mom_5", "mom_20", "reversal_3", "vol_20", "range_1d", "amount_chg_5", "log_mkt_cap"]


def _calendar_targets(dates: pd.Series, calendar: pd.DatetimeIndex, offset: int) -> pd.Series:
    positions = pd.Series(np.arange(len(calendar)), index=calendar)
    source_positions = dates.map(positions)
    target_positions = source_positions + offset
    valid = target_positions.between(0, len(calendar) - 1)
    result = pd.Series(pd.NaT, index=dates.index, dtype="datetime64[ns]")
    result.loc[valid] = calendar.take(target_positions.loc[valid].astype(int)).to_numpy()
    return result


def _attach_trade_outcomes(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    calendar = pd.DatetimeIndex(sorted(df["trade_date"].dropna().unique()))
    df["entry_date"] = _calendar_targets(df["trade_date"], calendar, 1)
    df["scheduled_exit_date"] = _calendar_targets(df["trade_date"], calendar, horizon)

    lookup_columns = ["code", "trade_date", "open", "close", "can_buy", "can_sell"]
    lookup = df[lookup_columns].copy()
    entry = lookup.rename(
        columns={
            "trade_date": "entry_date",
            "open": "entry_price",
            "close": "entry_close",
            "can_buy": "can_enter",
            "can_sell": "entry_can_sell",
        }
    )
    scheduled_exit = lookup.rename(
        columns={
            "trade_date": "scheduled_exit_date",
            "open": "scheduled_exit_open",
            "close": "scheduled_exit_price",
            "can_buy": "exit_can_buy",
            "can_sell": "can_exit_on_schedule",
        }
    )
    df = df.merge(entry, on=["code", "entry_date"], how="left")
    df = df.merge(scheduled_exit, on=["code", "scheduled_exit_date"], how="left")
    df["can_enter"] = df["can_enter"].fillna(False).astype(bool)
    df["can_exit_on_schedule"] = df["can_exit_on_schedule"].fillna(False).astype(bool)

    actual_exit_date = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    actual_exit_price = pd.Series(np.nan, index=df.index, dtype=float)
    for _, group in df.groupby("code", sort=False):
        sellable = group.loc[group["can_sell"] & group["close"].notna(), ["trade_date", "close"]]
        if sellable.empty:
            continue
        sell_dates = sellable["trade_date"].to_numpy(dtype="datetime64[ns]")
        sell_prices = sellable["close"].to_numpy(dtype=float)
        targets = group["scheduled_exit_date"].to_numpy(dtype="datetime64[ns]")
        valid_targets = ~pd.isna(targets)
        positions = np.searchsorted(sell_dates, targets[valid_targets], side="left")
        found = positions < len(sell_dates)
        target_index = group.index.to_numpy()[valid_targets][found]
        actual_exit_date.loc[target_index] = sell_dates[positions[found]]
        actual_exit_price.loc[target_index] = sell_prices[positions[found]]

    df["actual_exit_date"] = actual_exit_date
    df["actual_exit_price"] = actual_exit_price
    df["exit_delay_days"] = (df["actual_exit_date"] - df["scheduled_exit_date"]).dt.days
    df["fwd_return"] = df["scheduled_exit_price"] / df["entry_price"] - 1
    df["realized_return"] = np.where(
        df["can_enter"], df["actual_exit_price"] / df["entry_price"] - 1, np.nan
    )
    df["ret_1d_forward"] = df["entry_close"] / df["entry_price"] - 1
    return df


def build_features_and_labels(panel: pd.DataFrame, horizon: int = 5, min_history: int = 1) -> pd.DataFrame:
    """按全市场交易日历构造特征和 T+1 开盘到 T+H 收盘标签。"""
    if horizon < 2:
        raise ValueError("horizon must be at least 2 so entry and exit are distinct")
    if min_history < 1:
        raise ValueError("min_history must be at least 1")
    required = {"trade_date", "code", "open", "high", "low", "close", "amount", "market_cap"}
    missing = sorted(required - set(panel.columns))
    if missing:
        raise ValueError(f"panel is missing required columns: {missing}")

    df = panel.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["code", "trade_date"]).drop_duplicates(["code", "trade_date"], keep="last")
    df["history_observations"] = df.groupby("code").cumcount() + 1
    if "can_buy" not in df:
        df["can_buy"] = df.get("is_tradeable", True)
    if "can_sell" not in df:
        df["can_sell"] = df.get("is_tradeable", True)
    if "signal_eligible" not in df:
        df["signal_eligible"] = True
    df["can_buy"] = df["can_buy"].fillna(False).astype(bool)
    df["can_sell"] = df["can_sell"].fillna(False).astype(bool)
    df["signal_eligible"] = df["signal_eligible"].fillna(False).astype(bool)

    by_code = df.groupby("code", group_keys=False)
    df["ret_1d"] = by_code["close"].pct_change(fill_method=None)
    df["mom_5"] = by_code["close"].pct_change(5, fill_method=None)
    df["mom_20"] = by_code["close"].pct_change(20, fill_method=None)
    df["reversal_3"] = -by_code["close"].pct_change(3, fill_method=None)
    df["vol_20"] = by_code["ret_1d"].rolling(20, min_periods=15).std().reset_index(level=0, drop=True)
    df["range_1d"] = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
    df["amount_chg_5"] = by_code["amount"].pct_change(5, fill_method=None)
    df["log_mkt_cap"] = np.log(df["market_cap"].clip(lower=1))
    df = _attach_trade_outcomes(df, horizon)
    df["signal_eligible"] &= df["history_observations"] >= min_history

    eligible = df["signal_eligible"] & df["fwd_return"].notna()
    df["excess_return"] = np.nan
    df["label_rank"] = np.nan
    eligible_returns = df.loc[eligible, ["trade_date", "fwd_return"]]
    daily_median = eligible_returns.groupby("trade_date")["fwd_return"].transform("median")
    df.loc[eligible, "excess_return"] = eligible_returns["fwd_return"] - daily_median
    df.loc[eligible, "label_rank"] = eligible_returns.groupby("trade_date")["fwd_return"].rank(pct=True)
    df = df.loc[df["signal_eligible"]].dropna(subset=FEATURES)
    return df.reset_index(drop=True)
