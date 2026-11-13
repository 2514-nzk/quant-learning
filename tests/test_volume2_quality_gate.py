"""Volume II internal teaching-quality gates; not market verification."""
from __future__ import annotations
import math
import re
import unittest
from pathlib import Path
from urllib.parse import unquote
from examples.advanced_pit_intake_lab import demo_payload, evaluate

ROOT = Path(__file__).resolve().parents[1]
VOL = ROOT / "advanced" / "volume-2"
CHAPTERS = (
    "01_research_protocol", "02_math_statistics", "03_time_series",
    "04_market_rules", "05_pit_data", "06_labels_splits",
    "07_factor_engineering", "08_factor_validation",
    "09_factor_combination", "10_machine_learning", "11_oos_drift",
    "12_portfolio_optimization", "13_backtest_execution",
    "14_reproducible_capstone",
)
QA_STATUS = "状态：教学版 v1 方法与例题内部校审完成"

class VolumeTwoQualityGate(unittest.TestCase):
    def read(self, slug):
        return (VOL / (slug + ".md")).read_text(encoding="utf-8")

    def test_exactly_fourteen_ordered_chapters(self):
        actual = {p.stem for p in VOL.glob("[0-9][0-9]_*.md")}
        self.assertEqual(actual, set(CHAPTERS))
        for number, slug in enumerate(CHAPTERS, 1):
            body = self.read(slug)
            with self.subTest(chapter=slug):
                self.assertRegex(body, rf"(?m)^# 第二卷 · {number:02d}｜")
                headings = [int(x) for x in re.findall(
                    r"(?m)^## (\d+)\. ", body)]
                self.assertTrue(headings)
                self.assertEqual(headings, list(range(1, max(headings) + 1)))
                self.assertIn(QA_STATUS, body)
                self.assertEqual(body.count("### 质量核对｜"), 1)
                self.assertIn("答", body)
                self.assertIn("python examples/", body)
                self.assertIn("返回 [第二卷目录](README.md)", body)

    def test_math_delimiters_and_fences_are_well_formed(self):
        for slug in CHAPTERS:
            body = self.read(slug)
            with self.subTest(chapter=slug):
                self.assertEqual(body.count(r"\["), body.count(r"\]"))
                self.assertEqual(body.count(r"\("), body.count(r"\)"))
                self.assertNotRegex(body, r"(?m)^\[$")
                self.assertNotRegex(body, r"(?m)^N_t\^\{reference\}=#")
                fences = [line for line in body.splitlines()
                          if line.startswith("~~~")]
                self.assertEqual(len(fences) % 2, 0)

    def test_local_markdown_code_and_data_links_exist(self):
        source_files = [VOL / (c + ".md") for c in CHAPTERS] + [
            VOL / "README.md", VOL / "REVIEW_BACKLOG.md",
            VOL / "QUALITY_REVIEW_V1.md",
            VOL / "HISTORICAL_UNIVERSE_SOURCE_AUDIT.md",
        ]
        checked = 0
        for page in source_files:
            for m in re.finditer(r"\[[^\]]+\]\(([^)\s]+)\)",
                                 page.read_text("utf-8")):
                link = unquote(m.group(1)).split("#", 1)[0]
                if not link or link.startswith(("http://", "https://", "mailto:")):
                    continue
                target = (page.parent / link).resolve()
                with self.subTest(page=page.name, link=link):
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.exists(), f"broken link: {link}")
                checked += 1
        self.assertGreaterEqual(checked, 80)

    def test_no_private_research_dependency_in_book(self):
        pages = [VOL / (c + ".md") for c in CHAPTERS] + [
            VOL / "README.md", VOL / "REVIEW_BACKLOG.md",
            VOL / "QUALITY_REVIEW_V1.md",
            VOL / "HISTORICAL_UNIVERSE_SOURCE_AUDIT.md",
        ]
        forbidden = ("PTradePolicy", "xc_tushare_data.duckdb",
                     "local_all_a_2024_aggregate.json",
                     "advanced_source_join_probe.py",
                     "E:/duckdb_data", "E:\\duckdb_data")
        for page in pages:
            text = page.read_text("utf-8")
            with self.subTest(page=page.name):
                for needle in forbidden:
                    self.assertNotIn(needle, text)

    def test_pit_example_matches_frozen_course_fixture(self):
        report = evaluate(demo_payload())
        self.assertEqual(report["membership_asof"]["A"], "ELIGIBLE")
        self.assertEqual(report["membership_asof"]["B"],
                         "UNKNOWN_NO_KNOWN_MEMBERSHIP")
        self.assertEqual(report["membership_asof"]["C"], "INELIGIBLE")
        self.assertEqual(report["facts_asof"]["A"]["roe"]["value"], 0.10)
        self.assertEqual((report["train_labels_eligible"],
                          report["train_labels_purged"]), (1, 1))
        self.assertFalse(report["historical_pit_proven"])
        chapter = self.read("05_pit_data")
        for token in ("2024-03-15 16:20", "2024-04-10 16:20",
                      "2024-03-25 16:30", "NOT_COLLECTED", "0.10", "0.15"):
            self.assertIn(token, chapter)

    def test_worked_example_math(self):
        self.assertAlmostEqual(.7 * .1 / (.7 * .1 + .2 * .9), .28)
        self.assertAlmostEqual((4 / 3) / (2 / 3 + 1), .8)
        self.assertAlmostEqual(math.sqrt((.25 - .1875) / 4), .125)
        self.assertAlmostEqual(math.sqrt(1 / 3) / 2, .288675134594813)
        self.assertAlmostEqual(.4 * .08 + .4 * .12 -
                               (.4**2 * .04 + .4**2 * .09), .0592)
        after_buy = 10000 - 100 * 10 - 5
        self.assertEqual(after_buy, 8995)
        self.assertEqual(after_buy + 100 * 10.2, 10015)
        self.assertAlmostEqual(after_buy + 100 * 10.2 - 5 -
                               .001 * 100 * 10.2, 10008.98)

    def test_rules_and_teaching_versus_research_evidence(self):
        rules = self.read("04_market_rules")
        for token in ("2026-04-24", "2026-07-06", "3.7.1–3.7.10",
                      "www.sse.com.cn", "www.szse.cn", "www.bse.cn"):
            self.assertIn(token, rules)
        quality = (VOL / "QUALITY_REVIEW_V1.md").read_text("utf-8")
        for token in ("14/14", "不代表独立外部同行评审", "真实四股",
                      "SYNTHETIC_ONLY"):
            self.assertIn(token, quality)
        index = (VOL / "README.md").read_text("utf-8")
        self.assertEqual(index.count("教学版 v1 / 实验可复算"), 14)
        self.assertIn("(QUALITY_REVIEW_V1.md)", index)
        self.assertIn("14 章教学版 v1",
                      (ROOT / "README.md").read_text("utf-8"))

    def test_public_reader_labels_not_stale(self):
        html = (ROOT / "reader/index.html").read_text("utf-8")
        js = (ROOT / "reader/app.js").read_text("utf-8")
        self.assertIn("第二卷 14 章教学版 v1", html)
        self.assertNotIn("第二卷为教学初稿", html)
        self.assertIn("教学版 v1", js)
        self.assertNotIn("初稿试读", js)

if __name__ == "__main__":
    unittest.main()
