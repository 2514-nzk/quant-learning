"""Test false-positive root-cause labels and optional real DuckDB SQL."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from examples.advanced_source_join_probe import (
    EVIDENCE, classify_one, offline_report, probe_private_db, sha256_file
)


class SourceJoinProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_frozen_status_denominator(self):
        r = offline_report(self.evidence)
        self.assertEqual(r["total_snapshot_unjoined"], 60515)
        self.assertEqual(r["sh_sz_on_delist_date"], 52)
        self.assertEqual(r["bj_total_unjoined"], 60463)
        self.assertEqual(r["bj_with_suspend_source_flag"], 19)
        self.assertEqual(r["bj_trading_status_unknown"], 60444)
        self.assertFalse(r["source_daily_table_directly_inspected"])

    def test_direct_precedes_alias_and_source_suspension(self):
        self.assertEqual(classify_one(
            exchange="BJ", direct_source=True, alias_count=1,
            on_delist_date=False, suspend_flag=True),
            "SOURCE_DIRECT_PRESENT_SNAPSHOT_JOIN_MISSED")
        self.assertEqual(classify_one(
            exchange="BJ", direct_source=False, alias_count=1,
            on_delist_date=False, suspend_flag=False),
            "COMP_CODE_ALIAS_CANDIDATE")
        self.assertEqual(classify_one(
            exchange="BJ", direct_source=False, alias_count=2,
            on_delist_date=False, suspend_flag=False),
            "AMBIGUOUS_COMP_CODE_ALIASES")

    def test_delist_member_boundary_not_evidence_of_missing_trade(self):
        self.assertEqual(classify_one(
            exchange="SH", direct_source=False, alias_count=0,
            on_delist_date=True, suspend_flag=False),
            "DELIST_DATE_MEMBER_ENDPOINT")
        self.assertEqual(classify_one(
            exchange="SZ", direct_source=False, alias_count=0,
            on_delist_date=False, suspend_flag=False),
            "NO_MATCH_IN_CURRENT_SOURCE_DAILY")

    def test_source_suspend_flag_is_not_venue_confirmed(self):
        self.assertEqual(classify_one(
            exchange="BJ", direct_source=False, alias_count=0,
            on_delist_date=False, suspend_flag=True),
            "SUSPEND_SOURCE_FLAG_NEEDS_VENUE_CHECK")
        example = self.evidence["followup_cause_audit"][
            "bj_2024_source_suspend_listing_day_public_contradiction"]
        self.assertEqual(example["code"], "920002.BJ")
        self.assertEqual(example["public_actual_ipo_day_close"], 67.98)
        self.assertFalse(example["resolved_in_local_source"])

    def test_offline_cli_does_not_open_source_or_fetch(self):
        result = subprocess.run(
            [sys.executable, "examples/advanced_source_join_probe.py", "--json"],
            cwd=EVIDENCE.parents[2], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data["mode"], "PUBLIC_FROZEN_COUNTS_ONLY")
        self.assertFalse(data["historical_pit_verified"])
        self.assertFalse(data["source_daily_table_directly_inspected"])

    def test_private_invocation_needs_both_paths(self):
        result = subprocess.run(
            [sys.executable, "examples/advanced_source_join_probe.py",
             "--source-db", "/does/not/exist.duckdb"],
            cwd=EVIDENCE.parents[2], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--source-db and --parquet", result.stderr)

    @unittest.skipUnless(importlib.util.find_spec("duckdb"), "optional duckdb not installed")
    def test_sql_on_synthetic_source_daily_and_membership(self):
        import duckdb
        with tempfile.TemporaryDirectory() as d:
            source_db = Path(d) / "source.duckdb"
            parquet = Path(d) / "fake_universe.parquet"
            conn = duckdb.connect(str(source_db))
            conn.execute("CREATE TABLE daily(ts_code VARCHAR,trade_date VARCHAR)")
            conn.executemany("INSERT INTO daily VALUES (?,?)", [
                ("873806.BJ", "20240621"),
                ("920002.BJ", "20240621"),
                ("873001.BJ", "20240621"),
                ("830001.BJ", "20240621"),
                ("600000.SH", "20240620")])
            conn.execute("CREATE TABLE stock_basic(ts_code VARCHAR, comp_code VARCHAR, exchange VARCHAR)")
            conn.executemany("INSERT INTO stock_basic VALUES (?,?,?)", [
                ("873806.BJ","C1","BSE"),("920806.BJ","C1","BSE"),
                ("920002.BJ","C2","BSE"),
                ("873001.BJ","C3","BSE"),("830001.BJ","C3","BSE"),
                ("920001.BJ","C3","BSE")])
            conn.execute("""CREATE TABLE sample (
                trade_date DATE, code VARCHAR, comp_code VARCHAR,
                exchange VARCHAR, delist_date DATE, has_suspend_record BOOLEAN,
                has_daily_quote BOOLEAN)""")
            conn.executemany("INSERT INTO sample VALUES (?,?,?,?,?,?,?)", [
                ("2024-06-21","920806.BJ","C1","BJ",None,False,False),
                ("2024-06-21","920002.BJ","C2","BJ",None,False,False),
                ("2024-06-21","920001.BJ","C3","BJ",None,False,False),
                ("2024-06-21","920999.BJ","C4","BJ",None,True,False),
                ("2024-06-21","920998.BJ","C5","BJ",None,False,False),
                ("2024-06-21","600000.SH","X1","SH","2024-06-21",False,False),
                ("2024-06-21","000001.SZ","X2","SZ","2024-06-22",False,False)])
            conn.execute(f"COPY sample TO '{str(parquet).replace(chr(39),chr(39)*2)}' (FORMAT PARQUET)")
            conn.close()
            synthetic_evidence = {
                "year_2024": {"sha256": sha256_file(parquet),
                              "exchange_quote_rows": {
                                  "BJ": {"quote_missing": 5},
                                  "SH": {"quote_missing": 1},
                                  "SZ": {"quote_missing": 1}}}
            }
            report = probe_private_db(source_db, parquet, synthetic_evidence)
            result = {(x["exchange"], x["classification"]):x["security_days"]
                      for x in report["snapshot_unjoined_by_cause"]}
            self.assertEqual(result[("BJ", "COMP_CODE_ALIAS_CANDIDATE")], 1)
            self.assertEqual(result[("BJ", "SOURCE_DIRECT_PRESENT_SNAPSHOT_JOIN_MISSED")], 1)
            self.assertEqual(result[("BJ", "AMBIGUOUS_COMP_CODE_ALIASES")], 1)
            self.assertEqual(result[("BJ", "SUSPEND_SOURCE_FLAG_NEEDS_VENUE_CHECK")], 1)
            self.assertEqual(result[("BJ", "NO_MATCH_IN_CURRENT_SOURCE_DAILY")], 1)
            self.assertEqual(result[("SH", "DELIST_DATE_MEMBER_ENDPOINT")], 1)
            self.assertEqual(result[("SZ", "NO_MATCH_IN_CURRENT_SOURCE_DAILY")], 1)
            cases = {(x["member_code"],x["source_code"]):x["source_daily_rows"]
                     for x in report["public_case_source_keys"]}
            self.assertEqual(cases[("920806.BJ","873806.BJ")], 1)
            self.assertEqual(cases[("920002.BJ","920002.BJ")], 1)
            self.assertTrue(report["source_daily_table_directly_inspected"])
            self.assertFalse(report["historical_pit_verified"])


if __name__ == "__main__":
    unittest.main()
