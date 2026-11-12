"""Keep RankIC understandable and faithful to the actual A-share example.

This test is not a readability score. It prevents specific high-impact
regressions: unexplained jargon, swapping historical and future ranking, or
confusing RankIC with profit or prediction accuracy.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from examples.real_stock_learner import rank_ic

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "教程"


class RankIcReadabilityTests(unittest.TestCase):
    def test_real_four_stock_ranking_and_explanation_are_consistent(self):
        chapter = (DOC / "真实_08_单因子评价.md").read_text(encoding="utf-8")
        sample = json.loads((ROOT / "data/real_a_share/teaching_case.json").read_text(encoding="utf-8"))
        actual = sample["intro"]["rows"]
        self.assertEqual([x["name"] for x in actual], [
            "寒武纪", "宁德时代", "比亚迪", "贵州茅台"
        ])
        self.assertEqual([x["rank"] for x in actual], [1, 2, 3, 4])
        self.assertAlmostEqual(rank_ic(actual), -1)
        for term in ("2024 年 6 月 21 日", "6 月 28 日", "过去五日涨幅",
                     "后来观察到的收益", "RankIC = -1.00", "名次差的平方",
                     "**20**", "1 − 120 ÷ 60", "平均名次"):
            self.assertIn(term, chapter)

    def test_theory_follows_intuition_not_other_way_round(self):
        chapter = (DOC / "真实_08_单因子评价.md").read_text(encoding="utf-8")
        order = [
            "## 1. 先想一个不用公式的问题",
            "## 2. 两张真正的历史排行榜",
            "## 3. RankIC 的 +1、0、-1 分别是什么？",
            "## 4. 选读｜-1.00 是怎么从名次算出来的？",
            "## 5. 只看一次，还是看很多次？",
            "## 6. 排名对不对，与账户赚不赚钱是两回事",
        ]
        positions = [chapter.index(x) for x in order]
        self.assertEqual(positions, sorted(positions))
        for explanation in ("不是预测的涨幅", "不是账户收益率", "不是亏损 12.2%",
                            "过去指标", "预测正确率", "假设的两张榜单",
                            "**+0.8**", "18 个互不重叠"):
            self.assertIn(explanation, chapter)

    def test_key_jargon_is_explained_close_to_first_use(self):
        explanations = {
            "真实_阅读指南.md": ["“因子”就是", "“股票池”"],
            "真实_04_特征与走势.md": ["**特征**", "**动量因子**", "换手率"],
            "真实_05_均线与算子.md": ["**MA5**", "**MOM5**", "**算子**"],
            "真实_03_历史K线与时点.md": ["**不复权**", "开盘（open）", "收盘（close）"],
            "真实_07_时间切分与泄漏.md": ["**数据泄漏**", "**训练（Train）**", "**验证（Validation）**", "PIT，Point-in-Time"],
            "真实_09_成交与费用.md": ["**涨跌停**", "**停牌**", "**T+1**"],
            "真实_10_多因子.md": ["**多因子**", "**均线偏离**", "**权重**"],
            "真实_11_线性模型.md": ["**线性模型**", "**标准化**", "**Ridge（岭回归）**"],
            "真实_12_树与森林.md": ["**过拟合**", "**随机森林**"],
            "真实_13_逐步提升模型.md": ["**LightGBM**", "**Boosting（提升方法）**", "**早停**"],
            "真实_14_评价与风险.md": ["RankIC（排名相关性）", "最大回撤"],
            "真实_16_综合练习.md": ["RankIC（当时按指标排的名次"],
        }
        for file, terms in explanations.items():
            content = (DOC / file).read_text(encoding="utf-8")
            for term in terms:
                with self.subTest(file=file, term=term):
                    self.assertIn(term, content)

    def test_later_chapter_links_to_full_explanation(self):
        for filename in ("真实_14_评价与风险.md", "真实_16_综合练习.md"):
            content = (DOC / filename).read_text("utf-8")
            self.assertIn("(真实_08_单因子评价.md)", content)
        chapter14 = (DOC / "真实_14_评价与风险.md").read_text("utf-8")
        self.assertIn("排名一致程度、账户收益和回撤", chapter14)
        self.assertNotIn("排名正确率、账户收益", chapter14)


if __name__ == "__main__":
    unittest.main()
