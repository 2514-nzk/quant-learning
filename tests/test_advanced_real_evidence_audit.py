"""Evidence gate regression tests: real OHLC is not automatically PIT/OOS."""
from __future__ import annotations

import copy
import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from examples.advanced_real_evidence_audit import (
    DATA, audit_timeline, compare_tree, evaluate_case, run_audit,
    validate_snapshot,
)
from scripts.build_real_teaching_case import calculate_case, load_bars


class RealEvidenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = json.loads((DATA / "teaching_case.json").read_text("utf-8"))

    def test_real_snapshot_and_retrospective_evidence_gates(self):
        report = run_audit(reps=150)
        self.assertEqual(len(report["snapshot"]["files"]), 4)
        self.assertTrue(report["snapshot"]["capture_after_market_period"])
        self.assertEqual(report["timeline"]["round_count"], 18)
        self.assertEqual(report["source_kind"],
                         "REAL_OHLC_RETROSPECTIVE_FOUR_PRESELECTED_STOCKS")
        self.assertIn("NOT_INDEPENDENT_OOS", report["evidence_grade"])
        self.assertEqual(report["gates"]["L0_source_file_integrity"], "PASS")
        self.assertEqual(report["gates"]["L4_historical_full_universe"],
                         "FAIL_SELECTED_SURVIVORS")
        self.assertEqual(report["gates"]["L6_independent_OOS"],
                         "FAIL_PREVIOUSLY_EXPLORED")

    def test_analytics_match_known_real_classroom_data(self):
        stats = evaluate_case(self.case["rounds"], reps=150)
        self.assertAlmostEqual(stats["all"]["mean_rank_ic"], -0.1222222222222222)
        self.assertAlmostEqual(stats["all"]["mean_top2_minus_equal4"],
                               .0012386492222222212)
        self.assertEqual(stats["all"]["positive_ic_rounds"], 7)
        self.assertEqual(stats["all"]["top2_outperformance_rounds"], 10)
        self.assertEqual(stats["retrospective_reading_slices_not_oos"]["last_4_already_published"]["rounds"], 4)
        self.assertEqual(stats["method"]["split_status"],
                         "already explored by authors/readers; no untouched OOS")
        self.assertEqual(len(stats["rank_ic"]["observations"]), 18)

    def test_command_line_invocation_matches_test_imports(self):
        process = subprocess.run(
            [sys.executable, "examples/advanced_real_evidence_audit.py",
             "--json", "--resamples", "150"],
            cwd=DATA.parents[1], capture_output=True, text=True, check=True,
        )
        report = json.loads(process.stdout)
        self.assertEqual(report["timeline"]["round_count"], 18)
        self.assertEqual(report["gates"]["L3_2024_historical_PIT_availability"],
                         "NOT_PROVEN")

    def test_fingerprint_tampering_is_caught_before_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            for item in json.loads((DATA / "manifest.json").read_text("utf-8"))["items"]:
                shutil.copyfile(DATA / (item["symbol"] + ".csv"),
                                folder / (item["symbol"] + ".csv"))
            shutil.copyfile(DATA / "manifest.json", folder / "manifest.json")
            original = folder / "002594.csv"
            original.write_bytes(original.read_bytes() + b"\\n")
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                validate_snapshot(folder)

    def test_cached_derived_case_cannot_override_original_prices(self):
        original = copy.deepcopy(self.case)
        original["rounds"][-1]["rows"][0]["forward_return"] += .01
        with self.assertRaisesRegex(ValueError, "derived price calculation drift"):
            compare_tree(original, self.case)

    def test_later_exit_price_does_not_change_prior_signal_momentum(self):
        prices = load_bars()
        fixed = calculate_case(prices)
        altered = copy.deepcopy(prices)
        altered["600519"]["2024-06-28"]["close"] *= 1.04
        changed = calculate_case(altered)
        first = {r["symbol"]:r for r in fixed["rounds"][-1]["rows"]}
        later = {r["symbol"]:r for r in changed["rounds"][-1]["rows"]}
        self.assertEqual(first["600519"]["mom5"], later["600519"]["mom5"])
        self.assertEqual(first["600519"]["rank"], later["600519"]["rank"])
        self.assertNotEqual(first["600519"]["forward_return"],
                            later["600519"]["forward_return"])

    def test_overlap_and_time_travel_are_rejected(self):
        originals = self.case["rounds"]
        self.assertTrue(audit_timeline(originals)["nonoverlap"])
        bad = copy.deepcopy(originals)
        bad[1]["signal_date"] = bad[0]["exit_date"]
        with self.assertRaisesRegex(ValueError, "overlapping"):
            audit_timeline(bad)
        bad = copy.deepcopy(originals)
        bad[0]["rows"][0]["momentum_base_date"] = bad[0]["signal_date"]
        with self.assertRaisesRegex(ValueError, "nonhistorical"):
            audit_timeline(bad)

    def test_block_uncertainty_reproducible_but_not_confirmatory(self):
        a = evaluate_case(self.case["rounds"], reps=200, seed=21)
        b = evaluate_case(self.case["rounds"], reps=200, seed=21)
        self.assertEqual(a["rank_ic"]["circular_block_ci_mean_block3"],
                         b["rank_ic"]["circular_block_ci_mean_block3"])
        self.assertEqual(len(a["rank_ic"]["circular_block_ci_mean_block2"]), 2)
        self.assertEqual(len(a["rank_ic"]["circular_block_ci_mean_block4"]), 2)
        self.assertLess(a["rank_ic"]["leave_one_round_out_mean_range"][0],
                        a["rank_ic"]["leave_one_round_out_mean_range"][1])


if __name__ == "__main__":
    unittest.main()
