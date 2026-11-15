"""Regression of third-volume 01–04 against a self-contained teaching dataset."""
import copy
import math
import unittest

from examples.volume3_strategy_lab import (
    DATASET_ID, asof_members, eligible_training_weeks, evaluate, load_fixture,
    ranked_industries, regime, run_strategy, score_momentum, score_reversal, spearman, target_weights,
    turnover_l1, validate_fixture,
)


class VolumeThreeStrategyLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture()

    def test_fixed_data_and_taxonomy_change(self):
        f = self.fixture
        self.assertEqual(f["dataset_id"], DATASET_ID)
        self.assertEqual(f["evidence_grade"], "SYNTHETIC_ONLY")
        self.assertEqual(len(f["weeks"]), 16)
        self.assertEqual({w["taxonomy_version"] for w in f["weeks"][:8]}, {"TEACH_OLD"})
        self.assertEqual({w["taxonomy_version"] for w in f["weeks"][8:]}, {"TEACH_NEW"})
        before = {s["security_id"]: s["industry_code"] for s in f["weeks"][7]["stocks"]}
        after = {s["security_id"]: s["industry_code"] for s in f["weeks"][8]["stocks"]}
        self.assertEqual(before["S02"], "O_A")
        self.assertEqual(after["S02"], "N_B")

    def test_known_late_industry_member_not_silently_included(self):
        w = self.fixture["weeks"][6]
        known = {s["security_id"] for s in asof_members(w)}
        self.assertNotIn("S03", known)
        self.assertEqual(len(known), 7)
        self.assertEqual(len(asof_members(self.fixture["weeks"][5])), 8)

    def test_purge_uses_label_available_not_exit_date_or_fixed_rows(self):
        weeks = self.fixture["weeks"]
        self.assertEqual(eligible_training_weeks(weeks, weeks[1]), [])
        self.assertEqual(eligible_training_weeks(weeks, weeks[2]), [1])
        self.assertEqual(eligible_training_weeks(weeks, weeks[3]), [1, 2])
        copydata = copy.deepcopy(weeks)
        copydata[0]["label_available_at"] = copydata[6]["label_available_at"]
        self.assertEqual(eligible_training_weeks(copydata, copydata[2]), [])

    def test_regime_and_ranks_do_not_use_future_returns(self):
        original = self.fixture["weeks"][0]
        changed = copy.deepcopy(original)
        for industry in changed["industries"]:
            industry["following_period_return"] = -99
        for stock in changed["stocks"]:
            stock["following_period_return"] = 99
        self.assertEqual(regime(original), regime(changed))
        self.assertEqual(ranked_industries(original), ranked_industries(changed))
        for strategy in ("always_top", "regime_gated_top", "equal_four", "cash"):
            self.assertEqual(target_weights(original, strategy), target_weights(changed, strategy))
        self.assertNotEqual(run_strategy([original], "always_top", .001)[0]["gross_observation"],
                            run_strategy([changed], "always_top", .001)[0]["gross_observation"])

    def test_reject_time_leak_future_regime_and_industry_feature(self):
        bad = copy.deepcopy(self.fixture)
        bad["weeks"][0]["market"]["known_at"] = bad["weeks"][1]["signal_at"]
        with self.assertRaises(ValueError):
            validate_fixture(bad)
        bad = copy.deepcopy(self.fixture)
        bad["weeks"][0]["industries"][0]["feature_known_at"] = bad["weeks"][1]["signal_at"]
        with self.assertRaises(ValueError):
            validate_fixture(bad)
        bad = copy.deepcopy(self.fixture)
        bad["weeks"][0]["label_available_at"] = bad["weeks"][0]["entry_at"]
        with self.assertRaises(ValueError):
            validate_fixture(bad)

    def test_reject_naive_timestamp_duplicate_member_and_false_taxonomy(self):
        bad = copy.deepcopy(self.fixture)
        bad["weeks"][0]["decision_at"] = "2024-07-02T10:20:00"
        with self.assertRaises(ValueError):
            validate_fixture(bad)
        bad = copy.deepcopy(self.fixture)
        bad["weeks"][0]["stocks"][1]["security_id"] = "S01"
        with self.assertRaises(ValueError):
            validate_fixture(bad)
        bad = copy.deepcopy(self.fixture)
        bad["weeks"][8]["taxonomy_version"] = "TEACH_OLD"
        with self.assertRaises(ValueError):
            validate_fixture(bad)

    def test_score_definitions_and_ties(self):
        item = {"price_t": 95, "price_reference_reversal": 100, "price_reference_momentum": 90}
        self.assertAlmostEqual(score_reversal(item), .05)
        self.assertAlmostEqual(score_momentum(item), 95 / 90 - 1)
        self.assertAlmostEqual(spearman([1, 2, 3], [3, 2, 1]), -1)
        self.assertIsNone(spearman([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(spearman([1, 2], [1, 2]))
        self.assertAlmostEqual(spearman([1, 1, 3], [1, 2, 3]), math.sqrt(.75))

    def test_l1_turnover_cash_and_cost_are_explicit_proxies(self):
        self.assertAlmostEqual(turnover_l1({}, {"A": 1}), 1)
        self.assertAlmostEqual(turnover_l1({"A": 1}, {"B": 1}), 2)
        self.assertAlmostEqual(turnover_l1({"A": .25}, {"A": .25}), 0)
        rows = run_strategy(self.fixture["weeks"], "cash", .0017)
        self.assertTrue(all(p["synthetic_net_observation"] == 0 for p in rows))
        top = run_strategy(self.fixture["weeks"], "always_top", .0017)
        for p in top:
            self.assertAlmostEqual(p["synthetic_net_observation"],
                                   p["gross_observation"] - p["synthetic_cost_proxy"])

    def test_report_has_no_fabricated_market_claim(self):
        d = evaluate(self.fixture)
        self.assertEqual(d["weeks"], 16)
        self.assertEqual(d["unknown_members"], 1)
        self.assertEqual(len(d["strategies"]), 4)
        self.assertFalse(d["market_pit_proven"])
        self.assertFalse(d["real_market_OOS_proven"])
        self.assertFalse(d["execution_proven"])
        for result in d["strategies"].values():
            self.assertEqual(result["summary"]["development"]["n"], 8)
            self.assertEqual(result["summary"]["later_artificial"]["n"], 8)
            self.assertEqual(len(result["periods"]), 16)


if __name__ == "__main__":
    unittest.main()
