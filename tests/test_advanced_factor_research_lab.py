"""Synthetic tests for advanced factor engineering, purge and inference lab."""
from __future__ import annotations

import copy
import math
import unittest
from datetime import timedelta

from examples.advanced_factor_research_lab import (
    describe_day, hac_mean_se, holm_adjust, make_synthetic_panel,
    moment, moving_block_ci, pearson, purge_forward, quantile, rank_ic,
    ranks, run_lab, stamp, transform_factor_day, validate_panel,
)


def groups():
    data = make_synthetic_panel()
    first = data[0]["signal_at"]
    return [r for r in data if r["signal_at"] == first]


class FactorResearchLabTests(unittest.TestCase):
    def test_synthetic_run_documents_no_real_market_claim(self):
        result = run_lab()
        self.assertEqual(result["periods"], 12)
        self.assertEqual(result["rows"], 144)
        self.assertEqual(result["purge_demo"]["clean_removed"], 0)
        self.assertEqual(result["purge_demo"]["overlap_removed"], 1)
        self.assertIn("SYNTHETIC_ONLY", result["source_kind"])
        self.assertEqual(len(result["quartile_gross_returns"]), 4)

    def test_no_naive_timestamps(self):
        data = groups()
        data[0]["signal_at"] = "2024-01-05T15:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate_panel(data)

    def test_future_features_rejected(self):
        data = groups()
        data[0]["feature_available_at"] = "2024-01-05T16:00+08:00"
        with self.assertRaisesRegex(ValueError, "time order"):
            validate_panel(data)

    def test_duplicate_key_rejected(self):
        data = groups()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_panel(data + [dict(data[0])])

    def test_nonfinite_factor_rejected(self):
        data = groups()
        data[0]["factor_raw"] = math.nan
        with self.assertRaisesRegex(ValueError, "non-finite"):
            validate_panel(data)

    def test_forward_purge_uses_label_available_not_fixed_n_rows(self):
        panel = make_synthetic_panel()
        split = panel[9*12]["signal_at"]
        train, valid = panel[:9*12], panel[9*12:]
        changed = [dict(r) for r in train]
        cutoff = moment(split)
        # Last training sample's label was formed before the signal,
        # but its final quality-controlled *availability* is later.
        changed[-1]["label_available_at"] = stamp(cutoff + timedelta(minutes=1))
        outcome = purge_forward(changed, valid)
        self.assertEqual(len(outcome["removed"]), 1)
        self.assertEqual(len(outcome["kept"]), len(train) - 1)

    def test_strict_equality_at_boundary_removed(self):
        panel = make_synthetic_panel()
        train = [dict(r) for r in panel[:9*12]]
        valid = panel[9*12:]
        train[-1]["label_available_at"] = valid[0]["signal_at"]
        self.assertEqual(len(purge_forward(train, valid)["removed"]), 1)

    def test_reject_past_valid_with_future_training(self):
        panel = make_synthetic_panel()
        with self.assertRaisesRegex(ValueError, "forward-only"):
            purge_forward(panel[9*12:], panel[:12])

    def test_safety_gap_adds_buffer(self):
        panel = make_synthetic_panel()
        outcome = purge_forward(panel[:9*12], panel[9*12:], safety_gap_minutes=330)
        self.assertEqual(len(outcome["removed"]), 12)

    def test_neutralization_sector_means_and_size_exposure(self):
        processed = transform_factor_day(groups())
        industries = sorted({r["industry"] for r in processed})
        for industry in industries:
            values = [r["factor_neutral"] for r in processed if r["industry"] == industry]
            self.assertAlmostEqual(sum(values)/len(values), 0.0, places=11)
        self.assertAlmostEqual(sum(r["factor_neutral"] * r["log_mcap"]
                                   for r in processed), 0.0, places=10)

    def test_clean_features_do_not_consult_future_returns(self):
        before = transform_factor_day(groups())
        altered = [dict(r, future_return=1000 + i) for i, r in enumerate(groups())]
        after = transform_factor_day(altered)
        self.assertEqual([r["factor_neutral"] for r in before],
                         [r["factor_neutral"] for r in after])

    def test_singular_size_exposure_is_rejected(self):
        data = groups()
        for row in data:
            row["log_mcap"] = {"I1": 10, "I2": 11, "I3": 12}[row["industry"]]
        with self.assertRaisesRegex(ValueError, "collinear"):
            transform_factor_day(data)

    def test_rankic_with_ties_and_undefined_constant(self):
        self.assertEqual(ranks([3, 1, 1]), [3.0, 1.5, 1.5])
        self.assertAlmostEqual(rank_ic([1,2,3], [3,2,1]), -1)
        self.assertIsNone(rank_ic([1,1,1], [1,2,3]))
        self.assertIsNone(pearson([1,2,3], [1,1,1]))

    def test_quartile_uses_deterministic_tie_break(self):
        scored = transform_factor_day(groups())
        scored[0]["factor_neutral"] = scored[1]["factor_neutral"]
        first = describe_day(scored)
        second = describe_day(list(reversed(scored)))
        self.assertEqual(first["top_codes"], second["top_codes"])

    def test_hac_and_bootstrap_are_finite_deterministic(self):
        series = [0.1, -0.1, 0.03, 0.08, -0.04, 0.02, 0.11, -0.01]
        self.assertGreater(hac_mean_se(series, lags=2), 0)
        self.assertEqual(moving_block_ci(series, block=2, reps=250, seed=5),
                         moving_block_ci(series, block=2, reps=250, seed=5))
        with self.assertRaisesRegex(ValueError, "HAC"):
            hac_mean_se(series, lags=len(series))

    def test_bootstrap_constant_series_no_fake_significance(self):
        self.assertEqual(moving_block_ci([0.2]*8, block=3, reps=100), [0.2, 0.2])
        self.assertEqual(hac_mean_se([0.2]*8, lags=2), 0)

    def test_holm_adjustment_preserves_order_and_validity(self):
        self.assertEqual(holm_adjust([.03, .01, .08]), [.06, .03, .08])
        with self.assertRaises(ValueError):
            holm_adjust([.05, float("nan")])


if __name__ == "__main__":
    unittest.main()
