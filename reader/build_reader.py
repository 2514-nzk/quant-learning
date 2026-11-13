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
    "入门准备｜认识量化研究": "第一卷｜导读与准备",
    "入门准备｜基础工具箱（随学随查）": "第一卷｜导读与准备",
    "第一篇｜收益计算与策略评价（第 1–2 章）": "第一卷｜第 01–02 章 · 收益评价",
    "第二篇｜数据处理与因子研究（第 3–8 章）": "第一卷｜第 03–08 章 · 因子研究",
    "第三篇｜交易执行与策略组合（第 9–10 章）": "第一卷｜第 09–10 章 · 交易组合",
    "第四篇｜机器学习与模型评价（第 11–14 章）": "第一卷｜第 11–14 章 · 机器学习",
    "第五篇｜研究复现与综合实践（第 15–16 章）": "第一卷｜第 15–16 章 · 研究复现",
    "延伸阅读｜工具与参考": "第一卷｜附录与参考",
}
CHAPTER_PATH = re.compile(r"^(?:教程/真实_|advanced/volume-[23]/)(\d{2})_[^/]+\.md$")


def sidebar_title(path: str, label: str) -> str:
    """Canonical UI title; preserve Markdown titles and stable file paths."""
    label = re.sub(r"\s+", " ", label.strip())
    match = CHAPTER_PATH.match(path)
    if match:
        label = re.sub(r"^第\s*\d{1,2}\s*章\s*[｜|:：·—-]?\s*", "", label)
        return f"第 {int(match.group(1)):02d} 章｜{label}"
    if path.endswith("/README.md"):
        volume = "第二卷" if "volume-2/" in path else "第三卷"
        return f"导读｜{volume}课程目录"
    if path.endswith("/REAL_DATA_EVIDENCE_REVIEW.md"):
        return "附录 A｜真实价格证据审计"
    if path.endswith("/REVIEW_BACKLOG.md"):
        return "附录 B｜研究级审校台账"
    if path.endswith("/HISTORICAL_UNIVERSE_SOURCE_AUDIT.md"):
        return "附录 C｜教材数据集与复现规范"
    return label

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
    group = "入门准备 · 认识量化研究"

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
            title = sidebar_title(relative, label)
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


# Advanced volumes are separate from the already verified first-volume route.
# Do not change collect_documents(): first-volume ordering is a published contract.
FRAMEWORK_VOLUMES = (
    ("advanced/volume-2/README.md", "第二卷｜导读与目录", "第二卷课程目录"),
    ("advanced/volume-3/README.md", "第三卷｜导读与目录", "第三卷课程目录"),
)


def collect_framework_documents() -> list[dict[str, str | int]]:
    """Read explicitly linked chapter outlines from both volume indices."""
    documents: list[dict[str, str | int]] = []
    for index_path, group, title in FRAMEWORK_VOLUMES:
        index = (ROOT / index_path).resolve()
        index_content = index.read_text(encoding="utf-8")
        documents.append({
            "path": index_path,
            "title": sidebar_title(index_path, title),
            "group": group,
            "minutes": estimate_minutes(index_content),
            "content": index_content,
        })
        seen: set[str] = set()
        for label, href in LINK_RE.findall(index_content):
            chapter = (index.parent / href.split("#", 1)[0]).resolve()
            if not chapter.is_relative_to(index.parent) or not chapter.is_file() or chapter.suffix.lower() != ".md":
                continue
            path = chapter.relative_to(ROOT).as_posix()
            if path in seen or path == index_path:
                continue
            seen.add(path)
            content = chapter.read_text(encoding="utf-8")
            volume = "第二卷" if "volume-2/" in path else "第三卷"
            page_group = (
                f"{volume}｜第 01–{'14' if volume == '第二卷' else '13'} 章 · "
                f"{'研究方法' if volume == '第二卷' else '策略实战'}"
                if CHAPTER_PATH.match(path) else f"{volume}｜附录与审计"
            )
            documents.append({
                "path": path,
                "title": sidebar_title(path, label),
                "group": page_group,
                "minutes": estimate_minutes(content),
                "content": content,
            })
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
        "framework": collect_framework_documents(),
        "labs": LABS,
    }
    (output / "content.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Built {len(payload['documents'])} reading items at {output}")


if __name__ == "__main__":
    main()
