#!/usr/bin/env python3
"""Second-volume research contract and PIT audit lab.

All entities, dates, values and disclosures in sample_*() are SYNTHETIC.
This standard-library exercise validates time semantics, not market returns.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timezone
from typing import Any


REQUIRED_TEXT = (
    "study_id", "hypothesis", "failure_rule", "universe_rule", "benchmark"
)
TIME_FIELDS = (
    "feature_available_at", "signal_at", "decision_at", "entry_at",
    "exit_at", "label_end_at", "train_last_label_end_at", "valid_first_signal_at"
)


def moment(value: str) -> datetime:
    """Parse a timestamp as an aware instant; compare in UTC."""
    if not isinstance(value, str):
        raise ValueError("Timestamp must be a string with UTC offset")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid ISO timestamp: {value!r}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timezone offset is mandatory: {value!r}")
    return parsed.astimezone(timezone.utc)


def day(value: str) -> date:
    """Treat a date as a local exchange calendar date, not a UTC instant."""
    if not isinstance(value, str):
        raise ValueError("Calendar date must be ISO YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Invalid ISO date: {value!r}") from error
    if parsed.isoformat() != value:
        raise ValueError(f"Expected YYYY-MM-DD: {value!r}")
    return parsed


def validate_contract(contract: dict[str, Any]) -> dict[str, str]:
    """Fail closed on missing fields or impossible information/label windows."""
    for key in REQUIRED_TEXT:
        if not isinstance(contract.get(key), str) or not contract[key].strip():
            raise ValueError(f"Missing/blank research contract field: {key}")
    times = {}
    for key in TIME_FIELDS:
        if key not in contract:
            raise ValueError(f"Missing research contract timestamp: {key}")
        times[key] = moment(contract[key])

    if times["feature_available_at"] > times["decision_at"]:
        raise ValueError("Feature cutoff happens after decision")
    if times["signal_at"] > times["decision_at"]:
        raise ValueError("Signal anchor happens after decision")
    if not (times["decision_at"] < times["entry_at"] < times["exit_at"]):
        raise ValueError("Require decision < entry < exit")
    if times["exit_at"] > times["label_end_at"]:
        raise ValueError("Label must not finish before planned exit")
    if not (times["train_last_label_end_at"] < times["valid_first_signal_at"]):
        raise ValueError("Training label overlaps next validation signal: purge required")
    return {"study_id": contract["study_id"], "time_gate": "PASS", "fold_gate": "PASS"}


def _unique_revisions(records: list[dict], entity_fields: tuple[str, ...]) -> None:
    seen: set[tuple] = set()
    for row in records:
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in entity_fields):
            raise ValueError(f"Missing entity fields: {entity_fields}")
        known = moment(row["known_at"])
        key = tuple(row[k] for k in entity_fields) + (known,)
        if key in seen:
            raise ValueError(f"Ambiguous duplicate revision: {key}")
        seen.add(key)


def membership_asof(
    records: list[dict], cutoff: str, signal_date: str
) -> list[dict]:
    """Use the latest *known* status version per code and half-open intervals."""
    bound, at_day = moment(cutoff), day(signal_date)
    _unique_revisions(records, ("code",))
    latest: dict[str, dict] = {}
    for row in records:
        start = day(row["start_on"])
        end = day(row["end_before"]) if row.get("end_before") is not None else None
        if end is not None and end <= start:
            raise ValueError(f"Invalid membership interval for {row['code']}")
        when = moment(row["known_at"])
        if when > bound:
            continue
        old = latest.get(row["code"])
        if old is None or moment(old["known_at"]) < when:
            latest[row["code"]] = row
    included = []
    for code, row in sorted(latest.items()):
        if day(row["start_on"]) <= at_day and (
            row.get("end_before") is None or at_day < day(row["end_before"])
        ):
            included.append({
                "code": code, "start_on": row["start_on"],
                "end_before": row.get("end_before"), "known_at": row["known_at"],
                "source": row["source"]
            })
    return included


def facts_asof(
    records: list[dict], cutoff: str, signal_date: str,
    field: str, codes: list[str]
) -> dict[str, dict | None]:
    """Latest known reporting period, then latest known revision of that period."""
    bound, at_day = moment(cutoff), day(signal_date)
    _unique_revisions(records, ("code", "field", "period_end"))
    eligible = set(codes)
    selected: dict[str, dict] = {}
    for row in records:
        period, when = day(row["period_end"]), moment(row["known_at"])
        value = row.get("value")
        if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Numerical fact value required; missingness is explicit")
        if not math.isfinite(value):
            raise ValueError("Non-finite financial fact")
        if row["field"] != field or row["code"] not in eligible:
            continue
        if when > bound or period > at_day:
            continue
        old = selected.get(row["code"])
        if old is None or (period, when) > (day(old["period_end"]), moment(old["known_at"])):
            selected[row["code"]] = row
    return {
        code: (
            {
                "period_end": selected[code]["period_end"],
                "value": selected[code]["value"],
                "known_at": selected[code]["known_at"],
                "source": selected[code]["source"],
            }
            if code in selected else None
        )
        for code in sorted(eligible)
    }


def audit_snapshot(
    contract: dict, membership: list[dict], financial: list[dict], field: str
) -> dict:
    checks = validate_contract(contract)
    # Exchange-local calendar date is taken from the original signal timestamp,
    # *not* from its converted UTC date.
    signal_date = datetime.fromisoformat(contract["signal_at"]).date().isoformat()
    cutoff = contract["feature_available_at"]
    universe = membership_asof(membership, cutoff, signal_date)
    codes = [row["code"] for row in universe]
    facts = facts_asof(financial, cutoff, signal_date, field, codes)
    return {
        "source_kind": "SYNTHETIC_TUTORIAL_NOT_MARKET_EVIDENCE",
        "contract": checks,
        "feature_cutoff_at": cutoff,
        "signal_date": signal_date,
        "universe": universe,
        "facts": facts,
        "coverage": {
            "eligible": len(codes),
            "known_values": sum(row is not None for row in facts.values()),
            "missing_values": sum(row is None for row in facts.values()),
        },
        "limitations": [
            "Time and as-of semantics are tested, not source authenticity.",
            "No orders, fills, expected returns or profitability are evaluated.",
            "Real data needs timestamp provenance and historical instrument identifiers.",
        ],
    }


def sample_contract() -> dict:
    return {
        "study_id": "toy_pit_2024_03",
        "hypothesis": "For demonstration only: previously disclosed ROE is an input",
        "failure_rule": "Reject missing timestamps, overlap, unknown or late records",
        "universe_rule": "Latest known listing interval at the feature cutoff",
        "benchmark": "Not applicable: no investment return is measured",
        "feature_available_at": "2024-03-20T15:00:00+08:00",
        "signal_at": "2024-03-20T15:00:00+08:00",
        "decision_at": "2024-03-20T18:00:00+08:00",
        "entry_at": "2024-03-21T09:30:00+08:00",
        "exit_at": "2024-03-28T09:30:00+08:00",
        "label_end_at": "2024-03-28T09:30:00+08:00",
        "train_last_label_end_at": "2024-03-19T09:30:00+08:00",
        "valid_first_signal_at": "2024-03-20T15:00:00+08:00",
    }


def sample_memberships() -> list[dict]:
    return [
        {"code": "A", "start_on": "2020-01-01", "end_before": None,
         "known_at": "2020-01-01T12:00:00+08:00", "source": "toy-v1"},
        {"code": "B", "start_on": "2020-01-01", "end_before": None,
         "known_at": "2020-01-01T12:00:00+08:00", "source": "toy-v1"},
        {"code": "C", "start_on": "2020-01-01", "end_before": None,
         "known_at": "2024-03-21T09:00:00+08:00", "source": "toy-late"},
        {"code": "B", "start_on": "2020-01-01", "end_before": "2024-03-21",
         "known_at": "2024-03-21T12:00:00+08:00", "source": "toy-revision"},
    ]


def sample_financial() -> list[dict]:
    return [
        {"code": "A", "field": "roe", "period_end": "2023-12-31", "value": 0.10,
         "known_at": "2024-03-15T17:00:00+08:00", "source": "toy-initial"},
        {"code": "A", "field": "roe", "period_end": "2023-12-31", "value": 0.15,
         "known_at": "2024-04-10T17:00:00+08:00", "source": "toy-revision"},
        {"code": "B", "field": "roe", "period_end": "2023-09-30", "value": 0.08,
         "known_at": "2023-11-10T17:00:00+08:00", "source": "toy-previous-period"},
        {"code": "C", "field": "roe", "period_end": "2023-12-31", "value": 0.25,
         "known_at": "2024-03-25T17:00:00+08:00", "source": "toy-late"},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print full synthetic audit report")
    args = parser.parse_args()
    report = audit_snapshot(
        sample_contract(), sample_memberships(), sample_financial(), "roe"
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        cov = report["coverage"]
        print("Synthetic PIT audit:", report["contract"]["time_gate"])
        print("Universe:", [row["code"] for row in report["universe"]])
        print("Observed:", {k: v["value"] if v else None for k, v in report["facts"].items()})
        print(f"Coverage: {cov['known_values']}/{cov['eligible']} (synthetic only)")
        print("No real-market inference or execution result.")


if __name__ == "__main__":
    main()
