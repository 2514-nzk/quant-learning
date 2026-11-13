"""Reject forged/late PIT evidence while keeping user data local."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from examples.advanced_pit_intake_lab import demo_payload, evaluate

ROOT = Path(__file__).resolve().parents[1]


class PITIntakeTests(unittest.TestCase):
    def test_versioned_memberships_facts_and_label_purge(self):
        report = evaluate(demo_payload())
        self.assertEqual(report["evidence_grade"], "SYNTHETIC_ONLY")
        self.assertEqual(report["membership_asof"]["A"], "ELIGIBLE")
        self.assertEqual(report["membership_asof"]["B"], "UNKNOWN_NO_KNOWN_MEMBERSHIP")
        self.assertEqual(report["membership_asof"]["C"], "INELIGIBLE")
        self.assertEqual(report["facts_asof"]["A"]["roe"]["value"], 0.10)
        self.assertEqual(report["facts_asof"]["A"]["roe"]["revision_id"], "A-roe-1")
        self.assertEqual(report["train_labels_eligible"], 1)
        self.assertEqual(report["train_labels_purged"], 1)
        self.assertFalse(report["historical_pit_proven"])
        self.assertFalse(report["source_timestamps_independently_verified"])

    def test_after_cutoff_revision_never_leaks_back(self):
        payload = demo_payload()
        old = evaluate(payload)
        payload["membership_events"][1]["effective_to"] = "2024-02-01"
        payload["facts"][1]["value"] = -4_000_000
        self.assertEqual(evaluate(payload)["facts_asof"]["A"]["roe"],
                         old["facts_asof"]["A"]["roe"])
        self.assertEqual(evaluate(payload)["membership_asof"],
                         old["membership_asof"])

    def test_reject_naive_and_inconsistent_source_time(self):
        payload = demo_payload()
        payload["facts"][0]["source_published_at"] = "2024-03-15T16:00:00"
        with self.assertRaisesRegex(ValueError, "naive"):
            evaluate(payload)
        payload = demo_payload()
        payload["facts"][0]["available_at"] = "2024-03-15T15:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "time order"):
            evaluate(payload)

    def test_missing_provenance_and_duplicate_revision_rejected(self):
        payload = demo_payload()
        del payload["facts"][0]["source_ref"]
        with self.assertRaisesRegex(ValueError, "source_ref"):
            evaluate(payload)
        payload = demo_payload()
        payload["membership_events"].append(copy.deepcopy(payload["membership_events"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate membership"):
            evaluate(payload)
        payload = demo_payload()
        payload["facts"][0]["declared_evidence_sha256"] = "NOT_A_HASH"
        with self.assertRaisesRegex(ValueError, "SHA256"):
            evaluate(payload)

    def test_missing_is_not_zero_and_unknown_not_inactive(self):
        payload = demo_payload()
        payload["facts"][0]["value"] = None
        with self.assertRaisesRegex(ValueError, "missing_reason"):
            evaluate(payload)
        payload = demo_payload()
        payload["facts"][0]["value"] = None
        payload["facts"][0]["missing_reason"] = "NOT_ANNOUNCED"
        report = evaluate(payload)
        self.assertEqual(report["facts_asof"]["A"]["roe"]["status"],
                         "MISSING_NOT_ANNOUNCED")
        self.assertIsNone(report["facts_asof"]["A"]["roe"]["value"])

    def test_label_leakage_and_exact_boundary(self):
        payload = demo_payload()
        payload["labels"][0]["feature_available_at"] = "2024-03-04T20:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "future feature"):
            evaluate(payload)
        payload = demo_payload()
        payload["labels"][0]["label_available_at"] = "2024-04-03T09:30:00+08:00"
        report = evaluate(payload)
        self.assertEqual(report["train_labels_purged"], 2)
        payload = demo_payload()
        payload["labels"][0]["exit_at"] = "2024-03-04T09:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "timeline"):
            evaluate(payload)

    def test_exchange_local_signal_date_does_not_use_utc_calendar_date(self):
        payload = demo_payload()
        payload["signal_date"] = "2024-03-21"
        payload["decision_at"] = "2024-03-21T00:30:00+08:00"
        report = evaluate(payload)
        self.assertEqual(report["membership_asof"]["A"], "ELIGIBLE")
        self.assertTrue(report["label_gate_is_time_only_not_universe_eligible"])

    def test_user_supplied_times_still_not_verified_pit(self):
        payload = demo_payload()
        payload["data_kind"] = "USER_SUPPLIED_UNVERIFIED"
        payload["universe_scope"] = "HISTORICAL_UNIVERSE_CANDIDATE"
        report = evaluate(payload)
        self.assertEqual(report["evidence_grade"], "USER_DECLARED_TIMES_UNVERIFIED")
        self.assertFalse(report["historical_full_universe_proven"])
        self.assertFalse(report["historical_pit_proven"])

    def test_direct_cli_and_local_json_input(self):
        cmd = [sys.executable, "examples/advanced_pit_intake_lab.py", "--json"]
        process = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(process.stdout)["train_labels_purged"], 1)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "input.json"
            path.write_text(json.dumps(demo_payload(), ensure_ascii=False), encoding="utf-8")
            imported = subprocess.run(cmd + ["--input", str(path)], cwd=ROOT,
                                      capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(imported.stdout)["input_sha256"],
                             json.loads(process.stdout)["input_sha256"])


if __name__ == "__main__":
    unittest.main()
