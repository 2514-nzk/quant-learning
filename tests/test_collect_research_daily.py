import csv
import tempfile
import unittest
from pathlib import Path
from scripts.collect_research_daily import collect, symbols, validate, digest

class Frame:
    columns=["日期","开盘","最高","最低","收盘","成交量"]
    empty=False
    def __init__(self):
        self.rows=[dict(zip(self.columns,["2020-01-02",10,11,9,10.5,100]))]
    def __len__(self):return len(self.rows)
    def to_dict(self,kind):return self.rows
    def to_csv(self,path,index,encoding):
        with open(path,"w",encoding=encoding,newline="") as f:
            w=csv.DictWriter(f,fieldnames=self.columns);w.writeheader();w.writerows(self.rows)

class Fake:
    __version__="test"
    def stock_zh_a_hist(self,**kw):
        if kw["symbol"]=="000002":raise RuntimeError("unavailable")
        return Frame()

class BatchTests(unittest.TestCase):
    def test_manifest_and_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"data"
            report=collect(Fake(),{"000001":"A","000002":"B"},{"type":"TEST"},"20200101","20200103",out,pause=0,attempts=1)
            self.assertEqual(report["successful_files"],2)
            self.assertEqual(report["expected_files"],4)
            self.assertFalse(report["all_requests_succeeded"])
            self.assertFalse(report["historical_pit_proven"])
            for row in report["items"]:
                if row["status"]=="OK":self.assertEqual(row["sha256"],digest(out/row["path"]))
            self.assertFalse((out/"raw/000002.csv").exists())
            with self.assertRaises(ValueError):collect(Fake(),{},{},"20200101","20200103",out,0,1)
    def test_bad_rows(self):
        with self.assertRaises(ValueError):symbols([{"symbol":"1"}])
        with self.assertRaises(ValueError):symbols([{"symbol":"000001"},{"symbol":"000001"}])
        f=Frame();f.rows.append(f.rows[0])
        with self.assertRaises(ValueError):validate(f,"20200101","20200103")

    def test_fallback_source_and_units(self):
        class Fallback:
            def stock_zh_a_hist(self,**kwargs):raise RuntimeError("offline")
            def stock_zh_a_daily(self,**kwargs):
                f=Frame()
                f.columns=["date","open","high","low","close","volume"]
                f.rows=[dict(zip(f.columns,["2020-01-02",10,11,9,10.5,100]))]
                return f
        with tempfile.TemporaryDirectory() as tmp:
            report=collect(Fallback(),{"600519":"A"},{},"20200101","20200103",Path(tmp)/"data",pause=0,attempts=1)
            self.assertTrue(report["all_requests_succeeded"])
            self.assertTrue(all(r["source"]=="akshare.stock_zh_a_daily" and r["volume_unit"]=="shares" for r in report["items"]))
