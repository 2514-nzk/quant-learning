import copy
import unittest
from examples.volume3_microcap_lab import load, run, validate
class MicrocapLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=load()
    def test_fixture_is_frozen_synthetic(self):
        self.assertEqual(self.data["evidence_grade"],"SYNTHETIC_ONLY")
        self.assertEqual(len(self.data["rebalance_dates"]),3)
    def test_financial_data_at_or_after_cutoff_is_excluded(self):
        self.assertNotIn("A03",run(self.data)["reports"][0]["eligible"])
    def test_backup_is_used_only_when_primary_pool_is_short(self):
        first=run(self.data)["reports"][0]
        self.assertEqual(len(first["primary"]),3)
        self.assertEqual(first["backup"],["A06"])
        self.assertFalse(set(first["primary"])&set(first["backup"]))
    def test_price_limit_and_suspension_block_new_positions(self):
        reports=run(self.data)["reports"]
        first={x["security_id"]:x["reason"] for x in reports[0]["blocked_orders"]}
        second={x["security_id"]:x["reason"] for x in reports[1]["blocked_orders"]}
        self.assertEqual(first["A06"],"LIMIT_DOWN")
        self.assertEqual(second["A09"],"SUSPENDED")
        self.assertNotIn("A06",reports[0]["constrained_weights"])
        self.assertNotIn("A09",reports[1]["constrained_weights"])
    def test_blocked_exit_keeps_existing_position(self):
        third=run(self.data)["reports"][2]
        self.assertIn({"security_id":"A02","reason":"EXIT_NOT_FILLED"},third["blocked_orders"])
        self.assertAlmostEqual(third["constrained_weights"]["A02"],0.25)
    def test_cash_and_constrained_weights_reconcile(self):
        for r in run(self.data)["reports"]:
            self.assertLessEqual(sum(r["constrained_weights"].values()),1.0+1e-12)
            self.assertGreaterEqual(r["cash_weight"],0.0)
            self.assertAlmostEqual(sum(r["constrained_weights"].values())+r["cash_weight"],1.0)
    def test_duplicate_observations_and_naive_timestamps_fail(self):
        bad=copy.deepcopy(self.data);bad["observations"].append(copy.deepcopy(bad["observations"][0]))
        with self.assertRaises(ValueError):validate(bad)
        bad=copy.deepcopy(self.data);bad["observations"][0]["financial_available_at"]="2026-02-06T15:00:00"
        with self.assertRaises(ValueError):validate(bad)
    def test_no_real_market_or_execution_claim(self):
        r=run(self.data);self.assertFalse(r["market_pit_proven"]);self.assertFalse(r["real_OOS_proven"]);self.assertFalse(r["execution_proven"])
if __name__=="__main__":unittest.main()
