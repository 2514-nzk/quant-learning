"""Historical-universe coverage gates: no fake full-market denominator or PIT claim."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from examples.advanced_universe_coverage_lab import (
    DATA, audit_declared_reference, audit_real_four_stock_snapshot,
    demo_coverage_payload,
)

ROOT = Path(__file__).resolve().parents[1]


class HistoricalUniverseCoverageTests(unittest.TestCase):
    def test_demo_universe_keeps_unknown_and_ineligible_separate(self):
        report = audit_declared_reference(demo_coverage_payload())
        self.assertEqual(report["source_kind"], "SYNTHETIC_DEMONSTRATION")
        self.assertEqual(report["snapshot_count"], 2)
        first, second = report["reference_coverage"]
        self.assertEqual(first["known_eligible"], ["A"])
        self.assertEqual(first["known_ineligible"], ["C"])
        self.assertEqual(first["unknown_membership"], ["B"])
        self.assertAlmostEqual(first["reference_membership_known_fraction"], 2/3, places=6)
        self.assertEqual(first["eligible_with_declared_timely_price"], ["A"])
        self.assertEqual(first["field_coverage_on_declared_eligible"]["roe"]["KNOWN"], ["A"])
        self.assertEqual(second["known_eligible"], ["B"])
        self.assertEqual(second["known_ineligible"], ["A", "C"])
        self.assertEqual(second["eligible_with_declared_timely_price"], ["B"])

    def test_all_reference_securities_covered_does_not_imply_all_a_share_coverage(self):
        payload = demo_coverage_payload()
        payload["data_kind"] = "USER_SUPPLIED_UNVERIFIED"
        payload["universe_scope"] = "HISTORICAL_UNIVERSE_CANDIDATE"
        payload["snapshots"][0]["reference_security_ids"] = ["A"]
        report = audit_declared_reference(payload)
        self.assertEqual(report["reference_coverage"][0]["eligible_with_declared_timely_price"],
                         ["A"])
        self.assertFalse(report["historical_full_universe_verified"])
        self.assertFalse(report["historical_pit_verified"])
        self.assertIsNone(report["full_market_coverage_percent"])
        self.assertEqual(report["full_market_denominator_status"],
                         "NOT_VERIFIED_NO_AUTHORITATIVE_FULL_MARKET_LIST")
        self.assertEqual(report["evidence_grade"], "USER_DECLARED_REFERENCE_AUDIT")

    def test_prices_after_decision_are_not_eligible_even_if_record_exists(self):
        payload = demo_coverage_payload()
        payload["prices"][0]["source_published_at"] = "2024-03-20T18:05:00+08:00"
        payload["prices"][0]["ingested_at"] = "2024-03-20T18:10:00+08:00"
        payload["prices"][0]["available_at"] = "2024-03-20T18:10:00+08:00"
        first = audit_declared_reference(payload)["reference_coverage"][0]
        self.assertEqual(first["eligible_with_declared_timely_price"], [])
        self.assertEqual(first["eligible_with_late_price"], ["A"])
        self.assertEqual(first["price_by_reference_security"]["A"]["status"],
                         "LATE_OR_UNAVAILABLE_AT_DECISION")

    def test_no_price_is_distinct_from_late_price(self):
        payload = demo_coverage_payload()
        payload["prices"] = [p for p in payload["prices"] if p["security_id"] != "A"]
        first = audit_declared_reference(payload)["reference_coverage"][0]
        self.assertEqual(first["eligible_without_price"], ["A"])
        self.assertEqual(first["eligible_with_late_price"], [])
        self.assertEqual(first["price_by_reference_security"]["B"]["status"],
                         "LATE_OR_UNAVAILABLE_AT_DECISION")

    def test_late_membership_revision_and_fact_never_backfill(self):
        payload = demo_coverage_payload()
        previous = audit_declared_reference(payload)["reference_coverage"][0]
        payload["membership_events"][1]["effective_to"] = "2024-02-01"
        payload["facts"][1]["value"] = -999
        later = audit_declared_reference(payload)["reference_coverage"][0]
        self.assertEqual(later["known_eligible"], previous["known_eligible"])
        self.assertEqual(later["field_coverage_on_declared_eligible"],
                         previous["field_coverage_on_declared_eligible"])

    def test_duplicate_reference_and_duplicate_price_revisions_are_errors(self):
        payload = demo_coverage_payload()
        payload["snapshots"][0]["reference_security_ids"].append("A")
        with self.assertRaisesRegex(ValueError, "unique"):
            audit_declared_reference(payload)
        payload = demo_coverage_payload()
        payload["prices"].append(copy.deepcopy(payload["prices"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate security-date"):
            audit_declared_reference(payload)

    def test_reject_invalid_source_date_and_price(self):
        payload = demo_coverage_payload()
        payload["membership_events"][0]["source_published_at"] = "2024-01-03T16:00:00"
        with self.assertRaisesRegex(ValueError, "naive"):
            audit_declared_reference(payload)
        payload = demo_coverage_payload()
        payload["prices"][0]["trade_date"] = "2024-03-21"
        with self.assertRaisesRegex(ValueError, "outside"):
            audit_declared_reference(payload)
        payload = demo_coverage_payload()
        payload["prices"][0]["close"] = -1
        with self.assertRaisesRegex(ValueError, "positive finite"):
            audit_declared_reference(payload)

    def test_exchange_local_date_and_ordered_sessions(self):
        payload = demo_coverage_payload()
        payload["snapshots"][0]["decision_at"] = "2024-03-20T00:30:00+08:00"
        self.assertEqual(audit_declared_reference(payload)["snapshot_count"], 2)
        payload = demo_coverage_payload()
        payload["snapshots"].reverse()
        with self.assertRaisesRegex(ValueError, "ascending"):
            audit_declared_reference(payload)
        payload = demo_coverage_payload()
        payload["snapshots"][0]["decision_at"] = "2024-03-21T00:30:00+08:00"
        with self.assertRaisesRegex(ValueError, "exchange-local"):
            audit_declared_reference(payload)

    def test_missing_fact_not_a_zero_and_unknown_is_not_delisted(self):
        payload = demo_coverage_payload()
        payload["facts"][0]["value"] = None
        payload["facts"][0]["missing_reason"] = "NOT_COLLECTED"
        first = audit_declared_reference(payload)["reference_coverage"][0]
        self.assertEqual(first["field_coverage_on_declared_eligible"]["roe"]["DECLARED_MISSING"],
                         ["A"])
        self.assertEqual(first["known_ineligible"], ["C"])
        self.assertEqual(first["unknown_membership"], ["B"])

    def test_real_ohlc_sample_is_468_bars_but_full_denominator_unknown(self):
        report = audit_real_four_stock_snapshot()
        self.assertEqual(report["source_kind"],
                         "REAL_RETROSPECTIVE_OHLC_SELECTED_FOUR_A_SHARES")
        self.assertEqual(report["observed_security_count"], 4)
        self.assertEqual(report["observed_security_sessions"], 468)
        self.assertEqual(report["observed_date_union_sessions"], 117)
        self.assertEqual(report["common_observed_date_count"], 117)
        self.assertEqual(report["sample_internal_coverage_fraction"], 1.0)
        self.assertIsNone(report["full_market_denominator"])
        self.assertIsNone(report["full_market_coverage_percent"])
        self.assertFalse(report["official_exchange_calendar_verified"])
        self.assertFalse(report["historical_full_universe_verified"])
        self.assertFalse(report["historical_pit_verified"])
        self.assertEqual(report["source_layers"]["OHLC"]["csv_hash_integrity"], "PASS")
        self.assertEqual(report["source_layers"]["INDUSTRY_PIT"]["historical_coverage"],
                         "NOT_PROVIDED")
        self.assertIn("2026-11-11", report["capture_timestamp"])

    def test_cli_json_real_and_synthetic_and_local_reports(self):
        command = [sys.executable, "examples/advanced_universe_coverage_lab.py", "--json"]
        synthetic = subprocess.run(command, cwd=ROOT, text=True,
                                   capture_output=True, check=True)
        self.assertEqual(json.loads(synthetic.stdout)["snapshot_count"], 2)
        actual = subprocess.run(command + ["--real-teaching"], cwd=ROOT, text=True,
                                capture_output=True, check=True)
        self.assertEqual(json.loads(actual.stdout)["observed_security_sessions"], 468)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "my_local_unverified.json"
            path.write_text(json.dumps(demo_coverage_payload()), encoding="utf-8")
            local = subprocess.run(command + ["--input", str(path)],
                                   cwd=ROOT, text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(local.stdout)["input_sha256"],
                             json.loads(synthetic.stdout)["input_sha256"])
            out = Path(d) / "report.json"
            written = subprocess.run([sys.executable,
                "examples/advanced_universe_coverage_lab.py", "--real-teaching",
                "--output", str(out)], cwd=ROOT, text=True, capture_output=True, check=True)
            self.assertTrue(out.is_file())
            self.assertIn("report", written.stdout)
            duplicate = subprocess.run([sys.executable,
                "examples/advanced_universe_coverage_lab.py", "--real-teaching",
                "--output", str(out)], cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("FileExistsError", duplicate.stderr)


if __name__ == "__main__":
    unittest.main()
