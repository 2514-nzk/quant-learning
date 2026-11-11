"""Regression tests for concept-first chapter order and in-chapter prerequisites.

Do not silently reintroduce 'explaining after use' problems into beginner flow.
"""
import re
import unittest
from pathlib import Path

from reader.build_reader import collect_documents


ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = ROOT / "教程"
CHAPTERS = [
    ("01_研究问题定义.md", 1),
    ("01a_研究假设与研报复现.md", 2),
    ("02_数据与标签.md", 3),
    ("03_特征工程.md", 4),
    ("03a_因子表达式与算子.md", 5),
    ("03b_传统因子与预处理.md", 6),
    ("04_时间切分与泄漏.md", 7),
    ("08a_单因子研究与评价.md", 8),
    ("09_预测到组合.md", 9),
    ("09a_多因子合成与综合实训.md", 10),
    ("05_线性基线.md", 11),
    ("06_决策树与随机森林.md", 12),
    ("07_GBDT与LightGBM.md", 13),
    ("08_模型评价与解释.md", 14),
    ("10_研究框架与结课项目.md", 15),
    ("11_完整手算案例与实验操作.md", 16),
]


class LearningFlowTests(unittest.TestCase):
    def test_chapter_number_titles_match_sidebar_order(self):
        documents = collect_documents()
        order = [doc["path"] for doc in documents]
        numbers = []
        for filename, expected in CHAPTERS:
            path = "教程/" + filename
            numbers.append(order.index(path))
            first = (TUTORIAL / filename).read_text("utf-8").splitlines()[0]
            self.assertTrue(
                first.startswith(f"# 第 {expected} 章｜"),
                f"{filename} displays the wrong chapter number: {first}",
            )
        self.assertEqual(numbers, sorted(numbers))

    def test_data_before_features_before_model_selection(self):
        document = (TUTORIAL / "02_数据与标签.md").read_text("utf-8")
        # Introduce familiar OHLC before a row, then a future label, then PIT.
        topics = [
            "## 1. 从交易软件的 K 线",
            "## 2. 同一张表",
            "## 3. 当时的输入和未来的答案",
            "## 4. 财报什么时候公布",
        ]
        places = [document.index(part) for part in topics]
        self.assertEqual(places, sorted(places))
        self.assertIn("下一章先不急着训练模型", document)
        time_split = (TUTORIAL / "04_时间切分与泄漏.md").read_text("utf-8")
        self.assertIn("现在才需要比较", time_split)
        self.assertIn("下一章会把动量因子的排名", time_split)

    def test_python_practice_follows_introduction(self):
        source = (TUTORIAL / "00g_读懂第一段量化代码.md").read_text("utf-8")
        self.assertLess(source.index("## 2. 用一条记录"), source.index("ranked = sorted"))
        self.assertLess(source.index("ranked = sorted"), source.index("### 学过排序后，自己先猜一次"))

    def test_advanced_uncertainty_follows_basic_evaluation(self):
        lesson = (TUTORIAL / "08_模型评价与解释.md").read_text("utf-8")
        self.assertLess(lesson.index("## 2. RankIC 与组合收益"), lesson.index("## 3. 复利、净值"))
        self.assertLess(lesson.index("## 3. 复利、净值"), lesson.index("## 4. 选读｜14 期"))
        self.assertLess(lesson.index("## 4. 选读｜14 期"), lesson.index("## 5. 特征消融"))

    def test_study_notes_do_not_use_old_chapter_numbers(self):
        cases = {
            "00a_Python数据分析基础.md": "第 5 章",
            "00d_量化Python实战.md": "第 5 章",
            "参考_因子算子与边界.md": "第 5 章",
            "参考_模型比较与解释.md": "第 7 章",
            "真实A股K线_入门实例.md": "第 5 章",
        }
        for filename, term in cases.items():
            with self.subTest(filename=filename):
                self.assertIn(term, (TUTORIAL / filename).read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
