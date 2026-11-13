#!/usr/bin/env python3
"""Inspect a public aggregate evidence report; optionally reproduce against private Parquet.

The committed JSON contains COUNTS, not source rows. A local duckdb installation
is required ONLY with --verify-parquet. No network, writes or hidden uploads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "advanced" / "volume-2" / "local_all_a_2024_aggregate.json"


def validate(report: dict) -> dict:
    if report.get("evidence_grade") != "REAL_LOCAL_SNAPSHOT_AGGREGATES_ONLY_NOT_PIT_CERTIFIED":
        raise ValueError("incorrect evidence grade")
    origin, snap, year = report["origin"], report["snapshot"], report["year_2024"]
    if origin["raw_data_included"] is not False:
        raise ValueError("never distribute source rows in this evidence report")
    if snap["year_2024"] != year["row_count"] or snap["partition_count"] != 17:
        raise ValueError("year/partition manifest mismatch")
    if not re.fullmatch(r"[a-f0-9]{64}", year["sha256"]):
        raise ValueError("invalid frozen source SHA")
    matrix = year["exchange_quote_rows"]
    if set(matrix) != {"SH", "SZ", "BJ"}:
        raise ValueError("unrecognized exchange groups")
    for group in matrix.values():
        if any(type(x) is not int or x < 0 for x in group.values()):
            raise ValueError("invalid coverage counts")
    per_exchange = {k: v["quote_present"] + v["quote_missing"]
                    for k, v in matrix.items()}
    if sum(per_exchange.values()) != year["row_count"]:
        raise ValueError("quote numerator and denominator mismatch")
    day = year["example_day"]
    if sum(day["exchange_rows"].values()) != day["quote_present"] + day["quote_missing"]:
        raise ValueError("day exchange/quote counts disagree")
    n = sum(day["exchange_rows"].values())
    if day["is_trading_true"] + day["is_trading_false"] + day["is_trading_unknown"] != n:
        raise ValueError("day trading states disagree")
    if day["is_st_true"] + day["is_st_false"] != n:
        raise ValueError("day ST states disagree")
    if any(report["claims"][name] is not False for name in (
        "authoritative_full_market_denominator_verified",
        "independently_verified_event_time_PIT",
        "cross_source_price_status_completeness_verified",
        "independent_OOS_verified",
        "tradable_alpha_verified",
    )):
        raise ValueError("unverified claim promoted to proven")
    if report["claims"]["true_full_market_coverage_percent"] is not None:
        raise ValueError("unknown full market denominator requires null")
    return {
        "evidence_grade": report["evidence_grade"],
        "frozen_snapshot_id": origin["snapshot_id"],
        "year_2024_rows": year["row_count"],
        "observed_quotes": sum(x["quote_present"] for x in matrix.values()),
        "missing_quotes": sum(x["quote_missing"] for x in matrix.values()),
        "by_exchange": per_exchange,
        "full_market_coverage": None,
        "historical_pit_verified": False,
        "raw_data_embedded": False,
    }


def verify_private_parquet(path: Path, report: dict) -> None:
    """Only user-local replay, never used by CI without private dataset access."""
    if not path.is_file():
        raise FileNotFoundError(path)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != report["year_2024"]["sha256"]:
        raise ValueError("private Parquet SHA changed; refuse stale reported figures")
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("optional local validation requires: pip install duckdb") from exc
    conn = duckdb.connect(":memory:", read_only=False)
    try:
        rows = conn.execute(
            "SELECT exchange, has_daily_quote, COUNT(*) FROM read_parquet(?) "
            "GROUP BY exchange, has_daily_quote",
            [str(path)]
        ).fetchall()
        observed = {k: {"quote_present": 0, "quote_missing": 0}
                    for k in ("SH", "SZ", "BJ")}
        for exchange, present, count in rows:
            if exchange not in observed or present is None:
                raise ValueError("unknown exchange or quote presence in Parquet")
            observed[exchange]["quote_present" if present else "quote_missing"] += count
        if observed != report["year_2024"]["exchange_quote_rows"]:
            raise ValueError("private Parquet and published aggregate disagree")
        keys = conn.execute(
            "SELECT COUNT(*) FROM (SELECT trade_date, code, COUNT(*) AS n "
            "FROM read_parquet(?) GROUP BY 1,2 HAVING n>1)", [str(path)]
        ).fetchone()[0]
        if keys != report["year_2024"]["duplicate_trade_date_code_groups"]:
            raise ValueError("duplicate security-day check mismatch")
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--verify-parquet", type=Path,
                    help="local private 2024 Parquet file (never uploaded)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    source = json.loads(args.report.read_text(encoding="utf-8"))
    result = validate(source)
    if args.verify_parquet:
        verify_private_parquet(args.verify_parquet, source)
        result["private_parquet_verified"] = True
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print("Snapshot:", result["frozen_snapshot_id"])
        print("2024 membership rows:", result["year_2024_rows"])
        print("Observed/missing quote rows:",
              result["observed_quotes"], result["missing_quotes"])
        print("Source contents and historical PIT are not published or certified.")


if __name__ == "__main__":
    main()
