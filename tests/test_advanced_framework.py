"""Protect published first-volume route while exposing advanced outline pages."""
import re
import unittest
from pathlib import Path

from reader.build_reader import collect_documents, collect_framework_documents

ROOT = Path(__file__).resolve().parents[1]


class AdvancedFrameworkTests(unittest.TestCase):
    def test_first_volume_is_untouched(self):
        first = collect_documents()
        self.assertEqual(len(first), 23)
        self.assertTrue(all(x["path"].startswith("教程/真实_") for x in first))

    def test_advanced_pages_are_complete_as_outlines(self):
        pages = collect_framework_documents()
        second = [p for p in pages if p["group"].startswith("第二卷")]
        third = [p for p in pages if p["group"].startswith("第三卷")]
        self.assertEqual(len(second), 15)  # index + 14 chapters
        self.assertEqual(len(third), 14)  # index + 13 chapters
        self.assertEqual(len({p["path"] for p in pages}), 29)
        for page in pages:
            with self.subTest(path=page["path"]):
                self.assertTrue((ROOT / page["path"]).is_file())
                self.assertIn("状态", page["content"])
                if page["path"].endswith("README.md"):
                    continue
                if page["path"].endswith(("01_research_protocol.md", "05_pit_data.md", "06_labels_splits.md", "07_factor_engineering.md", "08_factor_validation.md",
                    "09_factor_combination.md", "10_machine_learning.md", "11_oos_drift.md")):
                    self.assertIn("状态：教学正文初稿", page["content"])
                    self.assertIn("合成", page["content"])
                    if page["path"].endswith((
                        "09_factor_combination.md", "10_machine_learning.md", "11_oos_drift.md"
                    )):
                        lab = "advanced_model_validation_lab.py"
                    elif page["path"].endswith((
                        "06_labels_splits.md", "07_factor_engineering.md", "08_factor_validation.md"
                    )):
                        lab = "advanced_factor_research_lab.py"
                    else:
                        lab = "advanced_protocol_pit_lab.py"
                    self.assertIn("python examples/" + lab, page["content"])
                else:
                    self.assertIn("正文待写", page["content"])
                    self.assertIn("实验未运行", page["content"])
                    for heading in ("本章核心问题", "计划知识模块", "计划动手实验", "本章交付物"):
                        self.assertIn(heading, page["content"])

    def test_volume_index_links(self):
        for dirname, count in (("volume-2", 14), ("volume-3", 13)):
            directory = ROOT / "advanced" / dirname
            links = re.findall(r"\]\((\d{2}_[^)]*\.md)\)", (directory / "README.md").read_text("utf-8"))
            unique_links = set(links)
            self.assertEqual(len(unique_links), count)
            for filename in unique_links:
                self.assertTrue((directory / filename).is_file())


if __name__ == "__main__":
    unittest.main()
