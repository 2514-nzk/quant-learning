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
                self.assertRegex(body, r"返回 \[[^\]]*目录\]\(README\.md\)")

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

    def test_introductory_math_is_typeset_and_explained(self):
        intro = self.read("01_research_protocol")
        self.assertNotIn("IC_t = Spearman", intro)
        for token in (r"\operatorname{Spearman}", r"H_0:\quad E[IC_t]=0",
                      r"H_1:\quad E[IC_t]>0", "因子名次", "收益名次",
                      "样本平均", "完整的单侧原假设"):
            self.assertIn(token, intro)
        chapter = self.read("02_math_statistics")
        self.assertLess(chapter.index("阅读准备｜先认识这些数学符号"),
                        chapter.index("## 1. 概率论"))
        self.assertIn("70 ÷ 250 = 28%", chapter)
        self.assertIn("0.20 ÷ 10 = 0.02", chapter)
        self.assertAlmostEqual(1 - 6 * (0 + 1 + 1 + 0) / (4 * (4**2 - 1)), .8)
        self.assertAlmostEqual((.12 - .04 + .06 + .02 + .09) / 5, .05)

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

class ClassroomResearchTests(unittest.TestCase):
    def test_reproducible_panel_and_no_future_feature(self):
        from examples.rev20_classroom_lab import make_panel, signal_snapshot, report
        panel = make_panel()
        self.assertEqual(len(panel), 40)
        original = signal_snapshot(panel, 20)
        panel["S01"]["close"][21:] = [999.0] * len(panel["S01"]["close"][21:])
        self.assertEqual(original, signal_snapshot(panel, 20))
        r = report()
        self.assertEqual(r, report())
        self.assertEqual(r["source_kind"], "SYNTHETIC_ONLY")
        self.assertEqual(len(r["weeks"]), 24)
        self.assertEqual([w["signal"] for w in r["weeks"]], list(range(20, 136, 5)))
        self.assertNotIn(75, r["trainable_at_first_validation"])
        self.assertIn(70, r["trainable_at_first_validation"])
        self.assertTrue(all(w["label_available"] == w["signal"]+6 for w in r["weeks"]))
        for w in r["weeks"]:
            self.assertEqual(len(w["scores"])+len(w["excluded"]), 40)
            self.assertEqual(len(w["labels"])+len(w["missing_labels"]), w["eligible"])
            if w["missing_labels"]:
                self.assertIsNone(w["gross_difference"])

    def test_pit_split_dividend_and_fee_counterexamples(self):
        from examples.rev20_classroom_lab import pitfalls, spearman, make_panel, signal_snapshot
        p = pitfalls()
        self.assertEqual(p["pit"], {"correct": .10, "wrong_latest": .15})
        self.assertEqual(p["split"]["raw_return"], -.5)
        self.assertEqual(p["split"]["adjusted_return"], 0)
        self.assertEqual(p["split"]["before"], p["split"]["after"])
        self.assertEqual(p["dividend"]["total_return"], 0)
        self.assertEqual(p["blocked_buy"]["filled"], 0)
        self.assertLess(p["fee_example"]["net_pnl"], 0)
        self.assertAlmostEqual(spearman([1,2,3,4], [1,3,2,4]), .8)
        self.assertIsNone(spearman([1,1], [2,3]))
        panel = make_panel()
        self.assertEqual(signal_snapshot(panel, 20)[1]["S39"], "OUTSIDE_LISTING")
        self.assertEqual(signal_snapshot(panel, 55)[1]["S39"], "SHORT_HISTORY")
        self.assertEqual(signal_snapshot(panel, 80)[1]["S38"], "ST_POLICY")
        self.assertEqual(signal_snapshot(panel, 95)[1]["S40"], "OUTSIDE_LISTING")


if __name__ == "__main__":
    unittest.main()
