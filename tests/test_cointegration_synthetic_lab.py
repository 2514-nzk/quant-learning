import copy
import unittest
from examples.cointegration_synthetic_lab import evaluate, generate

class SyntheticCointegrationLabTests(unittest.TestCase):
    def test_known_data_generating_process_and_evidence_boundary(self):
        result=evaluate()
        self.assertEqual(result["evidence_grade"],"SYNTHETIC_ONLY")
        self.assertTrue(result["data_generating_process_known"])
        self.assertFalse(result["market_cointegration_proven"])
        self.assertFalse(result["market_alpha_proven"])
        self.assertFalse(result["execution_proven"])

    def test_time_split_is_frozen_and_has_holdout(self):
        result=evaluate()
        self.assertEqual((result["train_observations"],result["holdout_observations"]),(200,100))

    def test_known_stationary_spread_is_distinguished_from_random_walk_control(self):
        result=evaluate()
        self.assertTrue(result["train_spread"]["stationary_ar1_parameter_region"])
        self.assertFalse(result["independent_random_walk_control"]["train_spread"]["stationary_ar1_parameter_region"])

    def test_future_holdout_changes_do_not_reestimate_training_hedge_ratio(self):
        data=generate()
        before=evaluate(data)
        changed=copy.deepcopy(data)
        for key in changed:
            changed[key][200:]=[v*3.0+50.0 for v in changed[key][200:]]
        after=evaluate(changed)
        self.assertEqual(before["fit"],after["fit"])
        self.assertEqual(before["train_spread"],after["train_spread"])

    def test_rejects_malformed_or_nonfinite_series(self):
        data=generate()
        data["x"][0]=float("nan")
        with self.assertRaises(ValueError):
            evaluate(data)

if __name__=="__main__":
    unittest.main()
