"""Validate links and entry points for the *published* real-stock textbook."""
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

from reader.build_reader import collect_documents


ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "教程"


class CurriculumLinkTests(unittest.TestCase):
    def test_published_index_and_lessons_have_no_broken_local_links(self):
        documents = collect_documents()
        paths = [COURSE / "README.md"] + [ROOT / doc["path"] for doc in documents]
        pattern = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")
        for source in paths:
            with self.subTest(source=source.relative_to(ROOT)):
                self.assertTrue(source.is_file(), f"missing chapter: {source}")
                content = source.read_text(encoding="utf-8")
                for href in pattern.findall(content):
                    href = href.strip().split("#", 1)[0]
                    if not href or "://" in href or href.startswith(("mailto:", "tel:", "data:")):
                        continue
                    target = (source.parent / unquote(href)).resolve()
                    self.assertTrue(
                        target.is_relative_to(ROOT) and target.is_file(),
                        f"broken local link in {source.relative_to(ROOT)}: {href}",
                    )

    def test_new_book_entry_and_real_data_exercise_are_discoverable(self):
        index = (COURSE / "README.md").read_text(encoding="utf-8")
        guide = (COURSE / "真实_阅读指南.md").read_text(encoding="utf-8")
        project = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("真实_起步一课.md", index)
        self.assertIn("真实_16_综合练习.md", index)
        self.assertIn("100 万元课堂模拟资金", guide)
        self.assertIn("python examples/real_stock_learner.py", project)
        self.assertIn("2024-06-21", project)


if __name__ == "__main__":
    unittest.main()
