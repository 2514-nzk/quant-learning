"""Protect preview's second-volume navigation, math and existing first-volume route."""
from pathlib import Path
import unittest
from reader.build_reader import collect_documents, collect_framework_documents

ROOT = Path(__file__).resolve().parents[1]


class ReaderPreviewTests(unittest.TestCase):
    def test_first_volume_and_advanced_payload_are_separate(self):
        first = collect_documents()
        advanced = collect_framework_documents()
        self.assertEqual(len(first), 22)
        self.assertEqual(len(advanced), 29)
        self.assertNotIn("教程/真实_专题A_协整与配对交易.md", [x["path"] for x in first])
        self.assertIn("advanced/volume-3/08_stat_arb.md", [x["path"] for x in advanced])
        self.assertEqual(sum(p["path"].startswith("advanced/volume-2/") for p in advanced), 15)
        self.assertEqual(sum(p["path"].startswith("advanced/volume-3/") for p in advanced), 14)
        self.assertEqual(sum(p["path"].endswith(".md") and not p["path"].endswith("README.md") for p in advanced
                             if p["path"].startswith("advanced/volume-2/")), 14)

    def test_landing_page_exposes_three_volumes_and_preview_warning(self):
        html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
        js = (ROOT / "reader/app.js").read_text(encoding="utf-8")
        for token in ("三卷量化研究教材", "第二卷 14 章教学初稿", "preview-note", "second-volume-progress-copy"):
            self.assertIn(token, html)
        for token in ("第一卷 · 量化研究基础", "第二卷 · 专业量化研究方法",
                      "第三卷 · A 股策略与交易系统", "advanced/volume-2/"):
            self.assertIn(token, js)
        self.assertIn('readingRoute = firstVolume.filter', js)

    def test_volume_boundary_requires_explicit_bookshelf_switch(self):
        js = (ROOT / "reader/app.js").read_text(encoding="utf-8")
        self.assertIn("function volumeOf(doc)", js)
        self.assertIn('nextIsAnotherVolume ? "__home__"', js)
        self.assertIn('previousIsAnotherVolume ? "__home__"', js)
        self.assertIn('if (path === "__home__") showHome()', js)

    def test_moved_pair_trading_case_retains_old_bookmarks_and_progress(self):
        js = (ROOT / "reader/app.js").read_text(encoding="utf-8")
        self.assertIn('const oldPairPath = "教程/真实_专题A_协整与配对交易.md"', js)
        self.assertIn('const newPairPath = "advanced/volume-3/08_stat_arb.md"', js)
        self.assertIn("state.bookmarks.map(migratePairPath)", js)
        self.assertIn("state.completed.map(migratePairPath)", js)
        self.assertIn("state.positions[newPairPath]", js)
        self.assertIn('第三卷 第 8 / 13 章 · 入门案例', js)

    def test_chapter_links_use_preview_source_and_math_has_readable_fallback(self):
        html = (ROOT / "reader/index.html").read_text(encoding="utf-8")
        js = (ROOT / "reader/app.js").read_text(encoding="utf-8")
        self.assertIn("docs/three-volume-research-framework", js)
        self.assertIn("typesetMath(wrapper)", js)
        self.assertIn("if (!window.katex) return", js)
        self.assertIn("katex.min.js", html)
        self.assertIn("katex.min.css", html)


if __name__ == "__main__":
    unittest.main()
