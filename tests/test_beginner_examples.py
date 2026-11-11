"""Verify beginner arithmetic and workbook coverage without external dependencies."""

from __future__ import annotations

import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "教程"

MAIN_CHAPTERS = [
    "00f_从一次选股认识量化.md",
    "00g_读懂第一段量化代码.md",
    "01_研究问题定义.md",
    "01a_研究假设与研报复现.md",
    "02_数据与标签.md",
    "03_特征工程.md",
    "03a_因子表达式与算子.md",
    "03b_传统因子与预处理.md",
    "04_时间切分与泄漏.md",
    "08a_单因子研究与评价.md",
    "09_预测到组合.md",
    "09a_多因子合成与综合实训.md",
    "05_线性基线.md",
    "06_决策树与随机森林.md",
    "07_GBDT与LightGBM.md",
    "08_模型评价与解释.md",
    "10_研究框架与结课项目.md",
    "11_完整手算案例与实验操作.md",
]


class BeginnerExamplesTests(unittest.TestCase):
    def test_lessons_have_beginner_examples_and_optional_advanced(self):
        for filename in MAIN_CHAPTERS:
            with self.subTest(filename=filename):
                value = (COURSE / filename).read_text(encoding="utf-8")
                self.assertIn("## 1.", value)
                self.assertRegex(value, r"(?m)^### .+")
                if "进阶训练" in value:
                    self.assertIn("## 选读｜进阶训练：", value)
                self.assertNotIn(chr(92) + chr(96), value)

    def test_workbook_has_sixteen_answers(self):
        text = (COURSE / "00h_零基础16道小题.md").read_text(encoding="utf-8")
        indexes = [int(x) for x in re.findall(r"(?m)^### (\d+)\. ", text)]
        self.assertEqual(indexes, list(range(1, 17)))
        self.assertEqual(text.count("<details>"), 16)
        self.assertEqual(text.count("</details>"), 16)
        self.assertIn("8,320 元", text)
        self.assertIn("8,191.61 元", text)

    def test_examples_agree_with_cash_arithmetic(self):
        self.assertTrue(math.isclose(4000 * 1.05 + 4000 * 1.03, 8320))
        self.assertTrue(math.isclose(2000 * (1.05 + 1.01 + 1.03 + .98), 8140))
        self.assertTrue(math.isclose(100 * 1.1 * .9, 99))
        self.assertTrue(math.isclose((.05 + .03) / 2, .04))
        self.assertTrue(math.isclose(4000 * 1.05 + 4000, 8200))
        fee_case = 4000 / 1.001 * 1.05 * .999 + 4000
        self.assertTrue(math.isclose(fee_case, 8191.608391608392))
        self.assertTrue(math.isclose(.4 + .1 * (.8 - .4), .44))


if __name__ == "__main__":
    unittest.main()
