"""Check Markdown emphasis boundaries in published chapters.

In CommonMark, a closing ** immediately after punctuation is not right-flanking
when followed by another letter. For example, **Ridge（岭回归）**是在 can appear
with literal asterisks instead of bold text. Use whitespace after the closing
delimiter (or explicit HTML) to make the rendered emphasis unambiguous.
"""
import re
import unicodedata
import unittest

from reader.build_reader import collect_documents


class MarkdownBoldDelimiterTests(unittest.TestCase):
    def test_emphasis_ending_with_punctuation_has_safe_following_boundary(self):
        for doc in collect_documents():
            content = doc["content"]
            for match in re.finditer(r"\*\*([^*\n]+)\*\*", content):
                end_char = match.group(1)[-1]
                following = content[match.end():match.end() + 1]
                if (following and following.isalnum()
                        and unicodedata.category(end_char)[0] in ("P", "S")):
                    line = content.count("\n", 0, match.start()) + 1
                    self.fail(
                        f'{doc["path"]}:{line}: add a space after '
                        f'{match.group(0)!r} before {following!r} '
                        "(Markdown bold may render as literal **)"
                    )

    def test_affected_emphasis_is_preserved_in_published_book(self):
        docs = {doc["path"]: doc["content"] for doc in collect_documents()}
        samples = {
            "教程/真实_11_线性模型.md": "**Ridge（岭回归）** 是在",
            "教程/真实_10_多因子.md": "**214 元 + 7.64%** 并不是",
            "教程/真实_16_综合练习.md": "**RankIC（当时按指标排的名次，与后来按收益排的名次有多一致）** 怎样",
            "教程/真实_专题A_协整与配对交易.md": "**协整（Cointegration）** 研究的是",
        }
        for path, snippet in samples.items():
            with self.subTest(path=path):
                self.assertIn(snippet, docs[path])


if __name__ == "__main__":
    unittest.main()
