"""Check that the published course index and newly expanded chapters link to real files."""
import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "教程"
MAIN_CHAPTERS = [
    "00_学习路线.md", "00f_从一次选股认识量化.md",
    "00g_读懂第一段量化代码.md",
    "01_研究问题定义.md",
    "01a_研究假设与研报复现.md", "02_数据与标签.md",
    "03_特征工程.md", "03a_因子表达式与算子.md",
    "03b_传统因子与预处理.md", "04_时间切分与泄漏.md",
    "08a_单因子研究与评价.md", "09_预测到组合.md",
    "09a_多因子合成与综合实训.md", "05_线性基线.md",
    "06_决策树与随机森林.md", "07_GBDT与LightGBM.md",
    "08_模型评价与解释.md", "10_研究框架与结课项目.md",
    "11_完整手算案例与实验操作.md",
    "00h_零基础16道小题.md",
    "进阶实战_从教学数据到研究级流程.md",
    "专题A_单因子到稳健性研究.md",
    "专题B_机器学习验证与增量检验.md",
    "真实A股K线_入门实例.md",
]


class CurriculumLinkTests(unittest.TestCase):
    def test_reading_index_and_chapter_local_links(self):
        paths = [COURSE / "README.md"] + [COURSE / name for name in MAIN_CHAPTERS]
        pattern = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")
        for source in paths:
            with self.subTest(source=source.name):
                self.assertTrue(source.is_file(), f"missing chapter: {source}")
                content = source.read_text(encoding="utf-8")
                for href in pattern.findall(content):
                    href = href.strip().split("#", 1)[0]
                    if not href or "://" in href or href.startswith(("mailto:", "tel:", "data:")):
                        continue
                    target = (source.parent / unquote(href)).resolve()
                    self.assertTrue(
                        target.is_relative_to(ROOT) and target.is_file(),
                        f"broken local link in {source.relative_to(ROOT)}: {href}",
                    )

    def test_four_level_track_is_discoverable(self):
        index = (COURSE / "README.md").read_text(encoding="utf-8")
        guide = (COURSE / "00_学习路线.md").read_text(encoding="utf-8")
        self.assertIn("进阶实战_从教学数据到研究级流程.md", index)
        self.assertIn("研究级", guide)
        self.assertIn("python examples/research_audit_lab.py", (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
