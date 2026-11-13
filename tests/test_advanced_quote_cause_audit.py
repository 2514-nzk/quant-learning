"""Keep market reality, local join misses and remote API silence separate."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

from examples.advanced_quote_cause_audit import (
    EVIDENCE, CASES, extract_exact_date, fetch_case, offline_summary,
)


class QuoteCauseAuditTests(unittest.TestCase):
    def test_offline_local_triage(self):
        evidence = json.loads(EVIDENCE.read_text("utf-8"))
        result = offline_summary(evidence)
        self.assertEqual(result["sh_sz_unjoined_and_equal_delist_day"], 52)
        self.assertEqual(result["bj_unjoined"], 60463)
        self.assertFalse(result["akshare_queried"])
        self.assertFalse(result["historical_pit_proven"])

    def test_date_required_missing_not_zero_return(self):
        data = [{"日期": "2024-06-20", "收盘": 12.2}]
        self.assertEqual(extract_exact_date(data, "2024-06-21")["status"],
                         "NOT_RETURNED_CANNOT_INFER_HALTED_OR_DELISTED")
        self.assertEqual(extract_exact_date(
            [{"日期": "2024-06-21", "收盘": 52.01}], "2024-06-21")["close"], 52.01)

    def test_simulated_akshare_historical_fallback_checks_both_codes(self):
        class FakeAK:
            @staticmethod
            def stock_zh_a_hist(**kw):
                if kw["symbol"] == "873806":
                    return [{"日期": "2024-06-21", "收盘": 9.44}]
                return []
        report = fetch_case(FakeAK(), CASES[0])
        self.assertEqual(report["attempted_symbols"], ["873806", "920806"])
        self.assertTrue(report["api_matches_2024_public_report"])
        self.assertEqual(report["interpretation"], "INDEPENDENT_QUOTE_PRESENT")

    def test_missing_akshare_query_does_not_prove_suspension(self):
        class FakeAK:
            @staticmethod
            def stock_zh_a_hist(**kwargs):
                return []
        report = fetch_case(FakeAK(), CASES[2])
        self.assertFalse(report["api_price_observed"])
        self.assertIsNone(report["api_matches_2024_public_report"])
        self.assertEqual(report["interpretation"],
                         "NOT_CONFIRMED_BY_API_QUERY_NO_ABSENCE_INFERENCE")

    def test_symbol_920002_direct_2024_trade_is_considered(self):
        self.assertEqual(CASES[2]["canonical_code"], CASES[2]["historical_code"])
        self.assertEqual(CASES[2]["public_close"], 52.01)

    def test_live_akshare_results_are_recorded_with_public_crosscheck(self):
        evidence = json.loads(EVIDENCE.read_text("utf-8"))
        actual = evidence["followup_cause_audit"]["akshare_verification"]
        self.assertEqual(actual["workflow_run_id"], 43378034226)
        self.assertEqual(len(actual["results"]), 3)
        self.assertEqual(
            [(r["company"], r["close"]) for r in actual["results"]],
            [("云星宇", 9.44), ("纬达光电", 8.18), ("万达轴承", 52.01)]
        )
        self.assertTrue(all(r["matched_dated_public_report"]
                            for r in actual["results"]))
        self.assertFalse(
            evidence["followup_cause_audit"]["full_daily_relation_content_verified"]
        )

    def test_no_network_by_default(self):
        result = subprocess.run(
            [sys.executable, "examples/advanced_quote_cause_audit.py", "--json"],
            cwd=EVIDENCE.parents[2], capture_output=True, text=True, check=True)
        value = json.loads(result.stdout)
        self.assertFalse(value["akshare_queried"])
        self.assertEqual(value["sh_sz_unjoined_and_equal_delist_day"], 52)


if __name__ == "__main__":
    unittest.main()
