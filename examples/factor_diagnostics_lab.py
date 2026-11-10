#!/usr/bin/env python3
"""A transparent factor-research lab on the artificial 60-round teaching fixture.

Python standard library only. The scores, labels and prices are not A-share data.
Fold-level test statistics are descriptive, not a procedure for selecting factors.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from statistics import mean, stdev

from examples.research_audit_lab import audit, average_ranks, load_rows, spearman

FACTOR_NAMES = ("mom_5", "ep", "roe", "equal_rank")
FOLDS = (("train", 1, 36), ("validation", 37, 46), ("test", 47, 60))


def score_round(rows: list[dict], factor: str) -> dict[str, float]:
    """No future return or label is read while producing scores."""
    if factor not in FACTOR_NAMES:
        raise ValueError(f"Unknown factor: {factor}")
    if factor == "equal_rank":
        n = len(rows)
        ranks = {
            key: average_ranks([r[key] for r in rows])
            for key in ("mom_5", "ep", "roe")
        }
        return {
            row["code"]: sum(ranks[key][i] / n for key in ranks) / 3
            for i, row in enumerate(rows)
        }
    return {row["code"]: row[factor] for row in rows}


def round_metrics(rows: list[dict], factor: str) -> dict:
    """Four-stock Top-2 vs bottom-2 descriptive comparison."""
    if len(rows) != 4 or len({r["code"] for r in rows}) != 4:
        raise ValueError("The teaching high/low split requires exactly four stocks")
    scores = score_round(rows, factor)
    ordered = sorted(rows, key=lambda r: (-scores[r["code"]], r["code"]))
    top, bottom = ordered[:2], ordered[2:]
    top_return = mean(r["fwd_return"] for r in top)
    bottom_return = mean(r["fwd_return"] for r in bottom)
    benchmark = mean(r["fwd_return"] for r in rows)
    return {
        "round_id": rows[0]["round_id"],
        "selected": [r["code"] for r in top],
        "rank_ic": spearman(
            [scores[r["code"]] for r in rows],
            [r["fwd_return"] for r in rows],
        ),
        "top2_gross": top_return,
        "bottom2_gross": bottom_return,
        "top_minus_bottom": top_return - bottom_return,
        "benchmark_gross": benchmark,
    }


def summarize(records: list[dict], fee: float) -> dict:
    """ICIR uses sample standard deviation at the *round*, not stock, level."""
    if not 0 <= fee < 1:
        raise ValueError("Fee per side must be in [0, 1)")
    ics = [r["rank_ic"] for r in records if r["rank_ic"] is not None]
    ic_std = stdev(ics) if len(ics) >= 2 else None
    icir = mean(ics) / ic_std if ic_std is not None and ic_std > 0 else None
    wealth = 8000.0
    reference = 8000.0
    replacements = []
    previous = None
    for row in records:
        factor = (1 - fee) / (1 + fee)
        wealth *= (1 + row["top2_gross"]) * factor
        reference *= (1 + row["benchmark_gross"]) * factor
        current = set(row["selected"])
        if previous is not None:
            replacements.append(1 - len(current & previous) / 2)
        previous = current
    return {
        "periods": len(records),
        "defined_ic_periods": len(ics),
        "mean_ic": mean(ics) if ics else None,
        "sample_std_ic": ic_std,
        "icir_per_round": icir,
        "positive_ic_ratio": mean(x > 0 for x in ics) if ics else None,
        "mean_top_minus_bottom": mean(r["top_minus_bottom"] for r in records),
        "mean_selection_replacement": mean(replacements) if replacements else None,
        "net_top2_final_money": wealth,
        "net_equal_weight_final_money": reference,
        "net_terminal_wealth_difference": wealth - reference,
    }


def report(rows: list[dict], factor: str = "mom_5", fee: float = 0.001) -> dict:
    if factor not in FACTOR_NAMES:
        raise ValueError("Choose a supported factor")
    audit(rows)  # Reject unavailable inputs and crossed teaching fold boundaries.
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["round_id"]].append(row)
    all_rounds = [round_metrics(grouped[i], factor) for i in sorted(grouped)]
    phases = {}
    for name, start, end in FOLDS:
        selected = [r for r in all_rounds if start <= r["round_id"] <= end]
        phases[name] = {
            "round_span": [start, end],
            **summarize(selected, fee),
        }
    return {
        "disclaimer": "Artificial fixture, descriptive; no real-market claim",
        "factor": factor,
        "fee_per_side": fee,
        "pricing": "fractional positions, all orders filled, liquidation every round",
        "n_stocks_per_round": 4,
        "rounds": all_rounds,
        "phases": phases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor", choices=FACTOR_NAMES, default="mom_5")
    parser.add_argument("--fee", type=float, default=0.001)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = report(load_rows(), factor=args.factor, fee=args.fee)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return
    print(f"人工案例 / 因子 {args.factor} / 单边费率 {args.fee:.2%}")
    first = result["rounds"][0]
    print(
        f"R01 Top-2 {','.join(first['selected'])}；"
        f"RankIC {first['rank_ic']:.2f}；"
        f"高减低 {first['top_minus_bottom']:.2%}"
    )
    for name, stats in result["phases"].items():
        print(
            f"{name:10s} R{stats['round_span'][0]:02d}–R{stats['round_span'][1]:02d} "
            f"IC={stats['mean_ic']:.4f} ICIR/期={stats['icir_per_round']:.3f} "
            f"Top-2期末={stats['net_top2_final_money']:.2f} "
            f"基准期末={stats['net_equal_weight_final_money']:.2f}"
        )
    print("注意：测试期仅供固定候选的描述性评价，不要根据其成绩倒选因子。")


if __name__ == "__main__":
    main()
