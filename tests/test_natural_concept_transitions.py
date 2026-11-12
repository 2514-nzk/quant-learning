"""Editorial regression checks: examples and questions precede new abstractions.

These checks intentionally focus on high-impact narrative order, not a global
keyword quota that could hide useful concepts from the textbook.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "教程"


def read(name: str) -> str:
    return (COURSE / name).read_text(encoding="utf-8")


class NaturalConceptTransitionsTests(unittest.TestCase):
    def test_beginner_stock_pick_is_an_exercise_before_a_warning(self):
        chapter = read("真实_起步一课.md")
        self.assertIn("## 1. 先按最近五日涨幅排个名", chapter)
        self.assertIn("## 2. 买入后这五天，实际表现怎么样？", chapter)
        self.assertIn("## 4. 这次结果能告诉我们什么？", chapter)
        self.assertNotIn("不能提前看下面这张表", chapter)
        self.assertLess(chapter.index("我们试一条简单规则"),
                        chapter.index("股票已经选好了"))
        for fact in ("215.29", "198.67", "+7.64%", "-7.51%",
                     "954,338.69", "985,218.01", "100 万元"):
            self.assertIn(fact, chapter)

    def test_financial_quality_starts_with_three_connected_real_examples(self):
        chapter = read("真实_06a_合并报表与财务质量.md")
        self.assertIn("## 5. 怎样把更多财务项目联系起来看？", chapter)
        self.assertIn("先学会把有关系的项目放在一起看", chapter)
        self.assertIn("营收和应收账款", chapter)
        self.assertIn("净利润和经营现金流", chapter)
        self.assertIn("收入和存货", chapter)
        self.assertLess(chapter.index("## 5. 怎样把更多财务项目联系起来看？"),
                        chapter.index("选读｜还有哪些财务科目可以一起研究？"))
        self.assertIn("权责发生制", chapter)
        self.assertIn("按业务实际发生的期间确认收入和费用", chapter)
        self.assertIn("财务质量分析是寻找经营数据之间的联系", chapter)

    def test_ridge_is_introduced_after_weight_instability_problem(self):
        chapter = read("真实_11_线性模型.md")
        self.assertIn("## 3. 模型为什么常用标准化？", chapter)
        self.assertIn("## 4. 如果历史数据让模型学出了很极端的权重呢？", chapter)
        self.assertIn("## 5. 这四只真实股票够训练一个可靠模型吗？", chapter)
        self.assertLess(chapter.index("## 3. 模型为什么常用标准化？"),
                        chapter.index("## 4. 如果历史数据让模型学出了很极端的权重呢？"))
        self.assertLess(chapter.index("6 和 -5"),
                        chapter.index("这时候才有必要认识 **Ridge（岭回归）**"))
        self.assertIn("假设只用来理解算法", chapter.replace("这个假设只用来理解算法", "假设只用来理解算法"))
        self.assertIn("18 个非重叠观察期", chapter)

    def test_account_story_precedes_evaluation_metric_table(self):
        chapter = read("真实_14_评价与风险.md")
        self.assertIn("## 1. 同一次选股，为什么会有不一样的成绩？", chapter)
        self.assertLess(chapter.index("100 万元涨到 120 万元"),
                        chapter.index("| 指标 | 回答什么 | 不回答什么 |"))
        self.assertIn("累计收益 = 90万 ÷ 100万 − 1 = -10%", chapter)
        self.assertIn("从前期高点回撤 = 90万 ÷ 120万 − 1 = -25%", chapter)

    def test_spread_chart_appears_after_price_and_z_score_explanation(self):
        chapter = read("真实_专题A_协整与配对交易.md")
        graphic = "![宁德时代与比亚迪：真实历史相对价格，以及前段拟合关系在后段的偏离]"
        self.assertEqual(chapter.count(graphic), 1)
        self.assertLess(chapter.index("## 3. 价差与均值回归"),
                        chapter.index(graphic))
        self.assertLess(chapter.index("## 5. 怎么判断价差偏离得多不多？"),
                        chapter.index(graphic))
        self.assertLess(chapter.index("**Z-score（标准分数）**"),
                        chapter.index(graphic))
        self.assertIn("Z 约为 **-6.38**", chapter)
        self.assertIn("实际价格与前期参考关系相差很远", chapter)


if __name__ == "__main__":
    unittest.main()
