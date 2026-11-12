"""Protect the concept-first, verified-real-market teaching sequence."""
import csv
import json
import re
import unittest
from pathlib import Path
from reader.build_reader import collect_documents

ROOT=Path(__file__).resolve().parents[1]
COURSE=ROOT/"教程"

class LearningFlowTests(unittest.TestCase):
    def test_all_main_chapter_titles_match_sidebar_order(self):
        docs=collect_documents()
        chapters=[d for d in docs if "第 " in d["title"] and "章" in d["title"]]
        self.assertEqual(len(chapters),16)
        for n,doc in enumerate(chapters,1):
            title=doc["content"].splitlines()[0]
            self.assertTrue(title.startswith(f"# 第 {n} 章｜"),(n,title))
            self.assertIn("## 1.",doc["content"],doc["path"])

    def test_no_disguised_synthetic_stock_examples_in_main_track(self):
        docs=collect_documents()
        text="\n".join(d["content"] for d in docs)
        self.assertNotIn("A、B、C、D",text)
        self.assertNotIn("虚构股票 A",text)
        self.assertNotIn("8,000 元虚拟资金",text)
        for name in ("贵州茅台","寒武纪","宁德时代","比亚迪"):
            self.assertIn(name,text)
        self.assertIn("1,000,000",text)

    def test_2024_ohlc_was_checked_in_not_made_up(self):
        saved=json.loads((ROOT/"data/real_a_share/teaching_case.json").read_text("utf-8"))
        self.assertEqual(set(saved["stocks"]),{"600519","688256","300750","002594"})
        self.assertEqual(len(saved["rounds"]),18)
        intro=saved["intro"]
        self.assertEqual(intro["signal_date"],"2024-06-21")
        self.assertEqual(intro["entry_date"],"2024-06-24")
        self.assertEqual(intro["exit_date"],"2024-06-28")
        self.assertEqual([r["name"] for r in intro["rows"][:2]],["寒武纪","宁德时代"])
        self.assertAlmostEqual(intro["theoretical_end"],954338.69,places=2)
        self.assertAlmostEqual(intro["benchmark_end"],985218.01,places=2)
        self.assertAlmostEqual(intro["lot_end"],954882,places=2)
        intro_doc=(COURSE/"真实_起步一课.md").read_text("utf-8")
        for amt in ("954,338.69","985,218.01","215.29","198.67"):
            self.assertIn(amt,intro_doc)

    def test_real_historical_financial_report_is_used_correctly(self):
        chapter = (COURSE / "真实_06_财务与预处理.md").read_text("utf-8")
        for term in ("宁德时代", "2023 年年度报告", "2024 年 3 月 15 日", "441.21 亿元", "24.04%", "报告期", "披露日期"):
            self.assertIn(term, chapter)
        timing = (COURSE / "真实_07_时间切分与泄漏.md").read_text("utf-8")
        for term in ("2024 年 2 月 1 日", "2024 年 6 月 21 日", "2024 年 3 月 15 日", "PIT"):
            self.assertIn(term, timing)
        self.assertIn("深交所披露文件", chapter)
        self.assertNotIn("不能凭空给它们配上", chapter)
        self.assertLess(chapter.index("## 2. 历史财报能拿到吗"), chapter.index("## 3. 什么叫预处理"))

    def test_real_price_terms_appear_before_advanced_statistics(self):
        docs=[d["path"] for d in collect_documents()]
        self.assertLess(docs.index("教程/真实_03_历史K线与时点.md"),
                        docs.index("教程/真实_05_均线与算子.md"))
        self.assertLess(docs.index("教程/真实_05_均线与算子.md"),
                        docs.index("教程/真实_07_时间切分与泄漏.md"))
        self.assertLess(docs.index("教程/真实_07_时间切分与泄漏.md"),
                        docs.index("教程/真实_08_单因子评价.md"))
        self.assertLess(docs.index("教程/真实_08_单因子评价.md"),
                        docs.index("教程/真实_11_线性模型.md"))


if __name__=="__main__":
    unittest.main()
