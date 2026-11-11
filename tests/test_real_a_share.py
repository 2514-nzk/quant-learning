"""Test AkShare data normalization and SVG rendering with *fake test fixture* rows.

Fake rows are used only in tests. Real charts must come from the AKShare collector.
"""
import csv
import hashlib
import io
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.collect_real_a_share import (
    FIELDS, csv_text, moving_average, render_svg, standardized_rows, write_snapshot,
)
from examples.real_kline_lab import explain

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "real_a_share"


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows
        self.columns = list(rows[0]) if rows else []

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


def fake_rows(provider="em"):
    value = []
    for i in range(55):
        day = date(2024, 1, 2) + timedelta(days=i)
        o = 10 + i * .1
        value.append({
            ("日期" if provider == "em" else "date"): day.isoformat(),
            ("开盘" if provider == "em" else "open"): o,
            ("最高" if provider == "em" else "high"): o + .25,
            ("最低" if provider == "em" else "low"): o - .25,
            ("收盘" if provider == "em" else "close"): o + .05,
            ("成交量" if provider == "em" else "volume"): 100 if provider == "em" else 10000,
            ("成交额" if provider == "em" else "amount"): 100000,
        })
    return value


class AkShareKlineTests(unittest.TestCase):
    def test_roundtrip_prices_and_normalized_volume(self):
        em = standardized_rows(FakeFrame(fake_rows()), "000001", "平安银行", "akshare.stock_zh_a_hist")
        sina = standardized_rows(FakeFrame(fake_rows("sina")), "000001", "平安银行", "akshare.stock_zh_a_daily")
        self.assertEqual(len(em), 55)
        self.assertEqual(em[0]["trade_date"], "2024-01-02")
        self.assertEqual(em[0]["volume_lots"], "100.00")
        self.assertEqual(sina[0]["volume_lots"], "100.00")
        turnover_rows = fake_rows("sina")
        turnover_rows[0]["turnover"] = .006
        converted = standardized_rows(FakeFrame(turnover_rows), "000001", "平安银行", "akshare.stock_zh_a_daily")
        self.assertEqual(converted[0]["turnover_pct"], "0.6000")
        self.assertEqual(em[-1]["turnover_pct"], "")

    def test_refuse_inconsistent_candle_and_duplicate_date(self):
        rows = fake_rows()
        rows[0]["最高"] = rows[0]["开盘"] - 1
        with self.assertRaises(ValueError):
            standardized_rows(FakeFrame(rows), "000001", "平安银行", "akshare.stock_zh_a_hist")
        duplicate = fake_rows()
        duplicate[1]["日期"] = duplicate[0]["日期"]
        with self.assertRaisesRegex(ValueError, "duplicated"):
            standardized_rows(FakeFrame(duplicate), "000001", "平安银行", "akshare.stock_zh_a_hist")

    def test_ma_is_backward_only(self):
        data = [10., 11., 12., 13., 14., 15.]
        self.assertEqual(moving_average(data, 3), [None, None, 11., 12., 13., 14.])

    def test_svg_is_static_and_metadata_has_checksum(self):
        rows = standardized_rows(FakeFrame(fake_rows()), "000001", "平安银行", "akshare.stock_zh_a_hist")
        svg = render_svg(rows, "000001", "平安银行", "akshare.stock_zh_a_hist")
        self.assertTrue(svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"'))
        self.assertIn("不复权", svg)
        self.assertIn("MA5", svg)
        self.assertIn("MA20", svg)
        self.assertNotIn("<script", svg)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            report = write_snapshot(
                base / "data", base / "charts",
                [("000001", "平安银行", "akshare.stock_zh_a_hist", rows)],
                "test-version",
            )
            record = report["items"][0]
            csv_bytes = (base / "data" / "000001.csv").read_bytes()
            self.assertEqual(record["csv_sha256"], hashlib.sha256(csv_bytes).hexdigest())
            self.assertTrue((base / "charts" / "000001.svg").is_file())
            self.assertEqual(len(list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))), 55)

    def test_real_worked_examples_from_snapshot(self):
        if not (SNAPSHOT / "manifest.json").exists():
            self.skipTest("Actual AKShare snapshot not yet captured")
        bank = explain("000001")
        self.assertEqual(bank["date"], "2024-06-28")
        self.assertAlmostEqual(bank["open"], 10.10)
        self.assertAlmostEqual(bank["high"], 10.26)
        self.assertAlmostEqual(bank["low"], 10.09)
        self.assertAlmostEqual(bank["close"], 10.15)
        self.assertAlmostEqual(bank["ma5"], 10.084)
        self.assertAlmostEqual(bank["mom5_pct"], 1.50)
        moutai = explain("600519")
        self.assertAlmostEqual(moutai["close"], 1467.39)
        self.assertAlmostEqual(moutai["ma5"], 1482.06)
        catl = explain("300750")
        self.assertAlmostEqual(catl["mom5_pct"], -2.7705767984, places=5)

    def test_reading_site_includes_real_charts(self):
        chapter = ROOT / "教程" / "真实A股K线_入门实例.md"
        self.assertTrue(chapter.is_file())
        content = chapter.read_text(encoding="utf-8")
        for symbol in ("000001", "600519", "300750"):
            self.assertIn(f"../reader/assets/real-a-share/{symbol}.svg", content)
            self.assertTrue((ROOT / "reader" / "assets" / "real-a-share" / f"{symbol}.svg").exists())
        index = (ROOT / "教程" / "README.md").read_text(encoding="utf-8")
        self.assertIn("真实A股K线_入门实例.md", index)

    def test_saved_real_snapshot_if_present(self):
        manifest_path = SNAPSHOT / "manifest.json"
        if not manifest_path.exists():
            self.skipTest("AKShare capture hasn't produced a real snapshot yet")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["retriever"], "AKShare")
        self.assertEqual(manifest["adjust"], "none")
        self.assertEqual({x["symbol"] for x in manifest["items"]}, {"000001", "600519", "300750"})
        for item in manifest["items"]:
            data = (SNAPSHOT / (item["symbol"] + ".csv")).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["csv_sha256"])
            records = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
            self.assertGreaterEqual(len(records), 45)
            self.assertEqual(set(records[0]), set(FIELDS))
            self.assertTrue((ROOT / "reader/assets/real-a-share" / (item["symbol"] + ".svg")).is_file())


if __name__ == "__main__":
    unittest.main()
