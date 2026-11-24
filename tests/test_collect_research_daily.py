import csv
import tempfile
import unittest
from pathlib import Path

from scripts.collect_research_daily import collect, symbols, validate, digest


class Frame:
    def __init__(self, columns=None, row=None):
        self.columns = columns or ["日期", "开盘", "最高", "最低", "收盘", "成交量"]
        values = row or ["2020-01-02", 10, 11, 9, 10.5, 100]
        self.rows = [dict(zip(self.columns, values))]
        self.empty = False

    def __len__(self):
        return len(self.rows)

    def to_dict(self, orient):
        return self.rows

    def to_csv(self, path, index, encoding):
        with open(path, "w", encoding=encoding, newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.columns)
            writer.writeheader()
            writer.writerows(self.rows)


class FakeEM:
    __version__ = "test"

    def stock_zh_a_hist_em(self, **kwargs):
        return Frame()

    def stock_zh_a_hist_sina(self, **kwargs):
        raise RuntimeError("not needed")


class BatchTests(unittest.TestCase):
    def test_manifest_and_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            report = collect(
                FakeEM(), {"000001": "A"}, {"type": "TEST"},
                "20200101", "20200103", out, pause=0, attempts=1,
            )
            self.assertEqual(report["successful_files"], 2)
            self.assertEqual(report["expected_files"], 2)
            self.assertTrue(report["all_requests_succeeded"])
            self.assertFalse(report["historical_pit_proven"])
            for row in report["items"]:
                self.assertEqual(row["source"], "akshare.stock_zh_a_hist_em")
                self.assertEqual(row["volume_unit"], "lots")
                self.assertEqual(row["turnover_unit"], "percent")
                self.assertEqual(row["sha256"], digest(out / row["path"]))
            with self.assertRaises(ValueError):
                collect(FakeEM(), {}, {}, "20200101", "20200103", out, 0, 1)

    def test_sina_fallback_and_units(self):
        class Fallback:
            __version__ = "test"

            def stock_zh_a_hist_em(self, **kwargs):
                raise RuntimeError("Eastmoney offline")

            def stock_zh_a_hist_sina(self, **kwargs):
                return Frame(
                    ["date", "open", "high", "low", "close", "volume"],
                    ["2020-01-02", 10, 11, 9, 10.5, 100],
                )
        with tempfile.TemporaryDirectory() as tmp:
            report = collect(
                Fallback(), {"600519": "A"}, {"type": "TEST"},
                "20200101", "20200103", Path(tmp) / "data", pause=0, attempts=1,
            )
            self.assertTrue(report["all_requests_succeeded"])
            self.assertTrue(all(row["source"] == "akshare.stock_zh_a_hist_sina" for row in report["items"]))
            self.assertTrue(all(row["volume_unit"] == "shares" for row in report["items"]))
            self.assertTrue(all(row["turnover_unit"] == "fraction" for row in report["items"]))

    def test_qfq_nonpositive_prices_are_preserved_but_flagged(self):
        frame = Frame(row=["2020-01-02", -0.1, 0.2, -0.3, 0.0, 100])
        first, last, flag = validate(frame, "20200101", "20200103", "akshare.stock_zh_a_hist_em", "qfq")
        self.assertEqual((first, last), ("20200102", "20200102"))
        self.assertTrue(flag)
        with self.assertRaises(ValueError):
            validate(frame, "20200101", "20200103", "akshare.stock_zh_a_hist_em", "raw")

    def test_beijing_a_share_code_uses_eastmoney_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = collect(
                FakeEM(), {"830799": "Beijing"}, {"type": "TEST"},
                "20200101", "20200103", Path(tmp) / "data", pause=0, attempts=1,
            )
            self.assertTrue(report["all_requests_succeeded"])
            self.assertTrue(all(row["source"] == "akshare.stock_zh_a_hist_em" for row in report["items"]))

    def test_invalid_dates_rows_and_codes(self):
        self.assertEqual(list(symbols([{"symbol": "830799"}])), ["830799"])
        with self.assertRaises(ValueError):
            symbols([{"symbol": "1"}])
        with self.assertRaises(ValueError):
            symbols([{"symbol": "000001"}, {"symbol": "000001"}])
        frame = Frame()
        frame.rows.append(frame.rows[0])
        with self.assertRaises(ValueError):
            validate(frame, "20200101", "20200103", "akshare.stock_zh_a_hist_em", "raw")


if __name__ == "__main__":
    unittest.main()
