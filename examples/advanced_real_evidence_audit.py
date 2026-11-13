#!/usr/bin/env python3
"""Evidence-grade audit of the fixed REAL 2024 four-A-share teaching snapshot.

This is a retrospective, deliberately selected four-name example. Even when
source integrity and arithmetic checks pass, it is NOT historical PIT, an
independent OOS test, an executable backtest or an alpha demonstration.

Standard library only; never downloads, changes or silently repairs source.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from statistics import mean, stdev

from examples.advanced_factor_research_lab import hac_mean_se, moving_block_ci
from examples.real_stock_learner import rank_ic
from scripts.build_real_teaching_case import calculate_case, load_bars

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "real_a_share"
SOURCE_KIND = "REAL_OHLC_RETROSPECTIVE_FOUR_PRESELECTED_STOCKS"
EVIDENCE_GRADE = "DESCRIPTIVE_ONLY_NOT_HISTORICAL_PIT_NOT_INDEPENDENT_OOS"
EXPECTED_CODES = {"600519", "688256", "300750", "002594"}
SNAPSHOT_KEYS = {"trade_date", "symbol", "open", "high", "low", "close"}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document_hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
        allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_snapshot(root: Path = DATA) -> dict:
    """Verify source bytes and dates, not purported historical PIT availability."""
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    if manifest.get("adjust") != "none" or manifest.get("retriever") != "AKShare":
        raise ValueError("unknown snapshot adjustment or acquisition source")
    stamp = datetime.fromisoformat(manifest["captured_utc"])
    if stamp.tzinfo is None:
        raise ValueError("snapshot capture must contain a timezone")
    items = manifest.get("items", [])
    if {row["symbol"] for row in items} != EXPECTED_CODES or len(items) != 4:
        raise ValueError("four fixed named teaching stocks required")
    results = []
    for item in sorted(items, key=lambda item: item["symbol"]):
        name = Path(item["csv_path"])
        if name.parts[:2] != ("data", "real_a_share") or name.name != item["symbol"] + ".csv":
            raise ValueError("manifest path or symbol is inconsistent")
        path = root / name.name
        if file_hash(path) != item["csv_sha256"]:
            raise ValueError(f"CSV snapshot sha256 mismatch for {item['symbol']}")
        with path.open(encoding="utf-8", newline="") as handle:
            rd = csv.DictReader(handle)
            if not SNAPSHOT_KEYS.issubset(set(rd.fieldnames or [])):
                raise ValueError("required historical price columns absent")
            rows = list(rd)
        dates = [row["trade_date"] for row in rows]
        if len(rows) != item["records"] or not rows or dates != sorted(set(dates)):
            raise ValueError(f"duplicate, unordered or missing bar for {item['symbol']}")
        if dates[0] != item["first_date"] or dates[-1] != item["last_date"]:
            raise ValueError("manifest historical date range mismatch")
        for row in rows:
            if row["symbol"] != item["symbol"]:
                raise ValueError("CSV symbol mismatches manifest")
            date.fromisoformat(row["trade_date"])
            prices = {k: float(row[k]) for k in ("open", "high", "low", "close")}
            if any(not math.isfinite(x) or x <= 0 for x in prices.values()):
                raise ValueError("nonfinite/negative historical price")
            if prices["high"] + 1e-10 < max(prices["open"], prices["close"]) or (
                    prices["low"] - 1e-10 > min(prices["open"], prices["close"])):
                raise ValueError("inconsistent OHLC bar")
        results.append({"symbol": item["symbol"], "bars": len(rows),
                        "first_date": dates[0], "last_date": dates[-1],
                        "sha256": item["csv_sha256"], "source": item["source"]})
    return {"source": manifest["retriever"], "capture_timestamp": manifest["captured_utc"],
            "adjustment": manifest["adjust"], "files": results,
            "manifest_sha256": file_hash(root / "manifest.json"),
            "capture_after_market_period": stamp.date() >
                max(date.fromisoformat(x["last_date"]) for x in results)}


def compare_tree(actual: object, expected: object, context: str = "case") -> None:
    """Rebuild must match saved derived rows; do not trust a cached result alone."""
    if type(actual) is not type(expected):
        raise ValueError(f"{context}: incompatible types")
    if isinstance(actual, dict):
        if actual.keys() != expected.keys():
            raise ValueError(f"{context}: field drift")
        for key in actual:
            compare_tree(actual[key], expected[key], context + "." + key)
    elif isinstance(actual, list):
        if len(actual) != len(expected):
            raise ValueError(f"{context}: record count drift")
        for index, (left, right) in enumerate(zip(actual, expected)):
            compare_tree(left, right, f"{context}[{index}]")
    elif isinstance(actual, float):
        if not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=0, abs_tol=5e-8):
            raise ValueError(f"{context}: derived price calculation drift")
    elif actual != expected:
        raise ValueError(f"{context}: derived output mismatch")


def audit_timeline(rounds: list[dict]) -> dict:
    """All input anchors precede their own labels and rounds do not overlap."""
    if not rounds:
        raise ValueError("no rounds")
    last_exit = None
    for k, period in enumerate(rounds, start=1):
        if period["round_id"] != k:
            raise ValueError("non-sequential round identifiers")
        signal, entry, exit_day = (date.fromisoformat(period[key])
                                   for key in ("signal_date", "entry_date", "exit_date"))
        if not signal < entry <= exit_day:
            raise ValueError("invalid signal/entry/exit order")
        if last_exit is not None and not last_exit < signal:
            raise ValueError("overlapping study round or time-travel")
        last_exit = exit_day
        if {r["symbol"] for r in period["rows"]} != EXPECTED_CODES or len(period["rows"]) != 4:
            raise ValueError("missing or duplicate fixed-case constituent")
        for row in period["rows"]:
            if row["signal_date"] != period["signal_date"] or (
                    row["entry_date"] != period["entry_date"] or
                    row["exit_date"] != period["exit_date"]):
                raise ValueError("stock date does not agree with round")
            if date.fromisoformat(row["momentum_base_date"]) >= signal:
                raise ValueError("momentum feature includes nonhistorical anchor")
            if abs(row["signal_close"]/row["momentum_base_close"]-1-row["mom5"]) > 5e-8:
                raise ValueError("lookback momentum arithmetic mismatch")
            if abs(row["exit_close"]/row["entry_open"]-1-row["forward_return"]) > 5e-8:
                raise ValueError("forward label arithmetic mismatch")
    return {"round_count": len(rounds), "start_signal": rounds[0]["signal_date"],
            "last_signal": rounds[-1]["signal_date"],
            "last_label_end": rounds[-1]["exit_date"], "nonoverlap": True,
            "label_available_at_known": False,
            "intra_day_source_known_at_proven": False}


def _describe(rounds: list[dict]) -> dict:
    ics = [rank_ic(p["rows"]) for p in rounds]
    diffs = [p["top2_gross"]-p["all4_gross"] for p in rounds]
    return {"rounds": len(rounds), "mean_rank_ic": mean(ics),
            "positive_ic_rounds": sum(v > 0 for v in ics),
            "mean_top2_gross": mean(p["top2_gross"] for p in rounds),
            "mean_all4_gross": mean(p["all4_gross"] for p in rounds),
            "mean_top2_minus_equal4": mean(diffs),
            "top2_outperformance_rounds": sum(v > 0 for v in diffs)}


def evaluate_case(rounds: list[dict], reps: int = 1000, seed: int = 20261113) -> dict:
    """Statistics are descriptive on *already explored*, non-PIT historic prices."""
    if len(rounds) < 8 or reps < 100:
        raise ValueError("insufficient descriptive periods or bootstrap repetitions")
    audit_timeline(rounds)
    ics = [rank_ic(p["rows"]) for p in rounds]
    spread = [p["top2_gross"] - p["all4_gross"] for p in rounds]
    return {
        "all": _describe(rounds),
        "retrospective_reading_slices_not_oos": {
            "first_10": _describe(rounds[:10]),
            "middle_4": _describe(rounds[10:14]),
            "last_4_already_published": _describe(rounds[14:]),
        },
        "rank_ic": {
            "observations": ics,
            "icir_not_annualized": mean(ics)/stdev(ics),
            "hac_se_lag2": hac_mean_se(ics, 2),
            "circular_block_ci_mean_block2": moving_block_ci(ics, block=2, reps=reps, seed=seed),
            "circular_block_ci_mean_block3": moving_block_ci(ics, block=3, reps=reps, seed=seed),
            "circular_block_ci_mean_block4": moving_block_ci(ics, block=4, reps=reps, seed=seed),
            "leave_one_round_out_mean_range": [min(mean(ics[:i]+ics[i+1:])
                                                     for i in range(len(ics))),
                                                max(mean(ics[:i]+ics[i+1:])
                                                     for i in range(len(ics)))],
        },
        "top2_minus_equal4": {
            "observations": spread,
            "hac_se_lag2": hac_mean_se(spread, 2),
            "circular_block_ci_mean_block3": moving_block_ci(spread, block=3, reps=reps, seed=seed),
        },
        "method": {
            "bootstrap": "circular moving-block percentile interval (descriptive only)",
            "resamples": reps, "seed": seed,
            "ic_grouping": "one cross-section of four retrospectively chosen stocks per date",
            "label": "next-session open to designated exit close, unadjusted, idealized",
            "benchmark": "same four-name equally weighted gross observation return",
            "split_status": "already explored by authors/readers; no untouched OOS",
        },
    }


def run_audit(root: Path = DATA, reps: int = 1000, seed: int = 20261113) -> dict:
    audit = validate_snapshot(root)
    saved = json.loads((root / "teaching_case.json").read_text("utf-8"))
    reconstructed = calculate_case(load_bars(root))
    compare_tree(saved, reconstructed)
    timeline = audit_timeline(saved["rounds"])
    return {
        "source_kind": SOURCE_KIND,
        "evidence_grade": EVIDENCE_GRADE,
        "snapshot": audit,
        "derived_case_sha256": file_hash(root / "teaching_case.json"),
        "timeline": timeline,
        "stats": evaluate_case(saved["rounds"], reps=reps, seed=seed),
        "gates": {
            "L0_source_file_integrity": "PASS",
            "L1_derived_price_arithmetic": "PASS",
            "L2_signal_label_date_order": "PASS",
            "L3_2024_historical_PIT_availability": "NOT_PROVEN",
            "L4_historical_full_universe": "FAIL_SELECTED_SURVIVORS",
            "L5_corporate_actions_total_return": "NOT_PROVEN",
            "L6_independent_OOS": "FAIL_PREVIOUSLY_EXPLORED",
            "L7_actual_execution_and_fees": "NOT_PROVEN",
        },
        "limitations": [
            "Four famous named stocks selected retrospectively, not a PIT full A-share universe.",
            "AKShare CSV capture in 2026 does not establish provider release/receipt in 2024.",
            "Close-based MOM5 only known after signal day's close; not tradable at same close.",
            "Unadjusted OHLC lacks dividends and corporate action total-return accounting.",
            "No order-book, queue, limit, halt, trading fees, slippage or short availability.",
            "18 periods and four names cannot establish robust cross-sectional alpha.",
            "All three displayed date slices were published/explored, NOT untouched OOS.",
            "Block CI/HAC are sensitivity descriptions, not confirmatory p-values.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="write a new audit report; refuse overwrite")
    parser.add_argument("--resamples", type=int, default=1000)
    options = parser.parse_args()
    report = run_audit(reps=options.resamples)
    body = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if options.output:
        if options.output.exists():
            raise FileExistsError("refuse to overwrite prior research evidence")
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(body+"\n", encoding="utf-8")
        print(f"Created descriptive evidence report: {options.output}")
    elif options.json:
        print(body)
    else:
        stats = report["stats"]["all"]
        print("REAL 2024 OHLC / RETROSPECTIVELY CHOSEN FOUR NAMES / NOT OOS")
        print(f"{stats['rounds']} rounds: mean RankIC={stats['mean_rank_ic']:+.4f}")
        print(f"Top2 minus equal4 mean gross gap={stats['mean_top2_minus_equal4']:+.4%}")
        print("Evidence: descriptive only; PIT, full-universe, OOS and fills unproven.")


if __name__ == "__main__":
    main()
