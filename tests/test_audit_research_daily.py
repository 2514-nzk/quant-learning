import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_research_daily import audit


class AuditResearchDailyTests(unittest.TestCase):
    def test_audit_counts_and_hashes_both_provider_schemas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "snapshot"
            (root / "raw").mkdir(parents=True)
            (root / "qfq").mkdir()
            (root / "universe.csv").write_text(
                "symbol,name\n600519,Moutai\n000001,Bank\n", encoding="utf-8"
            )
            em = root / "raw" / "600519.csv"
            em.write_text(
                "日期,开盘,最高,最低,收盘,成交量\n2024-01-02,10,11,9,10,100\n",
                encoding="utf-8",
            )
            sina = root / "qfq" / "600519.csv"
            sina.write_text(
                "date,open,high,low,close,volume\n2024-01-02,10,11,9,-0.1,100\n",
                encoding="utf-8",
            )
            items = []
            for symbol, adjust, path, source, rows in (
                ("600519","raw","raw/600519.csv","akshare.stock_zh_a_hist_em",1),
                ("600519","qfq","qfq/600519.csv","akshare.stock_zh_a_hist_sina",1),
            ):
                file = root / path
                items.append({
                    "symbol":symbol,"adjust":adjust,"path":path,"source":source,
                    "rows":rows,"sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
                    "status":"OK",
                })
            (root / "manifest.json").write_text(json.dumps({
                "started_at":"2026-11-24T00:00:00+00:00",
                "finished_at":"2026-11-24T00:10:00+00:00",
                "start":"20160101","end":"20251231",
                "universe_source":{"type":"CURRENT_CSI300_RETROSPECTIVE_FIXED_SAMPLE"},
                "historical_pit_proven":False,
                "historical_dynamic_membership_proven":False,
                "expected_files":4,"successful_files":2,"items":items,
            }),encoding="utf-8")
            output = Path(tmp) / "audit.md"
            result = audit(root, output)
            self.assertTrue(result["integrity_ok"])
            self.assertFalse(result["collection_complete"])
            self.assertEqual(result["universe_count"],2)
            self.assertEqual(result["actual_rows"],2)
            self.assertEqual(result["complete_raw_qfq_pairs"],1)
            self.assertEqual(result["nonpositive_qfq_close_rows"],1)
            self.assertIn("不是 2016—2025 年逐期历史成分",output.read_text("utf-8"))

    def test_missing_manifest_is_reported_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            output = Path(tmp) / "audit.md"
            result = audit(root, output)
            self.assertFalse(result["manifest_found"])
            self.assertIn("未生成 manifest",output.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
