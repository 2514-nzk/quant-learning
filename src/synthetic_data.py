"""生成可复现的合成股票面板，用于先验证研究流程。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .dataset import build_features_and_labels as _build_features_and_labels


def make_synthetic_panel(
    n_stocks: int = 80,
    start: str = "2018-01-01",
    end: str = "2024-12-31",
    sector_count: int = 8,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, end)
    codes = [f"S{i:04d}" for i in range(n_stocks)]
    sectors = {code: f"sector_{i % sector_count}" for i, code in enumerate(codes)}
    quality = dict(zip(codes, rng.normal(0, 0.8, n_stocks)))
    rows: list[pd.DataFrame] = []
    previous_close = dict(zip(codes, rng.uniform(8, 60, n_stocks)))
    for date in dates:
        market = rng.normal(0, 0.008)
        sector_shock = {f"sector_{i}": rng.normal(0, 0.006) for i in range(sector_count)}
        day_rows = []
        for code in codes:
            if rng.random() < 0.015:
                continue  # 模拟停牌
            prev = previous_close[code]
            # latent quality 让特征与未来收益有弱而不稳定的关系。
            ret = (
                0.00015
                + 0.00035 * quality[code]
                + 0.25 * market
                + sector_shock[sectors[code]]
                + rng.normal(0, 0.018)
            )
            close = max(1.0, prev * (1 + ret))
            open_price = max(1.0, prev * (1 + rng.normal(0, 0.010)))
            high = max(open_price, close) * (1 + abs(rng.normal(0, 0.008)))
            low = min(open_price, close) * (1 - abs(rng.normal(0, 0.008)))
            amount = max(1e5, rng.lognormal(15.0 + 0.25 * quality[code], 0.45))
            day_rows.append(
                {
                    "trade_date": date,
                    "code": code,
                    "sector": sectors[code],
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": amount / max(close, 1),
                    "amount": amount,
                    "market_cap": rng.lognormal(22.0, 0.7),
                    "is_tradeable": True,
                    "can_buy": True,
                    "can_sell": True,
                    "signal_eligible": True,
                }
            )
            previous_close[code] = close
        rows.append(pd.DataFrame(day_rows))
    panel = pd.concat(rows, ignore_index=True).sort_values(["trade_date", "code"])
    panel["ret_1d"] = panel.groupby("code")["close"].pct_change()
    return panel.reset_index(drop=True)


def build_features_and_labels(panel: pd.DataFrame, horizon: int = 5, min_history: int = 1) -> pd.DataFrame:
    return _build_features_and_labels(panel, horizon, min_history)
