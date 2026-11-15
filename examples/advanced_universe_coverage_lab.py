#!/usr/bin/env python3
"""Audit declared historical stock-universe coverage without inventing a denominator.

Two deliberately different modes:
  --real-teaching   Audits the repo's REAL four-preselected-stock OHLC snapshot.
  --input PATH      Audits a LOCAL candidate PIT membership/price/fact JSON.
  (no args)         Audits a clearly marked SYNTHETIC illustrative fixture.

No external-data acquisition, no network connection, no trading; never promotes
self-declared source timestamps into independently verified historical PIT.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.advanced_pit_intake_lab import (  # noqa: E402
    EXCHANGE_TZ, KINDS, SCOPES, aware, day, demo_payload,
    facts_asof, membership_asof, source_gate, text_field,
)
from examples.advanced_real_evidence_audit import DATA, validate_snapshot  # noqa: E402

LAYER_NAMES = ("SECURITY_MASTER", "HISTORICAL_MEMBERSHIP", "INDUSTRY_PIT",
               "OHLC", "CORPORATE_ACTIONS", "DISCLOSURES_AND_REVISIONS",
               "EXCHANGE_SESSIONS", "EXECUTION_STATUS")
PRICE_KEYS = ("security_id", "trade_date", "close")
UNKNOWN = "UNKNOWN_NO_KNOWN_MEMBERSHIP"


def report_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_coverage_input(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("coverage input must be a JSON object")
    if payload.get("data_kind") not in KINDS:
        raise ValueError("data_kind must be synthetic or user-supplied unverified")
    if payload.get("universe_scope") not in SCOPES:
        raise ValueError("unknown universe_scope")
    for field in ("reference_source", "calendar_source"):
        text_field(payload, field)
    for field in ("snapshots", "membership_events", "facts", "prices"):
        if not isinstance(payload.get(field), list):
            raise ValueError(f"expected list {field}")
    if not payload["snapshots"]:
        raise ValueError("no reference snapshots: universe denominator unavailable")
    required_fields = payload.get("required_fact_fields", [])
    if not isinstance(required_fields, list) or any(
        not isinstance(x, str) or not x.strip() for x in required_fields
    ) or len(required_fields) != len(set(required_fields)):
        raise ValueError("required_fact_fields must be a unique list of names")
    prev = None
    snapshot_dates = set()
    for snap in payload["snapshots"]:
        signal = day(snap["signal_date"])
        cutoff = aware(snap["decision_at"])
        if signal != cutoff.astimezone(EXCHANGE_TZ).date():
            raise ValueError("signal_date must match exchange-local decision day")
        if prev is not None and cutoff <= prev:
            raise ValueError("snapshots must have strictly ascending decisions")
        prev = cutoff
        if snap["signal_date"] in snapshot_dates:
            raise ValueError("duplicate reference session")
        snapshot_dates.add(snap["signal_date"])
        names = snap.get("reference_security_ids")
        if not isinstance(names, list) or not names or any(
            not isinstance(x, str) or not x.strip() for x in names
        ) or len(names) != len(set(names)):
            raise ValueError("reference ids must be a nonempty unique list")
    seen_m, seen_f, seen_p = set(), set(), set()
    for row in payload["membership_events"]:
        source_gate(row)
        sec, rev = text_field(row, "security_id"), text_field(row, "revision_id")
        start = day(row["effective_from"])
        end = day(row["effective_to"]) if row.get("effective_to") else None
        if end is not None and end <= start:
            raise ValueError("invalid half-open membership interval")
        key = (sec, rev)
        if key in seen_m:
            raise ValueError("duplicate membership revision")
        seen_m.add(key)
    for row in payload["facts"]:
        source_gate(row)
        key = (text_field(row, "security_id"), text_field(row, "field"),
               day(row["period_end"]), text_field(row, "revision_id"))
        if key in seen_f:
            raise ValueError("duplicate fact revision")
        seen_f.add(key)
        v = row.get("value")
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                              or not math.isfinite(v)):
            raise ValueError("invalid nonfinite fact")
        if v is None and not row.get("missing_reason"):
            raise ValueError("missing value needs explicit reason")
        if v is not None and row.get("missing_reason"):
            raise ValueError("numeric fact cannot have missing_reason")
    for row in payload["prices"]:
        for field in PRICE_KEYS:
            if field not in row:
                raise ValueError(f"missing price {field}")
        source_gate(row)
        sec = text_field(row, "security_id")
        d = day(row["trade_date"]).isoformat()
        if d not in snapshot_dates:
            raise ValueError("price date outside declared reference sessions")
        price = row["close"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or (
                not math.isfinite(price) or price <= 0):
            raise ValueError("price close must be positive finite")
        key = (sec, d, text_field(row, "revision_id"))
        if key in seen_p:
            raise ValueError("duplicate security-date price revision")
        seen_p.add(key)


def audit_declared_reference(payload: dict) -> dict:
    """A coverage ratio on an explicitly supplied list is NOT full-A-share coverage."""
    validate_coverage_input(payload)
    entries = []
    needed = payload.get("required_fact_fields", [])
    for snap in payload["snapshots"]:
        state = {"decision_at": snap["decision_at"],
                 "signal_date": snap["signal_date"],
                 "membership_events": payload["membership_events"],
                 "facts": payload["facts"]}
        memberships = membership_asof(state)
        facts = facts_asof(state, memberships)
        ids = snap["reference_security_ids"]
        cutoff = aware(snap["decision_at"])
        known = {code: memberships.get(code, UNKNOWN) for code in ids}
        eligible = [code for code in ids if known[code] == "ELIGIBLE"]
        unknown = [code for code in ids if known[code] == UNKNOWN]
        ineligible = [code for code in ids if known[code] == "INELIGIBLE"]
        price_data = {}
        for sec in ids:
            candidate = [r for r in payload["prices"]
                         if r["security_id"] == sec and
                         r["trade_date"] == snap["signal_date"]]
            observed = [r for r in candidate if all(
                aware(r[k]) <= cutoff for k in
                ("source_published_at", "ingested_at", "available_at"))]
            if observed:
                selected = max(observed, key=lambda r: (
                    aware(r["available_at"]), r["revision_id"]))
                price_data[sec] = {"status": "DECLARED_KNOWN_AT_DECISION",
                                   "close": selected["close"],
                                   "revision_id": selected["revision_id"]}
            elif candidate:
                price_data[sec] = {"status": "LATE_OR_UNAVAILABLE_AT_DECISION"}
            else:
                price_data[sec] = {"status": "MISSING_PRICE_RECORD"}
        timely = [sec for sec in eligible if price_data[sec]["status"] ==
                  "DECLARED_KNOWN_AT_DECISION"]
        late = [sec for sec in eligible if price_data[sec]["status"] ==
                "LATE_OR_UNAVAILABLE_AT_DECISION"]
        missing = [sec for sec in eligible if price_data[sec]["status"] ==
                   "MISSING_PRICE_RECORD"]
        field_status = {}
        for field in needed:
            statuses = {"KNOWN": [], "DECLARED_MISSING": [],
                        "UNKNOWN_NO_KNOWN_FACT": []}
            for sec in eligible:
                status = facts.get(sec, {}).get(field, {}).get("status",
                                                               "UNKNOWN_NO_KNOWN_FACT")
                key = ("KNOWN" if status == "KNOWN" else
                       "DECLARED_MISSING" if status.startswith("MISSING_") else
                       "UNKNOWN_NO_KNOWN_FACT")
                statuses[key].append(sec)
            field_status[field] = {k: sorted(v) for k, v in statuses.items()}
        entries.append({
            "signal_date": snap["signal_date"], "decision_at": snap["decision_at"],
            "declared_reference_count": len(ids),
            "known_eligible": eligible, "known_ineligible": ineligible,
            "unknown_membership": unknown,
            "reference_membership_known_fraction": round(
                (len(eligible) + len(ineligible)) / len(ids), 6),
            "eligible_with_declared_timely_price": timely,
            "eligible_with_late_price": late,
            "eligible_without_price": missing,
            "price_by_reference_security": price_data,
            "field_coverage_on_declared_eligible": field_status,
            "full_market_denominator": None,
            "full_market_coverage_percent": None,
        })
    return {
        "source_kind": payload["data_kind"],
        "evidence_grade": "SYNTHETIC_REFERENCE_AUDIT" if payload["data_kind"] ==
            "SYNTHETIC_DEMONSTRATION" else "USER_DECLARED_REFERENCE_AUDIT",
        "reference_scope": payload["universe_scope"],
        "reference_source": payload["reference_source"],
        "calendar_source": payload["calendar_source"],
        "snapshot_count": len(entries),
        "reference_coverage": entries,
        "historical_full_universe_verified": False,
        "historical_pit_verified": False,
        "historical_pit_source_timestamp_verified": False,
        "full_market_coverage_percent": None,
        "full_market_denominator_status": "NOT_VERIFIED_NO_AUTHORITATIVE_FULL_MARKET_LIST",
        "input_sha256": report_sha(payload),
        "limitations": [
            "Declared reference list is not an audited historical A-share universe.",
            "Source dates, SHA strings and calendar sessions supplied by a user "
            "are not independently verified.",
            "Unknown membership is not zero and is not a proven inactive stock.",
            "Late/absent price records must not be silently removed from the denominator.",
            "Not a tradable return, market-wide PIT backtest or untouched OOS.",
        ],
    }


def demo_coverage_payload() -> dict:
    events = demo_payload()
    def price(sec: str, d: str, close: float, revision: str,
              published: str, ready: str) -> dict:
        return {
            "security_id": sec, "trade_date": d, "close": close,
            "revision_id": revision, "source_ref": "SYNTHETIC_NOT_MARKET_DATA",
            "declared_evidence_sha256": "0" * 64,
            "source_published_at": published, "ingested_at": ready,
            "available_at": ready,
        }
    first = "2024-03-20"
    second = "2024-04-11"
    return {
        "data_kind": "SYNTHETIC_DEMONSTRATION",
        "universe_scope": "SELECTED_SAMPLE",
        "reference_source": "SYNTHETIC_THREE_SECURITY_REFERENCE",
        "calendar_source": "SYNTHETIC_DECLARED_SESSIONS_NOT_OFFICIAL",
        "required_fact_fields": ["roe"],
        "snapshots": [
            {"signal_date": first, "decision_at": first + "T18:00:00+08:00",
             "reference_security_ids": ["A", "B", "C"]},
            {"signal_date": second, "decision_at": second + "T18:00:00+08:00",
             "reference_security_ids": ["A", "B", "C"]},
        ],
        "membership_events": events["membership_events"],
        "facts": events["facts"],
        "prices": [
            price("A", first, 100.0, "A-1", first+"T16:00:00+08:00",
                  first+"T16:10:00+08:00"),
            price("B", first, 200.0, "B-late", first+"T18:10:00+08:00",
                  first+"T18:20:00+08:00"),
            price("B", second, 201.0, "B-2", second+"T16:00:00+08:00",
                  second+"T16:10:00+08:00"),
        ],
    }


def audit_real_four_stock_snapshot(root: Path = DATA) -> dict:
    """Grounded in actual four CSVs, with no invented authoritative denominator."""
    verified = validate_snapshot(root)  # byte hash and OHLC/data sanity
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    observed = {}
    date_sets = {}
    for item in manifest["items"]:
        path = root / (item["symbol"] + ".csv")
        with path.open(encoding="utf-8", newline="") as handle:
            dates = [r["trade_date"] for r in csv.DictReader(handle)]
        date_sets[item["symbol"]] = set(dates)
        observed[item["symbol"]] = {"observed_rows": len(dates),
                                    "min": min(dates), "max": max(dates)}
    union = set.union(*date_sets.values())
    common = set.intersection(*date_sets.values())
    missing = {code: sorted(union - ds) for code, ds in date_sets.items()}
    layers = {
        "OHLC": {"observed_records": sum(x["observed_rows"] for x in observed.values()),
                 "sample_symbols": len(observed),
                 "csv_hash_integrity": "PASS",
                 "historical_publication_receipt_verified": False},
        "SECURITY_MASTER": {"historical_coverage": "NOT_PROVIDED"},
        "HISTORICAL_MEMBERSHIP": {"historical_coverage": "NOT_PROVIDED"},
        "INDUSTRY_PIT": {"historical_coverage": "NOT_PROVIDED"},
        "CORPORATE_ACTIONS": {"historical_coverage": "NOT_PROVIDED"},
        "DISCLOSURES_AND_REVISIONS": {"historical_coverage": "NOT_PROVIDED"},
        "EXCHANGE_SESSIONS": {"historical_coverage": "NOT_PROVIDED"},
        "EXECUTION_STATUS": {"historical_coverage": "NOT_PROVIDED"},
    }
    return {
        "source_kind": "REAL_RETROSPECTIVE_OHLC_SELECTED_FOUR_A_SHARES",
        "evidence_grade": "FILE_INTEGRITY_ONLY_NO_HISTORICAL_UNIVERSE_PIT",
        "source": verified["source"],
        "capture_timestamp": verified["capture_timestamp"],
        "observed_security_count": len(observed),
        "observed_security_sessions": sum(x["observed_rows"] for x in observed.values()),
        "observed_date_union_sessions": len(union),
        "common_observed_date_count": len(common),
        "missing_on_observed_union": missing,
        "sample_internal_coverage_fraction": round(
            sum(x["observed_rows"] for x in observed.values()) /
            (len(observed) * len(union)), 6),
        "source_layers": layers,
        "observed_stock_files": observed,
        "official_exchange_calendar_verified": False,
        "historical_full_universe_verified": False,
        "historical_pit_verified": False,
        "historical_stock_status_verified": False,
        "independent_oos_verified": False,
        "full_market_denominator": None,
        "full_market_coverage_percent": None,
        "full_market_denominator_status": "NOT_ESTABLISHED_FROM_PRESELECTED_NAMES",
        "manifest_sha256": verified["manifest_sha256"],
        "limitations": [
            "File coverage compares only four named stocks on their OBSERVED date union.",
            "117 common dates are observed dates, not proof of all exchange sessions.",
            "Four preselected names exclude unknown delisted and omitted stocks.",
            "2026 acquisition is not 2024 historical source availability proof.",
            "No exchange security master/industry membership or PIT revisions in this snapshot.",
            "No total-return corporate actions or actual execution/short availability.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="local candidate JSON; never uploaded")
    parser.add_argument("--real-teaching", action="store_true",
                        help="audit committed four-stock 2024 OHLC sample")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="new local JSON report; refuses overwrite")
    args = parser.parse_args()
    if args.real_teaching and args.input:
        parser.error("--real-teaching and --input are mutually exclusive")
    if args.real_teaching:
        result = audit_real_four_stock_snapshot()
    else:
        payload = json.loads(args.input.read_text("utf-8")) if args.input else demo_coverage_payload()
        result = audit_declared_reference(payload)
    data = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            f.write(data + "\n")
        print(f"Wrote evidence report to {args.output}")
    elif args.json:
        print(data)
    else:
        print("Evidence:", result["evidence_grade"])
        print("Historical full-market coverage:", result["full_market_coverage_percent"])
        print("Denominator gate:", result["full_market_denominator_status"])


if __name__ == "__main__":
    main()
