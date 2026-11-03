"""用独立手算核对故事里的金额、排名、时间边界和已知信息。"""

import csv
import math
from pathlib import Path

from examples.story_research import basic_report, factor_scores, load_rows, rank_ic, replay_first_round, select_two


def test_four_rounds_compound_from_the_same_money():
    report = basic_report(load_rows())
    assert math.isclose(report["rounds"][-1]["wealth"], 8000 * 1.04 * 1.04 * .94 * .98)
    assert math.isclose(report["rounds"][-1]["wealth"], 7970.95936)
    assert math.isclose(report["rounds"][-1]["benchmark_wealth"], 8438.0593275)
    assert math.isclose(report["mean_rank_ic"], -.45)
    assert math.isclose(report["execution"]["ideal"]["final_money"], report["rounds"][0]["wealth"])


def test_buy_fee_fits_budget_and_failed_order_preserves_cash():
    result = replay_first_round(("C",), .001)
    a, c = result["ledger"]
    assert math.isclose(a["buy_notional"] + a["buy_fee"], 4000)
    assert math.isclose(a["sell_notional"] - a["sell_fee"], a["cash"])
    assert c["status"] == "cash" and c["cash"] == 4000
    assert math.isclose(result["final_money"], 4000 + 4000 / 1.001 * 1.05 * .999)


def test_future_answers_do_not_change_the_decision():
    rows = [row for row in load_rows() if row["round_id"] == 1]
    changed = [{**row, "fwd_return": -100 * row["fwd_return"]} for row in rows]
    for sample in (rows, changed):
        chosen = select_two(sample, factor_scores(sample, ["mom_5"]))
        assert [row["code"] for row in chosen] == ["A", "C"]


def test_price_history_agrees_with_the_first_round():
    path = Path(__file__).resolve().parents[1] / "data/story/price_history.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        history = list(csv.DictReader(stream))
    first_round = [row for row in load_rows() if row["round_id"] == 1]
    for row in first_round:
        values = sorted((int(h["day"]), float(h["close_index"])) for h in history if h["code"] == row["code"])
        assert len(values) == 6
        assert math.isclose(values[-1][1] / values[0][1] - 1, row["mom_5"])
        assert row["feature_available_day"] == values[-1][0] == row["signal_day"]


def test_split_boundaries_wait_for_labels():
    rows = load_rows()
    assert max(r["exit_day"] for r in rows if r["round_id"] <= 36) == 221
    assert min(r["signal_day"] for r in rows if r["round_id"] == 37) == 222
    assert max(r["exit_day"] for r in rows if r["round_id"] == 46) == 281
    assert min(r["signal_day"] for r in rows if r["round_id"] == 47) == 282


def test_rank_correlation_handles_ties_and_constants():
    assert math.isclose(rank_ic([8, -1, 4, 2], [5, 1, 3, -2]), .8)
    assert math.isclose(rank_ic([1, 2, 2, 4], [1, 3, 2, 4]), math.sqrt(.9))
    assert rank_ic([1, 1, 1, 1], [1, 2, 3, 4]) is None
