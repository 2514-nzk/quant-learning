"""Editorial and data-boundary checks for Volume III 01–04.

Proves textbook structure and consistency, NOT independent real-market performance.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

from reader.build_reader import collect_documents, collect_framework_documents
from examples.volume3_strategy_lab import load_fixture, evaluate

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "advanced/volume-3"
NEW = (
    "01_strategy_contract", "02_market_regime",
    "03_industry_rotation", "04_reversal_momentum",
)


class ThirdVolumeChaptersTests(unittest.TestCase):
    def test_first_four_have_full_ordered_chapters_exercises_and_no_draft(self):
        for n, slug in enumerate(NEW, 1):
            page = (V3 / (slug + ".md")).read_text("utf-8")
            with self.subTest(chapter=slug):
                self.assertTrue(page.startswith(f"# 第三卷 · {n:02d}｜"))
                self.assertIn("状态：教学正文 v1", page)
                self.assertIn("python examples/volume3_strategy_lab.py --json", page)
                self.assertTrue("习题" in page or "练习" in page)
                self.assertIn("答", page)
                self.assertNotIn("正文待写", page)
                self.assertNotIn("实验未运行", page)
                headings = [int(x) for x in re.findall(r"(?m)^## (\d+)\. ", page)]
                self.assertEqual(headings, list(range(1, 9)))
                self.assertEqual(page.count(r"\["), page.count(r"\]"))
                self.assertEqual(page.count(r"\("), page.count(r"\)"))
                self.assertIn("返回 [本卷目录](README.md)", page)
                self.assertIn("SYNTHETIC_ONLY" if n == 4 else "人工", page)

    def test_local_links_exist_without_external_private_dependencies(self):
        docs = [V3 / (slug + ".md") for slug in NEW] + [V3 / "README.md"]
        checked = 0
        for doc in docs:
            body = doc.read_text("utf-8")
            for phrase in ("PTradePolicy", "xc_tushare_data.duckdb",
                           "local_all_a_2024_aggregate.json", "E:/duckdb_data"):
                self.assertNotIn(phrase, body)
            for m in re.finditer(r"\[[^\]]+\]\(([^)\s]+)\)", body):
                href = unquote(m.group(1)).split("#", 1)[0]
                if not href or href.startswith(("https://", "http://", "mailto:")):
                    continue
                target = (doc.parent / href).resolve()
                with self.subTest(page=doc.name, href=href):
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.exists(), f"Broken third-volume link: {href}")
                checked += 1
        self.assertGreaterEqual(checked, 15)

    def test_textbook_dataset_is_fourth_and_synthetic_not_source_backtest(self):
        manifest = json.loads((ROOT / "data/teaching/manifest.json").read_text("utf-8"))
        self.assertEqual(len(manifest["datasets"]), 5)
        names = [x["id"] for x in manifest["datasets"]]
        self.assertIn("volume3-weekly-synthetic-v1", names)
        payload = load_fixture()
        self.assertEqual(payload["evidence_grade"], "SYNTHETIC_ONLY")
        self.assertEqual(payload["week_count"], 16)
        self.assertEqual(payload["industries_per_week"], 4)
        self.assertEqual(payload["stocks_per_week"], 8)
        self.assertEqual(payload["calendar"], "ARTIFICIAL_FRIDAY_MON_NO_EXCHANGE_HOLIDAYS")
        self.assertEqual({w["taxonomy_version"] for w in payload["weeks"]},
                         {"TEACH_OLD", "TEACH_NEW"})

    def test_course_lab_does_not_pretend_real_pit_oos_or_execution(self):
        result = evaluate(load_fixture())
        self.assertEqual(result["source_kind"], "SYNTHETIC_ONLY")
        self.assertFalse(result["market_pit_proven"])
        self.assertFalse(result["real_market_OOS_proven"])
        self.assertFalse(result["execution_proven"])
        self.assertEqual(result["weeks"], 16)
        self.assertEqual(result["unknown_members"], 1)
        self.assertEqual(result["eligible_training_week_ids_at_week_3"], [1])
        self.assertTrue(result["strategies"]["cash"]["summary"]["all"]
                        ["mean_synthetic_net_proxy"] == 0)

    def test_shelf_and_existing_reading_paths_preserved(self):
        first = collect_documents()
        all_docs = collect_framework_documents()
        self.assertEqual(len(first), 22)
        self.assertEqual(len(all_docs), 33)
        third_chapters = [x for x in all_docs if
                          re.fullmatch(r"advanced/volume-3/\d{2}_[^/]+\.md", x["path"])]
        self.assertEqual(len(third_chapters), 13)
        for n, item in enumerate(third_chapters[:4], 1):
            self.assertTrue(item["title"].startswith(f"第 {n:02d} 章｜"))
            self.assertIn("状态：教学正文 v1", item["content"])
        self.assertTrue("状态：真实价格入门案例初稿" in
                        third_chapters[7]["content"])
        self.assertIn("状态：教学正文 v1", third_chapters[4]["content"])

    def test_reader_completion_respects_existing_storage_and_new_written_chapters(self):
        app = (ROOT / "reader/app.js").read_text("utf-8")
        self.assertIn('const STORAGE_KEY = "quant-learning-reader-v1"', app)
        self.assertIn('5 章教学正文 · 1 章入门案例 · 7 章待写', app)
        self.assertIn("0[1-4]|08", app)
        self.assertIn("readingRoute = firstVolume.filter", app)
        self.assertNotIn('status: "1 章案例初稿 · 12 章待写"', app)


if __name__ == "__main__":
    unittest.main()
