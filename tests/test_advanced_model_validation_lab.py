"""Deterministic temporal/model tests; artificial data is NOT market evidence."""
from __future__ import annotations

import copy
import math
import unittest

from examples.advanced_model_validation_lab import (
    CANDIDATES, TRAIN_PERIODS, VALID_PERIODS, eligible_before, fit_model,
    group_by_signal, make_panel, moment, predict_group, run_lab,
    run_prequential, select_on_validation, solve_system, validate_rows,
)


class AdvancedModelValidationTests(unittest.TestCase):
    def test_full_lab_is_explicitly_synthetic(self):
        report = run_lab()
        self.assertEqual(report["total_periods"], 42)
        self.assertEqual(report["total_rows"], 504)
        self.assertEqual(len(report["simulated_prequential"]["folds"]), 12)
        self.assertIn("SYNTHETIC_ONLY", report["source_kind"])
        self.assertEqual(set(report["development"]["validation_ic"]), set(CANDIDATES))

    def test_selection_reads_no_holdout_labels(self):
        rows = make_panel()
        selected = select_on_validation(rows)
        for row in rows[30*12:]:
            row["future_return"] = -row["future_return"] * 9 + 10
        changed = select_on_validation(rows)
        self.assertEqual(selected, changed)

    def test_first_holdout_prediction_invariant_to_same_and_future_labels(self):
        rows = make_panel()
        selection = select_on_validation(rows)
        initial = run_prequential(rows, selection["selected"])
        modified = copy.deepcopy(rows)
        for row in modified[30*12:]:
            row["future_return"] += 100.0
        later = run_prequential(modified, selection["selected"])
        self.assertEqual(initial["folds"][0]["prediction_scores"],
                         later["folds"][0]["prediction_scores"])
        self.assertEqual(initial["folds"][0]["train_fingerprint"],
                         later["folds"][0]["train_fingerprint"])
        self.assertNotEqual(initial["folds"][0]["selected_ic"],
                            later["folds"][0]["selected_ic"])

    def test_prequential_fit_uses_only_completed_known_labels(self):
        rows = make_panel()
        output = run_prequential(rows, "ridge_all")
        for fold in output["folds"]:
            self.assertLess(moment(fold["last_train_label_available_at"]),
                            moment(fold["signal_at"]))
        self.assertEqual(output["folds"][0]["fit_rows"], 30*12)

    def test_validation_train_excludes_late_label(self):
        data = make_panel()
        cutoff = data[20*12]["signal_at"]
        data[19*12]["label_available_at"] = cutoff
        select = select_on_validation(data)
        self.assertEqual(select["train_rows"], 20*12-1)

    def test_duplicate_signal_code_rejected(self):
        data = make_panel()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_rows(data + [dict(data[0])])

    def test_future_feature_is_rejected(self):
        data = make_panel()
        data[0]["feature_available_at"] = "2024-01-05T19:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "timestamp"):
            validate_rows(data)

    def test_missing_timezone_and_nonfinite_rejected(self):
        data = make_panel()
        data[0]["signal_at"] = "2024-01-05T15:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate_rows(data)
        data = make_panel()
        data[0]["factor_a"] = math.nan
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            validate_rows(data)

    def test_model_prediction_cannot_read_labels(self):
        train = make_panel()[:20*12]
        group = make_panel()[20*12:21*12]
        for name in CANDIDATES:
            model = fit_model(name, train)
            before = predict_group(model, group)
            replaced = [dict(r, future_return=math.pi*100) for r in group]
            self.assertEqual(before, predict_group(model, replaced))

    def test_unknown_model_and_singular_solver_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            fit_model("xgboost_unapproved", make_panel()[:20*12])
        with self.assertRaisesRegex(ValueError, "singular"):
            solve_system([[1., 2.], [2., 4.]], [1., 2.])

    def test_reverse_time_is_not_training(self):
        data = make_panel()
        first_holdout = data[30*12]["signal_at"]
        sample = eligible_before(data, first_holdout)
        self.assertTrue(sample)
        self.assertTrue(all(moment(r["signal_at"]) < moment(first_holdout)
                            for r in sample))
        self.assertTrue(all(moment(r["label_available_at"]) < moment(first_holdout)
                            for r in sample))

    def test_prequential_drift_diagnostic_is_posthoc_only(self):
        original = run_lab()
        changed = make_panel()
        for row in changed[30*12:]:
            row["factor_a"] += 100
        new = run_lab(changed)
        self.assertEqual(original["development"], new["development"])
        self.assertNotEqual(original["drift_posthoc"], new["drift_posthoc"])

    def test_ranker_has_actual_pairwise_training(self):
        train = make_panel()[:20*12]
        model = fit_model("pairwise", train)
        self.assertGreater(model["pair_count"], 100)
        self.assertEqual(len(model["weights"]), 3)
        self.assertTrue(all(math.isfinite(w) for w in model["weights"]))


if __name__ == "__main__":
    unittest.main()
