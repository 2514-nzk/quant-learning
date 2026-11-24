"""Cross-volume publication gates. No claim of market validation or peer review."""
import re
import unittest
from pathlib import Path
from reader.build_reader import collect_documents, collect_framework_documents, LABS

ROOT=Path(__file__).resolve().parents[1]


def scan_fences(markdown):
    # Markdown permits 0–3 spaces before a fence; a closing fence cannot carry info.
    opened=None
    prose=[]
    blocks=[]
    errors=[]
    for n,line in enumerate(markdown.splitlines(),1):
        m=re.match(r"^ {0,3}([~]{3,}|[\x60]{3,})(.*)$",line)
        if opened:
            if m and m[1][0]==opened[0][0] and len(m[1])>=len(opened[0]):
                if not m[2].strip():
                    blocks.append((opened[1],opened[2]))
                    opened=None
                else:
                    errors.append(f"line {n}: fence inside block from line {opened[1]} has info text")
            continue
        if m:
            opened=(m[1],n,m[2].strip())
        else:
            prose.append(line)
    if opened:
        errors.append(f"unclosed fence at {opened[1]}")
    return "\n".join(prose),blocks,errors


class PublicCourseQuality(unittest.TestCase):
    def test_all_published_pages_have_closed_fences_and_math(self):
        docs=collect_documents()+collect_framework_documents()
        self.assertEqual(len(docs),55)
        for doc in docs:
            with self.subTest(path=doc["path"]):
                prose,blocks,errors=scan_fences(doc["content"])
                self.assertEqual(errors,[])
                # Literal inline snippets are not display math.
                prose=re.sub(r"(\x60+)[^\n]*?\1","",prose)
                for a,b in ((r"\[",r"\]"),(r"\(",r"\)")):
                    self.assertEqual(prose.count(a),prose.count(b))
                self.assertTrue(doc["content"].startswith("# "))

    def test_toolbox_python_does_not_swallow_math(self):
        source=(ROOT/"教程/真实_基础工具箱.md").read_text("utf-8")
        prose,blocks,errors=scan_fences(source)
        self.assertEqual(errors,[])
        self.assertEqual([lang for _,lang in blocks],["python","formula"])
        self.assertIn("## 2. 数学",prose)

    def test_browser_lab_dependencies_are_present(self):
        docs={d["path"] for d in collect_documents()+collect_framework_documents()}
        for path,lab in LABS.items():
            with self.subTest(path=path):
                self.assertIn(path,docs)
                for file in lab["files"]+[s["script"] for s in lab["scripts"]]:
                    self.assertTrue((ROOT/file).is_file(),file)


if __name__=="__main__":
    unittest.main()
