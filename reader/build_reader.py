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
    "第一编：研究问题与证据设计": "第一编 · 研究问题与证据设计",
    "第二编：构造并检验因子": "第二编 · 构造并检验因子",
    "第三编：从信号到组合": "第三编 · 从信号到组合",
    "第四编：检验模型是否增加信息": "第四编 · 模型比较",
    "第五编：复现与完整实训": "第五编 · 复现与完整实训",
    "参考资料与模板": "参考资料与模板",
}
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)(?:#[^)]*)?\)")


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
    shutil.copy2(ROOT / "reader" / "styles.css", output / "styles.css")
    shutil.copy2(ROOT / "reader" / "favicon.ico", output / "favicon.ico")
    shutil.copytree(ROOT / "reader" / "assets", output / "assets", dirs_exist_ok=True)
    payload = {
        "title": "A 股量化研究入门",
        "description": "沿研究问题、数据时点、因子、组合和模型比较编排的中文自学教材。",
        "documents": collect_documents(),
    }
    (output / "content.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Built {len(payload['documents'])} reading items at {output}")


if __name__ == "__main__":
    main()
