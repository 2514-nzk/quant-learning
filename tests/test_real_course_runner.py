"""Regression checks: course narrative, stored OHLC and the browser lab agree."""
import json
import unittest
from pathlib import Path

from scripts.build_real_teaching_case import calculate_case, load_bars
from examples.real_stock_learner import rank_ic, summarize
from reader.build_reader import collect_documents, RUNNABLE_SCRIPTS, RUNNABLE_DATA, LABS

ROOT = Path(__file__).resolve().parents[1]


class RealStockCourseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = json.loads((ROOT / "data/real_a_share/teaching_case.json").read_text("utf-8"))
        cls.rebuilt = calculate_case(load_bars())

    def test_price_derived_case_matches_original_snapshot(self):
        self.assertEqual(self.saved["stocks"], self.rebuilt["stocks"])
        self.assertEqual(len(self.saved["rounds"]), 18)
        self.assertEqual(self.saved["rounds"], self.rebuilt["rounds"])
        self.assertEqual(self.saved["intro"], self.rebuilt["intro"])

    def test_real_example_and_lot_arithmetic(self):
        intro = self.saved["intro"]
        self.assertEqual([x["name"] for x in intro["rows"][:2]], ["寒武纪", "宁德时代"])
        self.assertAlmostEqual(intro["top2_gross"] * 100, -4.5661309, places=4)
        self.assertAlmostEqual(intro["all4_gross"] * 100, -1.478199, places=4)
        self.assertAlmostEqual(intro["lot_uninvested_cash"], 11860)
        self.assertEqual(intro["lot_shares"], {"688256": 2300, "300750": 2700})
        self.assertAlmostEqual(intro["lot_end"], 954882)
        self.assertAlmostEqual(rank_ic(intro["rows"]), -1.0)

    def test_time_split_and_real_mean_rank_ic(self):
        rounds = self.saved["rounds"]
        self.assertEqual(len(rounds[:10]), 10)
        self.assertEqual(len(rounds[10:14]), 4)
        self.assertEqual(len(rounds[14:]), 4)
        mean_ic = sum(rank_ic(item["rows"]) for item in rounds)/len(rounds)
        self.assertAlmostEqual(mean_ic, -0.1222222222222222)
        all_rounds = summarize(rounds)
        self.assertAlmostEqual(all_rounds["selected_total_pct"], 14.85867224, places=4)

    def test_browser_labs_use_actual_case_only(self):
        self.assertEqual(RUNNABLE_SCRIPTS, ["examples/real_stock_learner.py"])
        self.assertEqual(RUNNABLE_DATA, ["data/real_a_share/teaching_case.json"])
        for path in ("教程/真实_Python入门.md", "教程/真实_08_单因子评价.md", "教程/真实_16_综合练习.md"):
            self.assertIn(path, LABS)
            self.assertEqual(LABS[path]["files"], RUNNABLE_DATA)
        docs = collect_documents()
        self.assertEqual(len(docs), 21)
        self.assertTrue(all(d["path"].startswith("教程/真实_") for d in docs))

    def test_main_course_images_are_checked_in(self):
        for symbol in ("600519", "688256", "300750", "002594"):
            self.assertTrue((ROOT / "reader/assets/real-a-share" / f"{symbol}.svg").is_file())
        main_text = "\n".join(d["content"] for d in collect_documents())
        for symbol in ("600519", "688256", "300750", "002594"):
            self.assertIn(f"real-a-share/{symbol}.svg", main_text) if symbol in ("600519","688256","300750") else self.assertIn("比亚迪", main_text)


if __name__ == "__main__":
    unittest.main()
