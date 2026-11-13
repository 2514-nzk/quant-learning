"""Protect a concept-first reading experience.

The early lessons introduce real prices and formulas. PIT/time leakage is
taught as a coherent method after learners understand features and labels,
not repeatedly as a warning before each new concept.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from reader.build_reader import collect_documents

ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "教程"


class ConceptFirstSequenceTests(unittest.TestCase):
    def test_intro_and_first_six_chapters_do_not_frontload_leakage_jargon(self):
        early = (
            "真实_阅读指南.md",
            "真实_起步一课.md",
            "真实_Python入门.md",
            "真实_01_收益与基准.md",
            "真实_02_多期与复利.md",
            "真实_03_历史K线与时点.md",
            "真实_04_特征与走势.md",
            "真实_05_均线与算子.md",
            "真实_06_财务与预处理.md",
            "真实_06a_合并报表与财务质量.md",
        )
        jargon = ("PIT", "数据泄漏", "偷看未来", "未来测试成绩")
        for filename in early:
            chapter = (COURSE / filename).read_text("utf-8")
            for term in jargon:
                with self.subTest(filename=filename, term=term):
                    self.assertNotIn(term, chapter)
        self.assertIn("成交量", (COURSE / "真实_04_特征与走势.md").read_text("utf-8"))
        self.assertIn("ROE", (COURSE / "真实_06_财务与预处理.md").read_text("utf-8"))

    def test_time_leakage_is_taught_after_feature_label_and_splits(self):
        timing = (COURSE / "真实_07_时间切分与泄漏.md").read_text("utf-8")
        order = (
            "## 1. 先认识“特征”和“标签”",
            "## 2. 为什么要把历史记录分成三段？",
            "## 3. 什么情况叫“未来信息泄漏”？",
            "## 4. 除了直接读未来价格",
            "## 5. 把这章方法用于自己的研究",
        )
        locations = [timing.index(text) for text in order]
        self.assertEqual(locations, sorted(locations))
        self.assertLess(timing.index("**特征（Feature）**"),
                        timing.index("**数据泄漏（Data Leakage）**"))
        self.assertLess(timing.index("**验证（Validation）**"),
                        timing.index("时点一致（PIT，Point-in-Time）"))
        for term in (
            "200.01", "215.29", "214.80", "198.67",
            "2024 年 3 月 15 日", "2024 年 2 月 1 日",
            "2024 年 6 月 21 日", "第 1–10 期", "第 11–14 期", "第 15–18 期",
        ):
            self.assertIn(term, timing)

    def test_chapter_three_is_ohlc_first_and_chapter_six_is_finance_first(self):
        price = (COURSE / "真实_03_历史K线与时点.md").read_text("utf-8")
        financial = (COURSE / "真实_06_财务与预处理.md").read_text("utf-8")
        self.assertIn("# 第 3 章｜一根 K 线怎样变成一行数据？", price)
        self.assertLess(price.index("## 1. 一根日 K 线"),
                        price.index("## 2. 价格表为什么需要股票代码和日期？"))
        self.assertIn("180.03 ÷ 183.00", price)
        self.assertIn("开盘（open）", price)
        self.assertLess(financial.index("## 1. 先理解 PE、EP、ROE"),
                        financial.index("## 4. 读财报时还应记住哪两个日期？"))
        self.assertIn("100 ÷ 5 = **20 倍**", financial)
        self.assertIn("**报告期**", financial)
        self.assertIn("**披露日期**", financial)

    def test_book_navigation_places_pit_in_chapter_seven(self):
        docs = collect_documents()
        self.assertEqual(len(docs), 22)
        paths = [doc["path"] for doc in docs]
        self.assertLess(paths.index("教程/真实_06a_合并报表与财务质量.md"),
                        paths.index("教程/真实_07_时间切分与泄漏.md"))
        index = (COURSE / "README.md").read_text("utf-8")
        self.assertIn("第二循环：从行情到因子评价", index)
        self.assertIn("怎样公平地检验选股指标？", index)
        self.assertIn("一根 K 线怎样变成一行数据？", index)

    def test_scaling_is_taught_when_two_indicators_are_combined(self):
        chapter6 = (COURSE / "真实_06_财务与预处理.md").read_text("utf-8")
        chapter10 = (COURSE / "真实_10_多因子.md").read_text("utf-8")
        chapter11 = (COURSE / "真实_11_线性模型.md").read_text("utf-8")
        self.assertIn("数据预处理", chapter6)
        self.assertIn("等到第 10 章", chapter6)
        self.assertNotIn("## 4. 归一化和标准化", chapter6)
        self.assertLess(chapter10.index("## 2. 两个指标怎么放到同一张评分表里"),
                        chapter10.index("### 把不同大小的数字换到一把尺子上"))
        self.assertLess(chapter10.index("排名只告诉我们谁在前面"),
                        chapter10.index("**归一化（这里指 Min-Max 缩放）**"))
        self.assertLess(chapter10.index("**归一化（这里指 Min-Max 缩放）**"),
                        chapter10.index("**标准化（这里指 Z-score）**"))
        self.assertIn("**Ridge（岭回归）**：", chapter11)
        self.assertIn("第 10 章已经用四只股票", chapter11)
        self.assertNotIn("## 4. 归一化和标准化", chapter11)
        real_returns = [7.64, 0.15, -0.94, -5.40]
        minimum, maximum = min(real_returns), max(real_returns)
        mean = sum(real_returns) / len(real_returns)
        std = (sum((value-mean)**2 for value in real_returns) / len(real_returns))**0.5
        normalized = [(value-minimum)/(maximum-minimum) for value in real_returns]
        standardized = [(value-mean)/std for value in real_returns]
        for value, expected in zip(normalized, [1.00, 0.43, 0.34, 0.00]):
            self.assertAlmostEqual(value, expected, delta=0.005)
        for value, expected in zip(standardized, [1.55, -0.05, -0.28, -1.23]):
            self.assertAlmostEqual(value, expected, delta=0.005)

    def test_later_chapters_lead_with_their_actual_topic(self):
        for filename, terms in {
            "真实_10_多因子.md": ("**多因子**", "综合分数 = 0.5 × 五日涨幅排名分"),
            "真实_11_线性模型.md": ("**线性模型**", "**Ridge（岭回归）**"),
            "真实_12_树与森林.md": ("**随机森林**", "**过拟合**"),
            "真实_13_逐步提升模型.md": ("**LightGBM**", "**早停**"),
        }.items():
            text = (COURSE / filename).read_text("utf-8")
            for term in terms:
                with self.subTest(filename=filename, term=term):
                    self.assertIn(term, text)
            self.assertNotIn("偷看未来", text)
            self.assertNotIn("未来测试成绩", text)


if __name__ == "__main__":
    unittest.main()
