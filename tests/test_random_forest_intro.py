"""Regression checks for a beginner-friendly random forest lesson.

Actual historical price observations are kept separate from hypothetical
hand-written tree rules. Concept order is more important than jargon volume.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOREST = ROOT / "教程" / "真实_12_树与森林.md"
BOOST = ROOT / "教程" / "真实_13_逐步提升模型.md"


class RandomForestIntroTests(unittest.TestCase):
    def test_first_example_uses_real_four_stock_values(self):
        chapter = FOREST.read_text("utf-8")
        for value in (
            "2024 年 6 月 21 日", "寒武纪", "宁德时代",
            "比亚迪", "贵州茅台", "+7.64%", "+0.15%",
            "-0.94%", "-5.40%", "215.29", "213.486",
            "185.16", "188.138", "250.67", "253.804",
            "1471.00", "1507.020", "214.80", "198.67", "-7.51%"
        ):
            with self.subTest(value=value):
                self.assertIn(value, chapter)
        self.assertGreater(215.29, 213.486)
        self.assertAlmostEqual((198.67 / 214.80 - 1) * 100, -7.51, delta=0.01)

    def test_narrative_builds_tree_before_forest(self):
        chapter = FOREST.read_text("utf-8")
        ordered = (
            "## 1. 一棵决策树，其实就是连续问问题",
            "## 2. 为什么不直接用一棵树？",
            "## 3. 让多棵树分别判断，再综合它们的意见",
            "## 4. 为什么叫“随机”森林？树为什么会不一样？",
            "## 5. 跟线性模型，以及下一章的 LightGBM，有什么不同？"
        )
        positions = [chapter.index(x) for x in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(chapter.index("沿着条件一步步走到最后一格"),
                        chapter.index("**随机森林**"))
        self.assertLess(chapter.index("**过拟合**"),
                        chapter.index("让多棵树分别判断"))

    def test_distinguishes_demonstration_from_training(self):
        chapter = FOREST.read_text("utf-8")
        for phrase in (
            "不是电脑从历史数据训练出来的模型",
            "真实的是股票价格与指标",
            "规则和判断只是为了演示汇总过程",
            "2 票“上涨”、1 票“下跌”",
            "**分类**", "**回归**",
            "有放回抽样", "部分指标中挑选",
            "不是买入当天随便扔骰子", "不保证一定预测得更准",
            "叶子节点", "树的深度", "叶子最少样本数"
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, chapter)
        self.assertEqual(chapter.count("<details>"), 3)
        self.assertEqual(chapter.count("</details>"), 3)

    def test_next_chapter_naturally_continues(self):
        text = BOOST.read_text("utf-8")
        self.assertIn("很多棵树分别作出判断，最后综合意见", text)
        self.assertIn("第一棵树先预测", text)
        self.assertIn("Boosting（提升方法）", text)
        self.assertIn("LightGBM", text)


if __name__ == "__main__":
    unittest.main()
