#!/usr/bin/env python3
"""Beginner-to-research audit for the artificial A/B/C/D learning dataset.

Only Python's standard library is required. This is not a real-market backtest.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "story" / "rounds.csv"


def average_ranks(values: list[float]) -> list[float]:
    """Return ascending ranks starting at 1, with average ranks for ties."""
    if not values:
        return []
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][1] == ordered[i][1]:
            j += 1
        average = ((i + 1) + j) / 2
        for k in range(i, j):
            result[ordered[k][0]] = average
        i = j
    return result


def spearman(left: list[float], right: list[float]) -> float | None:
    """Spearman correlation (Pearson correlation of average ranks)."""
    if len(left) != len(right):
        raise ValueError("RankIC requires aligned observations")
    if len(left) < 2:
        return None
    a, b = average_ranks(left), average_ranks(right)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    numerator = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    return numerator / math.sqrt(va * vb) if va > 0 and vb > 0 else None


def load_rows(path: Path = DEFAULT_CSV) -> list[dict]:
    """Read the fixed teaching file without training a model."""
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "round_id", "signal_day", "entry_day", "exit_day",
            "feature_available_day", "code", "mom_5", "ep", "roe", "fwd_return",
        }
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("Input CSV is missing required columns")
        for raw in reader:
            row = {key: int(raw[key]) for key in (
                "round_id", "signal_day", "entry_day", "exit_day",
                "feature_available_day",
            )}
            row["code"] = raw["code"]
            for key in ("mom_5", "ep", "roe", "fwd_return"):
                row[key] = float(raw[key])
                if not math.isfinite(row[key]):
                    raise ValueError(f"Non-finite {key} for {row['code']}")
            rows.append(row)
    if not rows:
        raise ValueError("No data rows were found")
    return rows


def select_top_two(rows: list[dict]) -> list[str]:
    """Selection depends only on past momentum and a deterministic tie break."""
    chosen = sorted(rows, key=lambda row: (-row["mom_5"], row["code"]))[:2]
    return [row["code"] for row in chosen]


def audit(rows: list[dict]) -> dict:
    """Audit PIT, label/decision order, fold boundaries, and rank statistics."""
    grouped = defaultdict(list)
    seen = set()
    for row in rows:
        key = (row["round_id"], row["code"])
        if key in seen:
            raise ValueError(f"Duplicate round/code: {key}")
        seen.add(key)
        if row["feature_available_day"] > row["signal_day"]:
            raise ValueError(f"Feature is not yet available: {key}")
        if not row["signal_day"] < row["entry_day"] <= row["exit_day"]:
            raise ValueError(f"Invalid entry/exit timing: {key}")
        grouped[row["round_id"]].append(row)

    periods = sorted(grouped)
    if periods != list(range(periods[0], periods[-1] + 1)):
        raise ValueError("Round identifiers are not contiguous")
    by_period = []
    for period in periods:
        group = grouped[period]
        if len({r["signal_day"] for r in group}) != 1:
            raise ValueError(f"Conflicting signal days: R{period}")
        selected = select_top_two(group)
        chosen = [r for r in group if r["code"] in selected]
        if len(chosen) != 2:
            raise ValueError(f"Fewer than two eligible stocks: R{period}")
        gross = sum(r["fwd_return"] for r in chosen) / 2
        benchmark = sum(r["fwd_return"] for r in group) / len(group)
        ic = spearman(
            [r["mom_5"] for r in group],
            [r["fwd_return"] for r in group],
        )
        by_period.append({
            "round_id": period,
            "stocks": len(group),
            "selected": selected,
            "gross_return": gross,
            "equal_weight_benchmark": benchmark,
            "rank_ic": ic,
        })

    fold_ranges = ((1, 36), (37, 46), (47, 60))
    checks = []
    for (a, b), (c, d) in zip(fold_ranges, fold_ranges[1:]):
        first = [r for r in rows if a <= r["round_id"] <= b]
        second = [r for r in rows if c <= r["round_id"] <= d]
        if not first or not second:
            raise ValueError("Teaching dataset must include all three fixed folds")
        last_label = max(r["exit_day"] for r in first)
        first_signal = min(r["signal_day"] for r in second)
        if last_label >= first_signal:
            raise ValueError(f"Training label crosses validation decision: R{b}/R{c}")
        checks.append({
            "train_end_round": b,
            "next_start_round": c,
            "max_train_label_end_day": last_label,
            "min_next_signal_day": first_signal,
            "passes": True,
        })

    ic_values = [r["rank_ic"] for r in by_period if r["rank_ic"] is not None]
    return {
        "note": "Artificial teaching data; no real-market profitability claim",
        "round_count": len(periods),
        "row_count": len(rows),
        "boundaries": checks,
        "first_round": by_period[0],
        "mean_rank_ic": sum(ic_values) / len(ic_values) if ic_values else None,
        "defined_ic_rounds": len(ic_values),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json", action="store_true", help="Print complete JSON summary")
    args = parser.parse_args()
    report = audit(load_rows(args.csv))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    first = report["first_round"]
    print(f"审计完成：{report['round_count']} 期，{report['row_count']} 条人工样本")
    print("时间边界：" + "；".join(
        f"R{x['train_end_round']}→R{x['next_start_round']} 合格"
        for x in report["boundaries"]
    ))
    print(
        f"首期：{','.join(first['selected'])}，毛收益 {first['gross_return']:.2%}，"
        f"四股等权基准 {first['equal_weight_benchmark']:.2%}，"
        f"RankIC {first['rank_ic']:.2f}"
    )
    print("注意：通过时间审计不代表真实市场有效，也不包含真实成交回放。")


if __name__ == "__main__":
    main()
