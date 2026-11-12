"""Check factual accounting data, cash-flow ratios and book order in CATL lesson."""
import json
import unittest
from pathlib import Path

from reader.build_reader import collect_documents
from examples.financial_quality_lab import calculate, load, report

ROOT=Path(__file__).resolve().parents[1]
LESSON=ROOT/"教程"/"真实_06a_合并报表与财务质量.md"

class FinancialQualityTests(unittest.TestCase):
    def test_original_report_numbers_and_reconciliation(self):
        data=load()
        self.assertEqual(data["symbol"],"300750")
        self.assertEqual(data["unit"],"万元")
        result=calculate(data)
        self.assertAlmostEqual(result["parent_equity_100m"],1977.080524,places=6)
        self.assertAlmostEqual(result["minority_equity_100m"],221.750982,places=6)
        self.assertAlmostEqual(result["total_equity_100m"],2198.831506,places=6)
        self.assertAlmostEqual(result["parent_profit_100m"],441.212483,places=6)
        self.assertAlmostEqual(result["minority_profit_100m"],26.397861,places=6)
        self.assertAlmostEqual(result["consolidated_profit_100m"],467.610345,places=6)
        self.assertAlmostEqual(result["cfo_to_consolidated_profit"],1.9851169973,places=7)
        self.assertAlmostEqual(result["receivables_growth_pct"],10.4439887434,places=6)
        self.assertAlmostEqual(result["inventory_growth_pct"],-40.7401295556,places=6)
        self.assertAlmostEqual(result["revenue_growth_pct"],22.0098541517,places=6)
        self.assertIn("真实合并财务报表",report(data,result))

    def test_lesson_is_after_financial_basics_before_time_split(self):
        docs=collect_documents()
        paths=[d["path"] for d in docs]
        self.assertEqual(len(docs),23)
        self.assertEqual(paths.index("教程/真实_06a_合并报表与财务质量.md"),
                         paths.index("教程/真实_06_财务与预处理.md")+1)
        self.assertLess(paths.index("教程/真实_06a_合并报表与财务质量.md"),
                        paths.index("教程/真实_07_时间切分与泄漏.md"))
        lesson=next(d for d in docs if d["path"].endswith("真实_06a_合并报表与财务质量.md"))
        self.assertEqual(lesson["group"],"第二循环 · 从行情到因子评价")

    def test_intro_defines_terms_and_fake_hypotheticals_are_separate(self):
        text=LESSON.read_text(encoding="utf-8")
        for key in ("**少数股东**","**合并报表**","归母净利润",
                    "1,977.08","221.75","2,198.83","467.61","441.21",
                    "26.40","928.26","1.99","640.21","454.34",
                    "10.44%","-40.74%","24.04%"):
            with self.subTest(key=key):
                self.assertIn(key,text)
        self.assertIn("财务质量分析是寻找经营数据之间的联系",text)
        self.assertIn("怎样把更多财务项目联系起来看",text)
        self.assertIn("报表附注解释各项指标的变化",text)
        self.assertIn("2024 年 3 月披露",text)
        self.assertIn("报告期与披露日期",text)
        self.assertIn("data/financial_reports/catl_2023_annual_excerpt.json",text)
        self.assertIn("python examples/financial_quality_lab.py",text)
        self.assertIn("真实_07_时间切分与泄漏.md",text)

    def test_neutral_instructional_language_across_lesson_and_exercise(self):
        source=json.loads((ROOT/"data/financial_reports/catl_2023_annual_excerpt.json").read_text("utf-8"))
        self.assertIn("static.cninfo.com.cn",source["document_url"])
        self.assertEqual(source["years"]["2023"]["reported_weighted_average_roe_percent"],24.04)
        texts = (
            LESSON.read_text("utf-8"),
            (ROOT/"教程/README.md").read_text("utf-8"),
            (ROOT/"README.md").read_text("utf-8"),
            (ROOT/"examples/financial_quality_lab.py").read_text("utf-8"),
            json.dumps(source, ensure_ascii=False),
        )
        for term in ("造假","舞弊","财务真假","指控"):
            for i, content in enumerate(texts):
                with self.subTest(term=term, source=i):
                    self.assertNotIn(term, content)
        data=load()
        bad=json.loads(json.dumps(data))
        bad["years"]["2023"]["minority_equity"]+=100
        with self.assertRaisesRegex(ValueError,"合并权益"):
            calculate(bad)


if __name__=="__main__":
    unittest.main()
