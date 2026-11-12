#!/usr/bin/env python3
"""Build the static reading site from the project Markdown chapters."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "教程" / "README.md"
GROUPS = {
    "阅读导览": "阅读导览",
    "基础准备：先找到常用工具（随学随查）": "基础准备 · 随学随查",
    "第一循环：这笔收益算不算本事？（第 1–2 章）": "第一循环 · 这笔收益算不算本事？",
    "第二循环：数据和因子可不可信？（第 3–8 章）": "第二循环 · 数据和因子可不可信？",
    "第三循环：信号能不能变成钱？（第 9–10 章）": "第三循环 · 信号能不能变成钱？",
    "第四循环：模型有没有增加信息？（第 11–14 章）": "第四循环 · 模型有没有增加信息？",
    "收尾：结论能不能重做？（第 15–16 章）": "收尾 · 结论能不能重做？",
    "进阶专题：从相关性到协整（第16章后选读）": "进阶专题 · 统计套利入门",
    "工具与参考": "工具与参考",
}
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)(?:#[^)]*)?\)")

RUNNABLE_SCRIPTS = [
    "examples/real_stock_learner.py",
]
RUNNABLE_DATA = [
    "data/real_a_share/teaching_case.json",
]
LABS = {
    "教程/真实_Python入门.md": {
        "kind": "real-data",
        "title": "用真实价格运行这段选股练习",
        "description": "读取教材保存的真实行情，直接在网页中计算四只股票的涨幅、组合金额与18期比较；无需下载Python运行环境。",
        "files": RUNNABLE_DATA,
        "scripts": [{"label":"计算真实股票选股结果", "script":"examples/real_stock_learner.py", "args": []}],
    },
    "教程/真实_08_单因子评价.md": {
        "kind": "real-data",
        "title": "核对真实股票的 RankIC",
        "description": "重算18个观察期的排名相关性；这些数字不代表已经获得实盘优势。",
        "files": RUNNABLE_DATA,
        "scripts": [{"label":"计算各期排名与收益", "script":"examples/real_stock_learner.py", "args": []}],
    },
    "教程/真实_16_综合练习.md": {
        "kind": "real-data",
        "title": "复核四只真实股票的全部手算",
        "description": "无需单独安装 Python，可在浏览器核对2024年固定行情。",
        "files": RUNNABLE_DATA,
        "scripts": [{"label":"重新计算选股与组合", "script":"examples/real_stock_learner.py", "args": []}],
    },
}


def estimate_minutes(markdown: str) -> int:
    readable = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    readable = re.sub(r"`[^`]*`", " ", readable)
    readable = re.sub(r"https?://\S+", " ", readable)
    chinese = len(re.findall(r"[\u3400-\u9fff]", readable))
    latin_words = len(re.findall(r"[A-Za-z0-9_]+", readable))
    return max(1, math.ceil((chinese + latin_words * 2) / 360))


def collect_documents() -> list[dict[str, str | int]]:
    documents: list[dict[str, str | int]] = []
    seen: set[str] = set()
    group = "阅读导览"

    for line in INDEX.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            group = GROUPS.get(heading.group(1), group)
        for label, link in LINK_RE.findall(line):
            source = (INDEX.parent / link.split("#", 1)[0]).resolve()
            try:
                source.relative_to(ROOT)
            except ValueError:
                continue
            if not source.is_file() or source.suffix.lower() != ".md":
                continue
            relative = source.relative_to(ROOT).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            markdown = source.read_text(encoding="utf-8")
            title = re.sub(r"\s+", " ", label.strip())
            documents.append({
                "path": relative,
                "title": title,
                "group": group,
                "minutes": estimate_minutes(markdown),
                "content": markdown,
            })

    if not documents:
        raise RuntimeError(f"No Markdown chapters found from {INDEX}")
    return documents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist-reader")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT not in output.parents:
        raise ValueError("Output must be a child directory of the repository root")

    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "reader" / "index.html", output / "index.html")
    shutil.copy2(ROOT / "reader" / "app.js", output / "app.js")
    shutil.copy2(ROOT / "reader" / "real-case.js", output / "real-case.js")
    shutil.copy2(ROOT / "reader" / "styles.css", output / "styles.css")
    shutil.copy2(ROOT / "reader" / "favicon.ico", output / "favicon.ico")
    shutil.copytree(ROOT / "reader" / "assets", output / "assets", dirs_exist_ok=True)
    shutil.copy2(ROOT / "reader" / "pyodide-worker.js", output / "pyodide-worker.js")
    for relative in RUNNABLE_SCRIPTS + RUNNABLE_DATA:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    payload = {
        "title": "A 股量化研究入门",
        "description": "以100万元课堂模拟账户和四只知名A股的真实历史K线贯穿课程，先手算再检验。",
        "documents": collect_documents(),
        "labs": LABS,
    }
    (output / "content.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Built {len(payload['documents'])} reading items at {output}")


if __name__ == "__main__":
    main()
