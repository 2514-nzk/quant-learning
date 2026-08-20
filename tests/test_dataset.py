import numpy as np
import pandas as pd

from src.dataset import build_features_and_labels


def _panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=35)
    rows = []
    for code, base in (("A", 10.0), ("B", 20.0)):
        for i, date in enumerate(dates):
            if code == "A" and i == 25:
                continue
            price = base + i * 0.1
            rows.append(
                {
                    "trade_date": date,
                    "code": code,
                    "open": price,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price * 1.002,
                    "amount": 1_000_000 + i * 10_000,
                    "market_cap": 1_000_000_000,
                    "can_buy": True,
                    "can_sell": not (code == "B" and i == 28),
                    "signal_eligible": True,
                }
            )
    return pd.DataFrame(rows)


def test_labels_use_market_calendar_and_track_delayed_exit():
    dates = pd.bdate_range("2024-01-02", periods=35)
    sample = build_features_and_labels(_panel(), horizon=5)

    missing_entry = sample[(sample.code == "A") & (sample.trade_date == dates[24])].iloc[0]
    assert missing_entry.entry_date == dates[25]
    assert not missing_entry.can_enter
    assert np.isnan(missing_entry.entry_price)

    delayed = sample[(sample.code == "B") & (sample.trade_date == dates[23])].iloc[0]
    assert delayed.scheduled_exit_date == dates[28]
    assert delayed.actual_exit_date == dates[29]
    assert not delayed.can_exit_on_schedule
    assert delayed.exit_delay_days > 0


def test_cross_sectional_rank_is_direct_return_rank():
    sample = build_features_and_labels(_panel(), horizon=5)
    day = sample[sample.trade_date == sample.trade_date.iloc[0]].dropna(subset=["fwd_return"])
    expected = day["fwd_return"].rank(pct=True)
    pd.testing.assert_series_equal(day["label_rank"], expected, check_names=False)


def test_rank_only_uses_the_point_in_time_universe():
    dates = pd.bdate_range("2024-01-02", periods=35)
    panel = _panel()
    signal_date = dates[23]
    exit_date = dates[28]
    panel.loc[(panel.code == "B") & (panel.trade_date == signal_date), "signal_eligible"] = False
    panel.loc[(panel.code == "B") & (panel.trade_date == exit_date), "close"] = 100.0
    sample = build_features_and_labels(panel, horizon=5)
    eligible_row = sample[(sample.code == "A") & (sample.trade_date == signal_date)].iloc[0]
    assert eligible_row.label_rank == 1.0


def test_min_history_is_enforced_per_security():
    sample = build_features_and_labels(_panel(), horizon=5, min_history=30)

    assert not sample.empty
    assert sample["history_observations"].min() >= 30
