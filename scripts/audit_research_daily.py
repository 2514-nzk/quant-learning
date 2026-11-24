#!/usr/bin/env python3
"""Summarize a local AKShare snapshot without publishing raw market data."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_missing_report(output: Path, data_dir: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "# 当前沪深300日线批量采集审计\n\n"
        "**状态：未生成 manifest，无法核验任何行情文件。**\n\n"
        f"采集目录：{data_dir}。请检查 AKShare 安装、指数成分接口和网络请求日志后重试。\n",
        encoding="utf-8",
    )


def audit(data_dir: Path, output: Path) -> dict:
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.is_file():
        write_missing_report(output, data_dir)
        return {"manifest_found": False, "integrity_ok": False, "collection_complete": False}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    universe_path = data_dir / "universe.csv"
    universe = []
    if universe_path.is_file():
        with universe_path.open(encoding="utf-8-sig", newline="") as handle:
            universe = list(csv.DictReader(handle))
    expected = manifest.get("expected_files", 2 * len(universe))
    items = manifest.get("items", [])
    successes = [item for item in items if item.get("status") == "OK"]
    failures = [item for item in items if item.get("status") != "OK"]
    year_stats = {
        adjust: defaultdict(lambda: {"rows": 0, "symbols": set()})
        for adjust in ("raw", "qfq")
    }
    source_counts = defaultdict(int)
    missing_files = []
    hash_mismatches = []
    row_mismatches = []
    nonpositive_qfq_close = 0
    actual_rows = 0
    actual_first = None
    actual_last = None
    by_symbol = defaultdict(set)

    for item in successes:
        relative = item.get("path")
        path = data_dir / str(relative)
        if not path.is_file():
            missing_files.append(str(relative))
            continue
        if sha256(path) != item.get("sha256"):
            hash_mismatches.append(str(relative))
        source = item.get("source", "")
        adjust = item.get("adjust", "")
        source_counts[source] += 1
        by_symbol[item.get("symbol", "")].add(adjust)
        date_col, close_col = (
            ("日期", "收盘") if source.endswith("_em") else ("date", "close")
        )
        file_rows = 0
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if date_col not in (reader.fieldnames or []) or close_col not in (reader.fieldnames or []):
                row_mismatches.append(str(relative) + ":missing required date/close column")
                continue
            for row in reader:
                day = str(row.get(date_col, ""))[:10].replace("-", "")
                if len(day) != 8 or not day.isdigit():
                    row_mismatches.append(str(relative) + ":invalid date")
                    continue
                year = day[:4]
                year_stats.setdefault(adjust, defaultdict(lambda: {"rows": 0, "symbols": set()}))
                year_stats[adjust][year]["rows"] += 1
                year_stats[adjust][year]["symbols"].add(item.get("symbol", ""))
                try:
                    close = float(row[close_col])
                except (TypeError, ValueError):
                    row_mismatches.append(str(relative) + ":invalid close")
                    continue
                if adjust == "qfq" and close <= 0:
                    nonpositive_qfq_close += 1
                file_rows += 1
                actual_rows += 1
                actual_first = day if actual_first is None else min(actual_first, day)
                actual_last = day if actual_last is None else max(actual_last, day)
        if file_rows != item.get("rows"):
            row_mismatches.append(
                f"{relative}:manifest rows={item.get('rows')} actual rows={file_rows}"
            )

    complete_pairs = sum(
        1 for item in universe
        if by_symbol.get(item.get("symbol", ""), set()) >= {"raw", "qfq"}
    )
    integrity_ok = not (missing_files or hash_mismatches or row_mismatches)
    collection_complete = len(successes) == expected and not failures and not missing_files
    report = {
        "manifest_found": True,
        "universe_count": len(universe),
        "expected_files": expected,
        "reported_successful_files": len(successes),
        "reported_failed_files": len(failures),
        "actual_rows": actual_rows,
        "complete_raw_qfq_pairs": complete_pairs,
        "mixed_provider_pairs": manifest.get("mixed_provider_pairs", []),
        "source_counts": dict(source_counts),
        "missing_files": missing_files,
        "hash_mismatches": hash_mismatches,
        "row_mismatches": row_mismatches,
        "nonpositive_qfq_close_rows": nonpositive_qfq_close,
        "first_date": actual_first,
        "last_date": actual_last,
        "integrity_ok": integrity_ok,
        "collection_complete": collection_complete,
        "year_stats": year_stats,
        "universe_source": manifest.get("universe_source", {}),
        "historical_pit_proven": manifest.get("historical_pit_proven", False),
        "historical_dynamic_membership_proven": manifest.get("historical_dynamic_membership_proven", False),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 当前沪深300固定名单日线数据审计",
        "",
        f"> 抓取时间：{manifest.get('started_at', '未知')} 至 {manifest.get('finished_at', '未完成')}",
        "",
        "## 样本身份",
        "",
        f"- 股票名单：{report['universe_source'].get('type', '未声明')}",
        f"- 名单证券数：{len(universe)}",
        f"- 请求区间：{manifest.get('start')} 至 {manifest.get('end')}",
        f"- 实际行情日期覆盖：{actual_first or '无'} 至 {actual_last or '无'}",
        "- 该名单是**抓取时点的当前沪深300成分固定名单**，不是 2016—2025 年逐期历史成分。",
        "- 历史动态成分与退市证券未恢复，不能据此声称无幸存者偏差或全市场 PIT。",
        "",
        "## 文件与完整性",
        "",
        f"- 预期文件：{expected}",
        f"- 成功文件：{len(successes)}",
        f"- 失败文件：{len(failures)}",
        f"- 采集是否完整：{'是' if collection_complete else '否'}",
        f"- 完整 raw/qfq 配对：{complete_pairs} / {len(universe)}",
        f"- 实际读取行数：{actual_rows:,}",
        f"- SHA-256 / 行数 / 日期字段检查：{'通过' if integrity_ok else '发现问题'}",
        f"- qfq 收盘价非正的行数：{nonpositive_qfq_close}",
        "",
        "### 数据源",
        "",
        "| AKShare 接口 | 文件数 |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in sorted(source_counts.items()))
    lines.extend([
        "",
        "### 年度覆盖（仅统计抓取成功的文件）",
        "",
        "| 年份 | raw 行数 | raw 股票数 | qfq 行数 | qfq 股票数 |",
        "|---:|---:|---:|---:|---:|",
    ])
    for year in range(2016, 2026):
        raw = year_stats["raw"][str(year)]
        qfq = year_stats["qfq"][str(year)]
        lines.append(
            f"| {year} | {raw['rows']:,} | {len(raw['symbols'])} | "
            f"{qfq['rows']:,} | {len(qfq['symbols'])} |"
        )
    lines.extend([
        "",
        "## 研究边界",
        "",
        "本报告只核验抓取覆盖和文件完整性，不计算因子 IC、组合收益或策略胜率。raw 是不复权报价，qfq 是本次抓取的前复权快照；qfq 历史值可能被后续公司行为重述，且非正价格不能直接用于价格比率。成交与总回报研究仍需独立公司行为账本。",
        "",
        "**这是一份数据覆盖试验，不是策略回测结论。** 原始数百只股票行情只保留在临时运行目录，不上传到公开仓库；本文件仅保存聚合审计结果。",
        "",
    ])
    if failures:
        lines.append(f"失败项目数：{len(failures)}。具体代码和错误留在本次临时 manifest，未随报告公开。")
    if missing_files or hash_mismatches or row_mismatches:
        lines.extend(["", "### 完整性问题", ""])
        lines.extend(f"- 缺失文件：{x}" for x in missing_files)
        lines.extend(f"- 哈希不匹配：{x}" for x in hash_mismatches)
        lines.extend(f"- 行数/字段问题：{x}" for x in row_mismatches)
    output.write_text("\n".join(lines), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.data_dir, args.output)
    print(json.dumps({key: report.get(key) for key in (
        "manifest_found", "universe_count", "expected_files",
        "reported_successful_files", "reported_failed_files",
        "collection_complete", "integrity_ok", "actual_rows",
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
