"""Canonical sidebar numbering and grouping across the three volumes."""
import re
import unittest
from reader.build_reader import collect_documents, collect_framework_documents, sidebar_title


class SidebarTaxonomyTests(unittest.TestCase):
    def test_first_volume_uses_two_digit_chapter_numbers(self):
        documents = collect_documents()
        chapters = [p for p in documents if re.fullmatch(r"教程/真实_\d{2}_[^/]+\.md", p["path"])]
        self.assertEqual(len(chapters), 16)
        self.assertEqual([p["title"].split("章")[0] for p in chapters],
                         [f"第 {n:02d} " for n in range(1, 17)])
        self.assertTrue(all(p["group"].startswith("第一卷｜") for p in documents))
        self.assertIn("第一卷｜导读与准备", [p["group"] for p in documents])

    def test_advanced_chapters_show_numbers_and_appendices_are_not_chapters(self):
        advanced = collect_framework_documents()
        second = [p for p in advanced if re.fullmatch(r"advanced/volume-2/\d{2}_[^/]+\.md", p["path"])]
        third = [p for p in advanced if re.fullmatch(r"advanced/volume-3/\d{2}_[^/]+\.md", p["path"])]
        self.assertEqual(len(second), 14)
        self.assertEqual(len(third), 13)
        for entries in (second, third):
            for n, item in enumerate(entries, 1):
                self.assertTrue(item["title"].startswith(f"第 {n:02d} 章｜"), item)
                self.assertRegex(item["group"], r"｜第 01–(?:14|13) 章 · ")
        appendix = [p for p in advanced if "｜附录与审计" in p["group"]]
        self.assertEqual([p["title"] for p in appendix],
                         ["附录 A｜真实价格证据审计", "附录 B｜教学版校审与外部待办",
                          "附录 C｜教材数据集与复现规范",
                          "附录 D｜全卷质量校审与术语表"])
        self.assertEqual(len({p["path"] for p in advanced}), 33)

    def test_titles_are_normalized_idempotently_and_paths_not_renamed(self):
        self.assertEqual(sidebar_title("advanced/volume-2/01_research_protocol.md",
                                       "第 01 章｜研究协议"), "第 01 章｜研究协议")
        self.assertEqual(sidebar_title("教程/真实_01_收益与基准.md",
                                       "第 1 章｜收益与基准"), "第 01 章｜收益与基准")
        self.assertEqual(sidebar_title("advanced/volume-2/README.md", "ignored"),
                         "导读｜第二卷课程目录")


if __name__ == "__main__":
    unittest.main()
