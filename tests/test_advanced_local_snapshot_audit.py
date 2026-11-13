"""Guard public aggregate claims without accessing private source datasets."""
import copy
import json
import subprocess
import sys
import unittest

from examples.advanced_local_snapshot_audit import REPORT, validate


class LocalAggregatesEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_2024_quote_partition_matrix_reconciles(self):
        result = validate(self.report)
        self.assertEqual(result["year_2024_rows"], 1296795)
        self.assertEqual(result["observed_quotes"], 1236280)
        self.assertEqual(result["missing_quotes"], 60515)
        self.assertEqual(result["by_exchange"]["BJ"], 60463)

    def test_single_day_state_reconciles(self):
        day = self.report["year_2024"]["example_day"]
        self.assertEqual(sum(day["exchange_rows"].values()), 5365)
        self.assertEqual(day["quote_present"], 5116)
        self.assertEqual(day["quote_missing"], 249)
        self.assertEqual(day["is_trading_unknown"], 249)

    def test_false_market_claims_stay_false(self):
        result = validate(self.report)
        self.assertIsNone(result["full_market_coverage"])
        self.assertFalse(result["historical_pit_verified"])
        bad = copy.deepcopy(self.report)
        bad["claims"]["independently_verified_event_time_PIT"] = True
        with self.assertRaisesRegex(ValueError, "unverified"):
            validate(bad)

    def test_tampered_denominator_rejected(self):
        bad = copy.deepcopy(self.report)
        bad["year_2024"]["exchange_quote_rows"]["BJ"]["quote_missing"] -= 2
        with self.assertRaisesRegex(ValueError, "denominator mismatch"):
            validate(bad)

    def test_source_file_digest_has_expected_shape(self):
        self.assertEqual(self.report["year_2024"]["sha256"],
                         "11eb9645ef8f6e9b420f24c464e9fd9511503e593a6bc17cafcd179b7e386c34")
        self.assertEqual(self.report["origin"]["raw_data_included"], False)

    def test_cli_replays_aggregate_only(self):
        process = subprocess.run([sys.executable, "examples/advanced_local_snapshot_audit.py",
                                  "--json"], cwd=REPORT.parents[2],
                                 text=True, capture_output=True, check=True)
        result = json.loads(process.stdout)
        self.assertEqual(result["missing_quotes"], 60515)
        self.assertIsNone(result["full_market_coverage"])


if __name__ == "__main__":
    unittest.main()
