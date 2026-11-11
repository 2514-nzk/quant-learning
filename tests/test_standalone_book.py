"""Protect the published four-stock textbook from inherited manuscript history.

Older synthetic examples are retained as research fixtures in the repository,
but must never be surfaced as this book's own history or capital assumptions.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from reader.build_reader import collect_documents


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PAGES = (
    ROOT / "README.md",
    ROOT / "教程/README.md",
    ROOT / "reader/index.html",
)
BANNED = (
    r"8\s*[,，]?\s*000\s*元",
    r"\b8\s*[kK]\s*(?:元|的资金|资金)",
    r"八千元?",
    r"旧版",
    r"旧讲义",
    r"旧教材",
    r"原来使用虚构",
    r"原来四只虚构",
    r"不再用只能买",
    r"主阅读路线改为",
    r"本次课程融合",
    r"本次(?:修改|调整|重做)",
)


class StandaloneBookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = collect_documents()

    def test_initial_account_is_one_million_everywhere(self):
        root = (ROOT / "README.md").read_text("utf-8")
        index = (ROOT / "教程/README.md").read_text("utf-8")
        guide = (ROOT / "教程/真实_阅读指南.md").read_text("utf-8")
        home = (ROOT / "reader/index.html").read_text("utf-8")
        first = (ROOT / "教程/真实_起步一课.md").read_text("utf-8")
        self.assertIn("100 万元课堂模拟账户", root)
        self.assertIn("100 万元课堂模拟资金", index)
        self.assertIn("100 万元课堂模拟资金", guide)
        self.assertIn("100 万元课堂模拟资金", home)
        self.assertIn("100 万元", first)
        self.assertIn("50 万元", first)

    def test_no_revision_changelog_inside_published_book(self):
        content = [(str(path.relative_to(ROOT)), path.read_text("utf-8")) for path in PUBLIC_PAGES]
        content.extend((doc["path"], doc["content"]) for doc in self.documents)
        for path, text in content:
            for pattern in BANNED:
                with self.subTest(path=path, pattern=pattern):
                    self.assertNotRegex(text, re.compile(pattern, re.IGNORECASE))

    def test_main_book_has_only_real_stock_lessons(self):
        docs = self.documents
        self.assertEqual(len(docs), 21)
        self.assertTrue(all(doc["path"].startswith("教程/真实_") for doc in docs))
        self.assertEqual(docs[0]["path"], "教程/真实_阅读指南.md")
        self.assertEqual(docs[1]["path"], "教程/真实_起步一课.md")
        self.assertEqual(docs[2]["path"], "教程/真实_Python入门.md")
        self.assertEqual(docs[-1]["path"], "教程/真实_研究边界.md")

    def test_dates_and_stock_names_remain_consistent(self):
        index = (ROOT / "教程/README.md").read_text("utf-8")
        root = (ROOT / "README.md").read_text("utf-8")
        for code, name in (
            ("600519", "贵州茅台"),
            ("688256", "寒武纪"),
            ("300750", "宁德时代"),
            ("002594", "比亚迪"),
        ):
            self.assertIn(name, index)
            self.assertIn(code, index)
            self.assertIn(name, root)
            self.assertIn(code, root)
        for day in ("2024-06-21", "2024-06-24", "2024-06-28"):
            self.assertIn(day, root)

    def test_reader_home_is_book_copy_not_edit_history(self):
        html = (ROOT / "reader/index.html").read_text("utf-8")
        self.assertIn("从四只真实股票开始", html)
        self.assertIn("真实历史行情 · 量化研究方法练习", html)
        self.assertNotIn("内容来自本地教材与研究模板", html)


if __name__ == "__main__":
    unittest.main()
