"""The reading site's first-time learning sequence uses genuine 2024 A-share prices."""
import unittest
from reader.build_reader import collect_documents

REAL_MAIN=[
    "教程/真实_阅读指南.md","教程/真实_起步一课.md",
    "教程/真实_Python入门.md","教程/真实_基础工具箱.md",
    "教程/真实_01_收益与基准.md","教程/真实_02_多期与复利.md",
    "教程/真实_03_历史K线与时点.md","教程/真实_04_特征与走势.md",
    "教程/真实_05_均线与算子.md","教程/真实_06_财务与预处理.md",
    "教程/真实_06a_合并报表与财务质量.md",
    "教程/真实_07_时间切分与泄漏.md","教程/真实_08_单因子评价.md",
    "教程/真实_09_成交与费用.md","教程/真实_10_多因子.md",
    "教程/真实_11_线性模型.md","教程/真实_12_树与森林.md",
    "教程/真实_13_逐步提升模型.md","教程/真实_14_评价与风险.md",
    "教程/真实_15_研究记录.md","教程/真实_16_综合练习.md",
    "教程/真实_研究边界.md",
]
class FoundationOrderTests(unittest.TestCase):
    def test_sidebar_is_real_stock_learning_path(self):
        docs=collect_documents()
        paths=[doc["path"] for doc in docs]
        self.assertEqual(paths,REAL_MAIN)
        self.assertEqual(len(paths),len(set(paths)))
        self.assertEqual(docs[3]["group"],"入门准备 · 认识量化研究")
        self.assertEqual(docs[4]["group"],"第一篇 · 收益计算与策略评价")
        self.assertEqual(docs[10]["group"],"第二篇 · 数据处理与因子研究")
        self.assertFalse(any("循环" in doc["group"] for doc in docs))
        lookup={doc["path"]:doc["group"] for doc in docs}
        self.assertEqual(lookup["教程/真实_11_线性模型.md"],"第四篇 · 机器学习与模型评价")

    def test_legacy_synthetic_chapters_are_not_in_sidebar(self):
        paths=[doc["path"] for doc in collect_documents()]
        for path in ("教程/00f_从一次选股认识量化.md",
                     "教程/00g_读懂第一段量化代码.md",
                     "教程/11_完整手算案例与实验操作.md"):
            self.assertNotIn(path,paths)


if __name__=="__main__":
    unittest.main()
