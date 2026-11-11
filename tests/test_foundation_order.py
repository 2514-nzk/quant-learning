"""Check fundamentals appear at the right points in the live reading order."""

import unittest
from pathlib import Path

from reader.build_reader import collect_documents


ROOT = Path(__file__).resolve().parents[1]


class FoundationOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = collect_documents()
        cls.positions = {doc["path"]: i for i, doc in enumerate(cls.documents)}

    def test_python_math_finance_are_near_the_start(self):
        pos = self.positions
        beginner = pos["教程/00g_读懂第一段量化代码.md"]
        chapter1 = pos["教程/01_研究问题定义.md"]
        for path in (
            "教程/00a_Python数据分析基础.md",
            "教程/00e_量化数学与统计.md",
            "教程/00c_金融市场基本概念.md",
        ):
            with self.subTest(path=path):
                self.assertLess(beginner, pos[path])
                self.assertLess(pos[path], chapter1)
                self.assertEqual(self.documents[pos[path]]["group"], "基础准备 · 随学随查")

    def test_advanced_basics_are_at_first_use(self):
        pos = self.positions
        self.assertLess(
            pos["教程/04_时间切分与泄漏.md"],
            pos["教程/00d_量化Python实战.md"],
        )
        self.assertLess(
            pos["教程/00d_量化Python实战.md"],
            pos["教程/08a_单因子研究与评价.md"],
        )
        self.assertLess(
            pos["教程/00b_机器学习基础.md"],
            pos["教程/05_线性基线.md"],
        )
        self.assertEqual(
            self.documents[pos["教程/00b_机器学习基础.md"]]["group"],
            "第四循环 · 模型有没有增加信息？",
        )

    def test_in_depth_references_are_still_at_end(self):
        pos = self.positions
        self.assertLess(
            pos["教程/11_完整手算案例与实验操作.md"],
            pos["教程/参考_因子研究完整方法.md"],
        )
        self.assertEqual(
            self.documents[pos["教程/参考_因子研究完整方法.md"]]["group"],
            "工具与参考",
        )
        self.assertEqual(len(pos), len(self.documents))

    def test_prerequisites_are_taught_before_factor_evaluation(self):
        # The visible left navigation must match how readers learn, not the old
        # numbers left in the source filenames.
        ordered = [
            "教程/02_数据与标签.md",
            "教程/03_特征工程.md",
            "教程/03a_因子表达式与算子.md",
            "教程/03b_传统因子与预处理.md",
            "教程/04_时间切分与泄漏.md",
            "教程/00d_量化Python实战.md",
            "教程/08a_单因子研究与评价.md",
        ]
        positions = [self.positions[path] for path in ordered]
        self.assertEqual(positions, sorted(positions))

    def test_comprehensive_workbook_is_after_final_lesson(self):
        self.assertGreater(
            self.positions["教程/00h_零基础16道小题.md"],
            self.positions["教程/11_完整手算案例与实验操作.md"],
        )
        self.assertLess(
            self.positions["教程/00h_零基础16道小题.md"],
            self.positions["教程/参考_因子研究完整方法.md"],
        )

    def test_python_intro_is_first(self):
        content = (ROOT / "教程/00a_Python数据分析基础.md").read_text("utf-8")
        intro = content.index("## 第一次读这里")
        contract = content.index("选读｜开始独立做项目时")
        self.assertLess(intro, contract)
        self.assertLess(contract, content.index("## 1. DataFrame"))
        self.assertIn("只炒过股、还没用过 Python 也可以读", content)


if __name__ == "__main__":
    unittest.main()
