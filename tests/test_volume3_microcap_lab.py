import copy,unittest
from examples.volume3_microcap_lab import load,run
class MicrocapLabTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.data=load()
 def test_fixture_frozen_synthetic(self):self.assertEqual(self.data["evidence_grade"],"SYNTHETIC_ONLY");self.assertEqual(len(self.data["rebalance_dates"]),3)
 def test_late_financial_data_excluded(self):
  d=copy.deepcopy(self.data);row=next(x for x in d["observations"] if x["date"]==d["rebalance_dates"][0]);row["financial_available_at"]="2026-12-31T18:00:00+08:00";self.assertNotIn(row["security_id"],run(d)["reports"][0]["eligible"])
 def test_primary_and_backup_separate(self):
  for r in run(self.data)["reports"]:self.assertLessEqual(len(r["primary"]),5);self.assertLessEqual(len(r["resi5_backup"]),5);self.assertFalse(set(r["primary"])&set(r["resi5_backup"]))
 def test_limit_down_and_suspension_blocked(self):
  blocked={x["security_id"] for x in run(self.data)["reports"][0]["blocked_orders"]};self.assertIn("S06",blocked);self.assertIn("S09",blocked)
 def test_cash_and_weights_bounded(self):
  for r in run(self.data)["reports"]:self.assertLessEqual(sum(r["actual_weights"].values()),1+1e-12);self.assertGreaterEqual(r["cash_weight"],0);self.assertAlmostEqual(sum(r["actual_weights"].values())+r["cash_weight"],1)
 def test_no_real_market_claim(self):
  x=run(self.data);self.assertFalse(x["market_pit_proven"]);self.assertFalse(x["real_OOS_proven"]);self.assertFalse(x["execution_proven"])
if __name__=="__main__":unittest.main()
