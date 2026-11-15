#!/usr/bin/env python3
"""Corporate-event PIT and event-window teaching lab. SYNTHETIC_ONLY."""
from __future__ import annotations
import argparse, json, math
from datetime import date, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/teaching/volume3_events_synthetic_v1.json"
DATASET_ID = "volume3-events-synthetic-v1"

def ts(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamps must include UTC offsets")
    return result

def validate(data):
    if data.get("dataset_id") != DATASET_ID or data.get("evidence_grade") != "SYNTHETIC_ONLY":
        raise ValueError("Only the declared synthetic classroom fixture is accepted")
    events = data.get("events", [])
    ids = [event["id"] for event in events]
    if len(ids) != len(set(ids)) or len(ids) != 7:
        raise ValueError("Expected seven unique frozen classroom events")
    for event in events:
        for key in ("published_at", "received_at", "decision_at"):
            ts(event[key])
        date.fromisoformat(event["event_date"])
        if ts(event["published_at"]) > ts(event["received_at"]):
            raise ValueError("Vendor receipt cannot precede publication")
    for mapping in data["mappings"]:
        date.fromisoformat(mapping["effective_from"])
        date.fromisoformat(mapping["effective_to"])
        ts(mapping["available_at"])
        if mapping["effective_from"] >= mapping["effective_to"]:
            raise ValueError("Mapping interval must be half-open and non-empty")
    allowed = set(data["window_offsets"] + data["placebo_offsets"])
    for collection, return_key in ((data["observations"], "security_return"),
                                   (data["control_observations"], "control_return")):
        for row in collection:
            if row["offset"] not in allowed:
                raise ValueError("Unexpected event offset")
            if not math.isfinite(row[return_key]) or not math.isfinite(row["benchmark_return"]):
                raise ValueError("Non-finite return")

def load(path=DATA):
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data)
    return data

def resolve_issuer(event, mappings):
    event_day = event["event_date"]
    cutoff = ts(event["decision_at"])
    candidates = [item for item in mappings
        if item["alias"] == event["alias"]
        and item["effective_from"] <= event_day < item["effective_to"]
        and ts(item["available_at"]) < cutoff]
    if not candidates:
        return None, "UNKNOWN_MAPPING"
    issuers = {item["issuer_id"] for item in candidates}
    if len(issuers) != 1:
        return None, "AMBIGUOUS_MAPPING"
    return next(iter(issuers)), "MAPPED"

def index_rows(rows):
    result = {}
    for row in rows:
        key = (row["event_id"], row["offset"])
        if key in result:
            raise ValueError("Duplicate event/offset return row")
        result[key] = row
    return result

def audit(data):
    validate(data)
    observations = index_rows(data["observations"])
    controls = index_rows(data["control_observations"])
    records = []
    for event in data["events"]:
        cutoff = ts(event["decision_at"])
        reasons = []
        if ts(event["published_at"]) >= cutoff:
            reasons.append("NOT_PUBLIC_BY_DECISION")
        if ts(event["received_at"]) >= cutoff:
            reasons.append("NOT_RECEIVED_BY_DECISION")
        issuer, mapping_status = resolve_issuer(event, data["mappings"])
        if issuer is None:
            reasons.append(mapping_status)
        records.append({
            "event_id": event["id"], "issuer_id": issuer,
            "mapping_status": mapping_status, "pit_eligible": not reasons,
            "exclusion_reasons": reasons, "event_day_index": event["event_day_index"],
            "control_id": event["control_id"], "window_status": "NOT_EVALUATED"
        })
    eligible = [record for record in records if record["pit_eligible"]]
    overlap_ids = set()
    for index, left in enumerate(eligible):
        for right in eligible[index + 1:]:
            if (left["issuer_id"] == right["issuer_id"] and
                    abs(left["event_day_index"] - right["event_day_index"]) <= 2):
                overlap_ids.update((left["event_id"], right["event_id"]))
    event_offsets = data["window_offsets"]
    placebo_offsets = data["placebo_offsets"]
    results = []
    for event in data["events"]:
        record = next(item for item in records if item["event_id"] == event["id"])
        if not record["pit_eligible"]:
            continue
        if event["id"] in overlap_ids:
            record["window_status"] = "OVERLAPPING_CLUSTER"
            continue
        needed = event_offsets + placebo_offsets
        event_rows = [observations.get((event["id"], offset)) for offset in needed]
        control_rows = [controls.get((event["id"], offset)) for offset in needed]
        if any(row is None for row in event_rows + control_rows):
            record["window_status"] = "INCOMPLETE_WINDOW"
            continue
        by_offset = {row["offset"]: row for row in event_rows}
        control_by_offset = {row["offset"]: row for row in control_rows}
        event_car = sum(by_offset[o]["security_return"] - by_offset[o]["benchmark_return"] for o in event_offsets)
        control_car = sum(control_by_offset[o]["control_return"] - control_by_offset[o]["benchmark_return"] for o in event_offsets)
        placebo_car = sum(by_offset[o]["security_return"] - by_offset[o]["benchmark_return"] for o in placebo_offsets)
        placebo_control = sum(control_by_offset[o]["control_return"] - control_by_offset[o]["benchmark_return"] for o in placebo_offsets)
        results.append({
            "event_id": event["id"], "issuer_id": record["issuer_id"],
            "event_car": round(event_car, 8),
            "matched_control_car": round(control_car, 8),
            "control_adjusted_car": round(event_car - control_car, 8),
            "placebo_car": round(placebo_car, 8),
            "placebo_control_adjusted_car": round(placebo_car - placebo_control, 8)
        })
        record["window_status"] = "COMPLETE"
    return {
        "dataset_id": DATASET_ID, "evidence_grade": "SYNTHETIC_ONLY",
        "events": records, "overlap_event_ids": sorted(overlap_ids),
        "isolated_complete_event_count": len(results), "event_results": results,
        "market_pit_proven": False, "causal_effect_proven": False,
        "real_event_alpha_proven": False, "execution_proven": False,
        "interpretation": "Synthetic protocol demonstration only; no real issuer identity, disclosure PIT, causal effect, market alpha or execution is established."
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit(load())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for event in result["events"]:
            print(event["event_id"], event["mapping_status"],
                  event["exclusion_reasons"], event["window_status"])
        print("isolated complete synthetic events:", result["isolated_complete_event_count"])

if __name__ == "__main__":
    main()
