"""Regression tests for the factor/ML deep-dive labs; standard library only."""

from __future__ import annotations

import copy
import json
import math
import unittest

from examples.factor_diagnostics_lab import report, round_metrics, score_round, summarize
from examples.model_selection_audit import REFERENCE, audit_model_report
from examples.research_audit_lab import load_rows


class FactorDeepDiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_rows()

    def test_first_round_hand_calculation(self):
        first = [r for r in self.rows if r["round_id"] == 1]
        metric = round_metrics(first, "mom_5")
        self.assertEqual(metric["selected"], ["A", "C"])
        self.assertAlmostEqual(metric["top2_gross"], .04)
        self.assertAlmostEqual(metric["bottom2_gross"], -.005)
        self.assertAlmostEqual(metric["top_minus_bottom"], .045)
        self.assertAlmostEqual(metric["rank_ic"], .8)

    def test_future_labels_do_not_change_past_scores(self):
        first = [dict(r) for r in self.rows if r["round_id"] == 1]
        for factor in ("mom_5", "ep", "roe", "equal_rank"):
            actual = score_round(first, factor)
            changed = [{**r, "fwd_return": -r["fwd_return"] * 100} for r in first]
            self.assertEqual(score_round(changed, factor), actual)

    def test_fold_report_and_fee_sensitivity(self):
        base = report(self.rows, "mom_5", .001)
        costly = report(self.rows, "mom_5", .005)
        self.assertEqual([base["phases"][k]["periods"] for k in ("train", "validation", "test")], [36, 10, 14])
        self.assertEqual(base["n_stocks_per_round"], 4)
        self.assertEqual(len(base["rounds"]), 60)
        for name in ("train", "validation", "test"):
            self.assertAlmostEqual(
                base["phases"][name]["mean_ic"],
                costly["phases"][name]["mean_ic"],
            )
            self.assertLess(
                costly["phases"][name]["net_top2_final_money"],
                base["phases"][name]["net_top2_final_money"],
            )
        self.assertEqual(base["rounds"][0]["selected"], ["A", "C"])

    def test_extreme_fee_rejected(self):
        with self.assertRaises(ValueError):
            summarize([], fee=1.0)

    def test_invalid_feature_available_time_fails(self):
        altered = copy.deepcopy(self.rows)
        altered[0]["feature_available_day"] = altered[0]["signal_day"] + 1
        with self.assertRaisesRegex(ValueError, "not yet available"):
            report(altered)


class ModelDeepDiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with REFERENCE.open(encoding="utf-8") as source:
            cls.payload = json.load(source)

    def test_frozen_record_selection_matches_validation(self):
        summary = audit_model_report(self.payload)
        self.assertEqual(summary["chosen"]["ridge_alpha"], 0.1)
        self.assertEqual(summary["chosen"]["forest_depth"], 4)
        self.assertEqual(summary["chosen"]["lightgbm_iteration_by_validation_l2"], 14)
        self.assertAlmostEqual(
            summary["test_descriptive_only"]["momentum"]["mean_rank_ic"],
            .4857142857142857,
        )

    def test_wrong_choice_is_rejected(self):
        edited = copy.deepcopy(self.payload)
        edited["models"]["chosen"]["ridge_alpha"] = 10.0
        with self.assertRaisesRegex(ValueError, "Ridge"):
            audit_model_report(edited)

    def test_test_data_cannot_choose_ridge_or_forest(self):
        edited = copy.deepcopy(self.payload)
        edited["models"]["test"]["Ridge"]["mean_rank_ic"] = 0.99
        edited["models"]["test"]["RandomForest"]["mean_rank_ic"] = -0.99
        original = audit_model_report(self.payload)
        altered = audit_model_report(edited)
        self.assertEqual(altered["chosen"], original["chosen"])


if __name__ == "__main__":
    unittest.main()
