#!/usr/bin/env python3
"""Fail-closed as-of intake contract for candidate PIT evidence (standard library).

SYNTHETIC_DEMONSTRATION is the default; optional --input accepts LOCAL user
files without uploading them. Neither a declared timestamp nor an SHA digest
proves an exchange/supplier actually published that fact at that instant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

KINDS = {"SYNTHETIC_DEMONSTRATION", "USER_SUPPLIED_UNVERIFIED"}
SCOPES = {"SELECTED_SAMPLE", "HISTORICAL_UNIVERSE_CANDIDATE"}
STAMP_FIELDS = ("source_published_at", "ingested_at", "available_at")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
MISSING_REASONS = {"NOT_ANNOUNCED", "NOT_COLLECTED", "NOT_APPLICABLE", "SOURCE_CONFLICT"}
LABEL_FIELDS = ("signal_at", "feature_available_at", "decision_at", "entry_at",
                "exit_at", "label_available_at")


def aware(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be timezone-aware ISO text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("naive timestamps are forbidden")
    return parsed.astimezone(timezone.utc)


def day(value: str) -> date:
    if not isinstance(value, str):
        raise ValueError("calendar day must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid calendar day") from exc
    if parsed.isoformat() != value:
        raise ValueError("calendar day must be YYYY-MM-DD")
    return parsed


def text_field(row: dict, key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing nonempty {key}")
    return value


def source_gate(row: dict) -> None:
    """Require declared version, provenance and monotonically available times."""
    for key in ("source_ref", "revision_id"):
        text_field(row, key)
    digest = text_field(row, "declared_evidence_sha256")
    if not SHA_RE.fullmatch(digest):
        raise ValueError("declared evidence SHA256 must be 64 lowercase hex digits")
    published, ingested, available = (aware(row[k]) for k in STAMP_FIELDS)
    if not (published <= ingested <= available):
        raise ValueError("publication, ingestion, availability time order violated")


def validate_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("JSON input must be an object")
    if payload.get("data_kind") not in KINDS:
        raise ValueError("unknown data_kind: cannot claim verified PIT")
    if payload.get("universe_scope") not in SCOPES:
        raise ValueError("universe scope is required")
    cutoff, first_valid = aware(payload["decision_at"]), aware(payload["validation_first_signal_at"])
    if not cutoff < first_valid:
        raise ValueError("decision must precede first validation signal")
    signal_day = day(payload["signal_date"])
    if signal_day > cutoff.date() or signal_day > first_valid.date():
        raise ValueError("signal calendar day cannot lie after cutoff")
    for section in ("membership_events", "facts", "labels"):
        if not isinstance(payload.get(section), list):
            raise ValueError(f"missing list: {section}")
    seen_membership, seen_facts = set(), set()
    for row in payload["membership_events"]:
        sec = text_field(row, "security_id")
        source_gate(row)
        start = day(row["effective_from"])
        end = day(row["effective_to"]) if row.get("effective_to") is not None else None
        if end is not None and end <= start:
            raise ValueError("invalid half-open membership interval")
        key = sec, text_field(row, "revision_id")
        if key in seen_membership:
            raise ValueError("ambiguous duplicate membership revision")
        seen_membership.add(key)
    for row in payload["facts"]:
        sec, field = text_field(row, "security_id"), text_field(row, "field")
        period = day(row["period_end"])
        source_gate(row)
        key = sec, field, period.isoformat(), row["revision_id"]
        if key in seen_facts:
            raise ValueError("duplicate fact revision")
        seen_facts.add(key)
        value = row.get("value")
        if value is None:
            if row.get("missing_reason") not in MISSING_REASONS:
                raise ValueError("missing fact value needs explicit missing_reason")
        elif isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError("fact value must be finite numeric or explicit missing")
        if "missing_reason" in row and value is not None:
            raise ValueError("numeric fact may not carry missing_reason")
    for row in payload["labels"]:
        text_field(row, "security_id")
        stamps = {k: aware(row[k]) for k in LABEL_FIELDS}
        if not (stamps["signal_at"] <= stamps["decision_at"] <
                stamps["entry_at"] <= stamps["exit_at"] <= stamps["label_available_at"]):
            raise ValueError("impossible signal/entry/exit/label timeline")
        if stamps["feature_available_at"] > stamps["decision_at"]:
            raise ValueError("future feature crossed decision boundary")
        if stamps["decision_at"] >= first_valid:
            raise ValueError("training label decision cannot be after validation opens")


def _effective(row: dict, signal: date) -> bool:
    return day(row["effective_from"]) <= signal and (
        row.get("effective_to") is None or signal < day(row["effective_to"]))


def _known(row: dict, cutoff: datetime) -> bool:
    return all(aware(row[k]) <= cutoff for k in STAMP_FIELDS)


def membership_asof(payload: dict) -> dict[str, str]:
    """Fail closed: unknown != inactive, and later-effective news cannot appear."""
    cutoff, signal = aware(payload["decision_at"]), day(payload["signal_date"])
    codes = {r["security_id"] for r in payload["membership_events"] + payload["facts"]}
    result: dict[str, str] = {}
    for code in sorted(codes):
        known = [r for r in payload["membership_events"]
                 if r["security_id"] == code and _known(r, cutoff)
                 and day(r["effective_from"]) <= signal]
        if not known:
            result[code] = "UNKNOWN_NO_KNOWN_MEMBERSHIP"
        else:
            # Newer known evidence overrides earlier versions; exclude future events.
            latest = max(known, key=lambda r: (aware(r["available_at"]),
                                               aware(r["source_published_at"]), r["revision_id"]))
            result[code] = "ELIGIBLE" if _effective(latest, signal) else "INELIGIBLE"
    return result


def facts_asof(payload: dict, memberships: dict[str, str]) -> dict[str, dict]:
    """Latest known reporting period, then latest version within that period."""
    cutoff, signal = aware(payload["decision_at"]), day(payload["signal_date"])
    fields = sorted({r["field"] for r in payload["facts"]})
    result: dict[str, dict] = {}
    for code, status in memberships.items():
        result[code] = {}
        for field in fields:
            if status != "ELIGIBLE":
                result[code][field] = {"status": "NOT_ELIGIBLE" if status == "INELIGIBLE"
                                       else "MEMBERSHIP_UNKNOWN"}
                continue
            candidates = [r for r in payload["facts"] if r["security_id"] == code
                          and r["field"] == field and day(r["period_end"]) <= signal
                          and _known(r, cutoff)]
            if not candidates:
                result[code][field] = {"status": "UNKNOWN_NO_KNOWN_FACT"}
                continue
            chosen = max(candidates, key=lambda r: (day(r["period_end"]),
                           aware(r["available_at"]), r["revision_id"]))
            result[code][field] = {
                "status": "MISSING_" + chosen["missing_reason"] if chosen["value"] is None else "KNOWN",
                "value": chosen.get("value"), "period_end": chosen["period_end"],
                "revision_id": chosen["revision_id"], "source_ref": chosen["source_ref"]
            }
    return result


def train_label_gate(payload: dict) -> list[dict]:
    first = aware(payload["validation_first_signal_at"])
    results = []
    for row in payload["labels"]:
        label_ready = aware(row["label_available_at"])
        signal = aware(row["signal_at"])
        results.append({
            "security_id": row["security_id"], "signal_at": row["signal_at"],
            "label_available_at": row["label_available_at"],
            "training_status": "ELIGIBLE_PRIOR_LABEL" if label_ready < first
                else "PURGED_LABEL_NOT_READY",
            "chronology_is_prior": signal < first,
        })
    return results


def demo_payload() -> dict:
    """Synthetic examples only; fake provenance hashes are intentionally not trustable."""
    base = {
        "source_ref": "SYNTHETIC_FAKE_EVENT_NOT_A_REAL_SOURCE",
        "declared_evidence_sha256": "0" * 64,
    }
    def row(revision: str, published: str, ingested: str, available: str, **fields: Any) -> dict:
        return {**base, "revision_id": revision, "source_published_at": published,
                "ingested_at": ingested, "available_at": available, **fields}
    old = ("2024-01-03T16:00:00+08:00", "2024-01-03T16:10:00+08:00",
           "2024-01-03T16:20:00+08:00")
    late = ("2024-04-10T16:00:00+08:00", "2024-04-10T16:10:00+08:00",
            "2024-04-10T16:20:00+08:00")
    return {
        "data_kind": "SYNTHETIC_DEMONSTRATION", "universe_scope": "SELECTED_SAMPLE",
        "signal_date": "2024-03-20", "decision_at": "2024-03-20T18:00:00+08:00",
        "validation_first_signal_at": "2024-04-03T09:30:00+08:00",
        "membership_events": [
            row("A-original", *old, security_id="A", effective_from="2024-01-01", effective_to=None),
            row("A-correction", *late, security_id="A", effective_from="2024-01-01", effective_to="2024-03-01"),
            row("B-later", "2024-03-25T16:00:00+08:00",
                "2024-03-25T16:15:00+08:00", "2024-03-25T16:30:00+08:00",
                security_id="B", effective_from="2024-03-01", effective_to=None),
            row("C-inactive", *old, security_id="C", effective_from="2024-01-01", effective_to="2024-03-15"),
        ],
        "facts": [
            row("A-roe-1", "2024-03-15T16:00:00+08:00", "2024-03-15T16:10:00+08:00",
                "2024-03-15T16:20:00+08:00", security_id="A", field="roe",
                period_end="2023-12-31", value=0.10),
            row("A-roe-2", *late, security_id="A", field="roe",
                period_end="2023-12-31", value=0.15),
            row("C-roe", *old, security_id="C", field="roe",
                period_end="2023-09-30", value=None, missing_reason="NOT_COLLECTED"),
        ],
        "labels": [
            {"security_id": "A", "signal_at": "2024-03-01T15:00:00+08:00",
             "feature_available_at": "2024-03-01T15:01:00+08:00",
             "decision_at": "2024-03-01T18:00:00+08:00",
             "entry_at": "2024-03-04T09:30:00+08:00",
             "exit_at": "2024-03-20T15:00:00+08:00",
             "label_available_at": "2024-03-20T15:20:00+08:00"},
            {"security_id": "A", "signal_at": "2024-03-19T15:00:00+08:00",
             "feature_available_at": "2024-03-19T15:01:00+08:00",
             "decision_at": "2024-03-19T18:00:00+08:00",
             "entry_at": "2024-03-20T09:30:00+08:00",
             "exit_at": "2024-04-03T15:00:00+08:00",
             "label_available_at": "2024-04-03T15:15:00+08:00"}
        ]
    }


def evaluate(payload: dict) -> dict:
    validate_payload(payload)
    memberships = membership_asof(payload)
    labels = train_label_gate(payload)
    return {
        "evidence_grade": "SYNTHETIC_ONLY" if payload["data_kind"] ==
            "SYNTHETIC_DEMONSTRATION" else "USER_DECLARED_TIMES_UNVERIFIED",
        "historical_pit_proven": False,
        "historical_full_universe_proven": False,
        "source_evidence_bytes_verified": False,
        "source_timestamps_independently_verified": False,
        "is_independent_oos": False,
        "universe_scope": payload["universe_scope"],
        "decision_at": payload["decision_at"],
        "membership_asof": memberships,
        "facts_asof": facts_asof(payload, memberships),
        "label_gate": labels,
        "train_labels_eligible": sum(r["training_status"] == "ELIGIBLE_PRIOR_LABEL" for r in labels),
        "train_labels_purged": sum(r["training_status"] == "PURGED_LABEL_NOT_READY" for r in labels),
        "input_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True,
            ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "limitations": [
            "Declared SHA and timestamp syntax do not verify provider publication/ingestion truth.",
            "Unknown membership is not treated as not listed or as zero return.",
            "Only an as-of candidate: no complete historical stock universe attested.",
            "No true calendar, corporate-action ledger, execution, price fills or independent OOS.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        help="optional LOCAL JSON events; no account data is uploaded")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = (json.loads(args.input.read_text(encoding="utf-8"))
               if args.input else demo_payload())
    report = evaluate(payload)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print("PIT intake time checks:", report["evidence_grade"])
        print("Membership:", report["membership_asof"])
        print("Train labels kept/purged:", report["train_labels_eligible"],
              report["train_labels_purged"])
        print("Historical PIT and OOS are NOT verified by these declared fields.")


if __name__ == "__main__":
    main()
