"""Real price and beginner-order checks for the optional cointegration topic.

No network, statsmodels or additional data downloads are needed for these tests.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from examples.cointegration_pair_lab import (
    TRAIN_DAYS, EXPECTED_DAYS,
    paired_closes, fit_training, spread_z, describe,
)
from reader.build_reader import collect_documents

ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / "教程" / "真实_专题A_协整与配对交易.md"
CHART = ROOT / "reader" / "assets" / "real-a-share" / "catl-byd-spread.svg"


class CointegrationLessonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = paired_closes()
        cls.model = fit_training(cls.rows)

    def test_actual_price_alignment_and_course_numbers(self):
        self.assertEqual(TRAIN_DAYS, 80)
        self.assertEqual(EXPECTED_DAYS, 117)
        self.assertEqual(len(self.rows), 117)
        self.assertEqual(self.rows[0], ("2024-01-02", 156.83, 192.60))
        self.assertEqual(self.rows[79], ("2024-05-07", 206.88, 229.88))
        self.assertEqual(self.rows[80], ("2024-05-08", 203.23, 226.23))
        self.assertEqual(self.rows[-1], ("2024-06-28", 180.03, 250.25))
        self.assertAlmostEqual(self.model.return_corr, 0.6151341203610018, places=8)
        self.assertAlmostEqual(self.model.intercept, -59.43772093793598, places=7)
        self.assertAlmostEqual(self.model.beta, 1.1692584900384166, places=8)
        self.assertAlmostEqual(self.model.spread_sd, 8.325372214630216, places=8)
        self.assertAlmostEqual(spread_z(self.rows[-1], self.model), -6.382803654207326, places=7)

    def test_training_fit_never_uses_future_prices(self):
        changed = self.rows[:TRAIN_DAYS] + [
            (day, price * 8, other * 2)
            for day, price, other in self.rows[TRAIN_DAYS:]
        ]
        self.assertEqual(fit_training(changed), self.model)
        self.assertNotAlmostEqual(spread_z(changed[-1], self.model),
                                  spread_z(self.rows[-1], self.model), places=2)

    def test_course_places_topic_after_capstone_before_reference(self):
        docs = collect_documents()
        paths = [x["path"] for x in docs]
        advanced = "教程/真实_专题A_协整与配对交易.md"
        self.assertEqual(len(docs), 22)
        self.assertEqual(paths[-2], advanced)
        self.assertEqual(paths[-1], "教程/真实_研究边界.md")
        self.assertLess(paths.index("教程/真实_16_综合练习.md"), paths.index(advanced))
        self.assertEqual(docs[-2]["group"], "进阶专题 · 统计套利入门")
        self.assertNotIn(advanced, [doc["path"] for doc in docs[:20]])

    def test_reading_order_and_caveats(self):
        text = CHAPTER.read_text("utf-8")
        headings = [
            "## 1. 先看真实行情",
            "## 2. 相关性",
            "## 3. 价差与均值回归",
            "## 4. 协整",
            "## 5. 怎么判断价差",
            "## 6. 怎样做正式的协整检验",
            "## 7. 如果真的存在协整",
            "## 8. 自己试一试",
        ]
        order = [text.index(h) for h in headings]
        self.assertEqual(order, sorted(order))
        for key in ("宁德时代", "比亚迪", "2024-01-02", "2024-05-07",
                    "2024-06-28", "117 个", "前 80 个", "后 37 个",
                    "**+0.615**", "**-6.38**", "Engle–Granger",
                    "协整是对数据性质的统计判断", "没有把上面的 Z 当成交易信号",
                    "100 万元模拟资金", "原假设是“不存在协整”"):
            with self.subTest(key=key):
                self.assertIn(key, text)
        self.assertIn("../reader/assets/real-a-share/catl-byd-spread.svg", text)
        self.assertTrue(CHART.is_file())
        graphic = CHART.read_text("utf-8")
        self.assertIn("最后一天 Z ≈ -6.38", graphic)
        self.assertIn("真实日收盘价", graphic)
        self.assertIn("不复权", graphic)
        self.assertIn("data/real_a_share", str(ROOT / "data/real_a_share"))

    def test_standard_mode_is_self_contained(self):
        output = describe(self.rows, self.model)
        self.assertIn("不代表检验通过", output)
        self.assertIn("相关系数不等于协整", output)
        self.assertIn("2024-06-28", output)
        self.assertIn("Z=-6.38", output)


if __name__ == "__main__":
    unittest.main()
