"""Tests for the beginner-to-research audit using the fixed artificial dataset."""
import unittest

from examples.research_audit_lab import (
    audit, average_ranks, load_rows, select_top_two, spearman,
)


class ResearchAuditLabTests(unittest.TestCase):
    def test_ties_use_average_ranks(self):
        self.assertEqual(average_ranks([2, 1, 2, 4]), [2.5, 1.0, 2.5, 4.0])
        self.assertIsNone(spearman([1, 1, 1], [1, 2, 3]))

    def test_first_period_and_fold_boundaries(self):
        report = audit(load_rows())
        self.assertEqual(report["round_count"], 60)
        self.assertEqual(report["row_count"], 240)
        self.assertEqual(report["defined_ic_rounds"], 60)
        first = report["first_round"]
        self.assertEqual(first["selected"], ["A", "C"])
        self.assertAlmostEqual(first["gross_return"], 0.04)
        self.assertAlmostEqual(first["equal_weight_benchmark"], 0.0175)
        self.assertAlmostEqual(first["rank_ic"], 0.8)
        self.assertTrue(all(boundary["passes"] for boundary in report["boundaries"]))

    def test_future_labels_cannot_change_selection(self):
        first = [dict(r) for r in load_rows() if r["round_id"] == 1]
        selected = select_top_two(first)
        for row in first:
            row["fwd_return"] = -10 if row["code"] == "A" else 10
        self.assertEqual(select_top_two(first), selected)

    def test_future_feature_is_rejected(self):
        rows = load_rows()
        rows[0]["feature_available_day"] = rows[0]["signal_day"] + 1
        with self.assertRaisesRegex(ValueError, "not yet available"):
            audit(rows)

    def test_label_crossing_fold_is_rejected(self):
        rows = load_rows()
        for row in rows:
            if row["round_id"] == 36:
                row["exit_day"] = 223
        with self.assertRaisesRegex(ValueError, "crosses validation"):
            audit(rows)


if __name__ == "__main__":
    unittest.main()
