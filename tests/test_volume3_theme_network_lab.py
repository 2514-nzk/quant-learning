import copy
import unittest
from datetime import datetime
from examples.volume3_theme_network_lab import (
    evaluate, jaccard, load_fixture, snapshot_for_period, validate, weighted_jaccard
)

class ThemeNetworkLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_fixture()

    def test_fixture_is_frozen_synthetic_with_six_periods(self):
        self.assertEqual(self.data["evidence_grade"], "SYNTHETIC_ONLY")
        self.assertEqual(len(self.data["periods"]), 6)
        self.assertEqual(len(self.data["securities"]), 12)

    def test_late_theme_edge_is_not_backfilled(self):
        p3 = snapshot_for_period(self.data["periods"][2], self.data)
        p4 = snapshot_for_period(self.data["periods"][3], self.data)
        self.assertNotIn("T03", p3["themes_by_security"]["S04"])
        self.assertIn("T03", p4["themes_by_security"]["S04"])

    def test_effective_date_and_availability_both_matter(self):
        p4 = snapshot_for_period(self.data["periods"][3], self.data)
        p5 = snapshot_for_period(self.data["periods"][4], self.data)
        self.assertIn("T06", p4["themes_by_security"]["S08"])
        self.assertNotIn("T06", p5["themes_by_security"]["S08"])
        self.assertNotIn("T04", p4["themes_by_security"]["S08"])
        self.assertIn("T04", p5["themes_by_security"]["S08"])

    def test_industry_baseline_only_compares_same_industry_peers(self):
        result = evaluate(self.data)
        industry = {x["security_id"]: x["industry_id"] for x in self.data["securities"]}
        for row in result["anchor_observations"]:
            for peer in row["shared_peer_ids"] + row["nonshared_peer_ids"]:
                self.assertEqual(industry[peer], row["industry_id"])
                self.assertNotEqual(peer, row["anchor"])

    def test_jaccard_is_symmetric_and_bounded(self):
        left, right = {"T1", "T2"}, {"T2", "T3"}
        self.assertAlmostEqual(jaccard(left, right), 1 / 3)
        self.assertAlmostEqual(jaccard(left, right), jaccard(right, left))
        self.assertGreaterEqual(jaccard(left, right), 0)
        self.assertLessEqual(jaccard(left, right), 1)

    def test_weighted_jaccard_is_symmetric_and_bounded(self):
        breadth = {"T1": 2, "T2": 5, "T3": 1}
        a = weighted_jaccard({"T1", "T2"}, {"T2", "T3"}, breadth, 12)
        b = weighted_jaccard({"T2", "T3"}, {"T1", "T2"}, breadth, 12)
        self.assertAlmostEqual(a, b)
        self.assertGreaterEqual(a, 0)
        self.assertLessEqual(a, 1)

    def test_weighted_similarity_is_reported_for_shared_peers(self):
        result = evaluate(self.data)
        for period in result["periods"]:
            self.assertGreaterEqual(period["mean_shared_weighted_jaccard"], 0)
            self.assertLessEqual(period["mean_shared_weighted_jaccard"], 1)

    def test_future_return_mutation_does_not_change_network_snapshot(self):
        changed = copy.deepcopy(self.data)
        before = snapshot_for_period(changed["periods"][0], changed)
        for row in changed["periods"][0]["returns"]:
            row["forward_return"] += 0.25
        after = snapshot_for_period(changed["periods"][0], changed)
        self.assertEqual(before["edges"], after["edges"])
        self.assertEqual(before["theme_breadth"], after["theme_breadth"])

    def test_availability_equal_to_decision_is_excluded(self):
        changed = copy.deepcopy(self.data)
        changed["theme_memberships"][0]["available_at"] = changed["periods"][0]["decision_at"]
        snap = snapshot_for_period(changed["periods"][0], changed)
        self.assertNotIn("T01", snap["themes_by_security"]["S01"])

    def test_future_label_is_never_available_at_decision(self):
        for period in self.data["periods"]:
            self.assertLess(datetime.fromisoformat(period["exit_at"]),
                            datetime.fromisoformat(period["label_available_at"]))
            self.assertLess(datetime.fromisoformat(period["decision_at"]),
                            datetime.fromisoformat(period["entry_at"]))

    def test_duplicate_active_edge_is_rejected(self):
        changed = copy.deepcopy(self.data)
        duplicate = copy.deepcopy(changed["theme_memberships"][0])
        duplicate["record_id"] = "DUPLICATE_EDGE"
        changed["theme_memberships"].append(duplicate)
        with self.assertRaises(ValueError):
            snapshot_for_period(changed["periods"][0], changed)

    def test_missing_future_return_is_rejected_not_imputed(self):
        changed = copy.deepcopy(self.data)
        changed["periods"][0]["returns"].pop()
        with self.assertRaises(ValueError):
            validate(changed)

    def test_date_blocks_not_pair_rows_define_bootstrap_units(self):
        result = evaluate(self.data)
        self.assertEqual(result["overall"]["independent_time_blocks"], 6)
        self.assertGreater(result["overall"]["anchor_period_observations"], 6)
        self.assertEqual(len(result["overall"]["period_block_bootstrap_95_descriptive"]), 2)

    def test_leave_one_industry_out_is_reported(self):
        result = evaluate(self.data)
        self.assertEqual(set(result["leave_one_industry_out"]), {"IND_A", "IND_B", "IND_C"})

    def test_synthetic_results_never_claim_alpha_or_causality(self):
        result = evaluate(self.data)
        self.assertFalse(result["market_pit_proven"])
        self.assertFalse(result["incremental_predictive_value_proven"])
        self.assertFalse(result["causal_effect_proven"])
        self.assertFalse(result["execution_proven"])

if __name__ == "__main__":
    unittest.main()
