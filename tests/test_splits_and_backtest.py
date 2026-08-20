import pandas as pd

from src.backtest import top_n_backtest
from src.research import rolling_splits, validate_config


def test_rolling_split_has_embargo_on_both_boundaries():
    dates = list(pd.bdate_range("2024-01-02", periods=40))
    train, validation, test = next(rolling_splits(dates, 10, 5, 5, 5, 3))
    positions = {date: i for i, date in enumerate(dates)}
    assert positions[validation[0]] - positions[train[-1]] == 4
    assert positions[test[0]] - positions[validation[-1]] == 4


def test_backtest_filters_unbuyable_names_and_waits_for_delayed_exit():
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    predictions = pd.DataFrame(
        [
            {
                "trade_date": dates[0],
                "code": "BLOCKED",
                "prediction": 10.0,
                "fwd_return": 0.5,
                "realized_return": 0.5,
                "can_enter": False,
                "entry_date": pd.Timestamp("2024-01-03"),
                "scheduled_exit_date": pd.Timestamp("2024-01-05"),
                "actual_exit_date": pd.Timestamp("2024-01-05"),
                "exit_delay_days": 0,
            },
            {
                "trade_date": dates[0],
                "code": "A",
                "prediction": 1.0,
                "fwd_return": 0.1,
                "realized_return": 0.08,
                "can_enter": True,
                "entry_date": pd.Timestamp("2024-01-03"),
                "scheduled_exit_date": pd.Timestamp("2024-01-05"),
                "actual_exit_date": pd.Timestamp("2024-01-08"),
                "exit_delay_days": 3,
            },
            {
                "trade_date": dates[1],
                "code": "B",
                "prediction": 2.0,
                "fwd_return": 0.2,
                "realized_return": 0.2,
                "can_enter": True,
                "entry_date": pd.Timestamp("2024-01-04"),
                "scheduled_exit_date": pd.Timestamp("2024-01-08"),
                "actual_exit_date": pd.Timestamp("2024-01-08"),
                "exit_delay_days": 0,
            },
        ]
    )
    result = top_n_backtest(predictions, top_n=1, holding_days=1, cost_bps=10)
    assert len(result) == 1
    assert result.iloc[0].gross_return == 0.08
    assert result.iloc[0].n_delayed_exits == 1


def test_config_rejects_insufficient_embargo():
    config = {
        "seed": 1,
        "label": {"horizon": 5},
        "split": {"train_days": 20, "validation_days": 5, "test_days": 5, "step_days": 5, "embargo_days": 4},
        "model": {"top_n": 2, "holding_days": 5, "cost_bps": 1, "stress_cost_bps": 2},
    }
    try:
        validate_config(config)
    except ValueError as exc:
        assert "embargo_days" in str(exc)
    else:
        raise AssertionError("expected config validation to fail")
