"""Guard the stock-trader-first reading route and fair net-cost comparisons."""

from __future__ import annotations

import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "教程"


class TraderFriendlyRouteTests(unittest.TestCase):
    def test_tools_are_optional_and_key_concepts_are_in_main_chapters(self):
        guide = (LESSONS / "00_学习路线.md").read_text(encoding="utf-8")
        index = (LESSONS / "README.md").read_text(encoding="utf-8")
        self.assertIn("正文优先，手册后查", guide)
        self.assertIn("第一次可以全部不读", index)
        required = {
            "00g_读懂第一段量化代码.md": ["DataFrame", "CSV"],
            "02_数据与标签.md": ["open", "high", "low", "close", "复权"],
            "03_特征工程.md": ["成交量", "成交额", "换手率"],
            "03a_因子表达式与算子.md": ["均线", "MOM5"],
            "03b_传统因子与预处理.md": ["PE", "EP"],
            "08a_单因子研究与评价.md": ["240 行", "60 个"],
            "09_预测到组合.md": ["T+1", "手数", "扣费"],
            "05_线性基线.md": ["fit", "transform", "predict"],
            "07_GBDT与LightGBM.md": ["早停", "验证误差"],
            "08_模型评价与解释.md": ["Sharpe", "最大回撤"],
        }
        for path, markers in required.items():
            with self.subTest(path=path):
                text = (LESSONS / path).read_text(encoding="utf-8")
                for item in markers:
                    self.assertIn(item, text)

    def test_same_fee_benchmark_numbers_are_correct(self):
        # Both strategies rebalance the entire budget and pay an equal round-trip
        # proportional fee on the actual buy and sell notionals.
        budget = 8000
        fee = 0.001
        factor = (1 - fee) / (1 + fee)
        selected_net = budget * 1.04 * factor
        benchmark_net = budget * 1.0175 * factor
        self.assertAlmostEqual(selected_net, 8303.376623376624)
        self.assertAlmostEqual(benchmark_net, 8123.736263736265)
        self.assertAlmostEqual(selected_net - benchmark_net, 179.64035964035884)
        self.assertAlmostEqual(selected_net - 8140, 163.37662337662368)
        crossing_uncharged_benchmark = (1.04 - 1.0175) / (1.04 + 1.0175)
        self.assertAlmostEqual(crossing_uncharged_benchmark * 100, 1.0935601458)
        self.assertGreater(1.04 * factor, 1.0175 * factor)
        chapter = (LESSONS / "09_预测到组合.md").read_text(encoding="utf-8")
        for amount in ("8,303.38", "8,123.74", "179.64", "163.38", "1.09%"):
            self.assertIn(amount, chapter)
        self.assertNotIn("2.25% - 2c", chapter)

    def test_guide_no_longer_requires_reading_the_handbooks_first(self):
        guide = (LESSONS / "00_学习路线.md").read_text(encoding="utf-8")
        self.assertIn("先动手算一道题", guide)
        self.assertNotIn("工具层不是选读", guide)
        self.assertIn("K 线", guide)


if __name__ == "__main__":
    unittest.main()
