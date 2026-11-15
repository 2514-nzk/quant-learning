#!/usr/bin/env python3
"""PIT theme-network and same-industry baseline lab. SYNTHETIC_ONLY."""
from __future__ import annotations
import argparse
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/teaching/volume3_theme_network_synthetic_v1.json"
DATASET_ID = "volume3-theme-network-synthetic-v1"

def parse_ts(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamps must include UTC offsets")
    return result

def validate(data):
    if data.get("dataset_id") != DATASET_ID or data.get("evidence_grade") != "SYNTHETIC_ONLY":
        raise ValueError("Only the declared synthetic classroom fixture is accepted")
    securities = data.get("securities", [])
    ids = [x["security_id"] for x in securities]
    if len(ids) != data.get("expected_securities") or len(ids) != len(set(ids)):
        raise ValueError("Unexpected or duplicate synthetic security universe")
    periods = data.get("periods", [])
    if len(periods) != data.get("expected_periods") or len(periods) < 2:
        raise ValueError("Unexpected synthetic period count")
    known_ids = set(ids)
    for period in periods:
        for key in ("signal_at", "snapshot_complete_at", "decision_at",
                    "entry_at", "exit_at", "label_available_at"):
            parse_ts(period[key])
        if not (parse_ts(period["signal_at"]) <= parse_ts(period["snapshot_complete_at"])
                < parse_ts(period["decision_at"]) < parse_ts(period["entry_at"])
                < parse_ts(period["exit_at"]) < parse_ts(period["label_available_at"])):
            raise ValueError("Signal, snapshot, decision, entry, exit and label times are out of order")
        date.fromisoformat(period["signal_at"][:10])
        if len(period["returns"]) != len(known_ids):
            raise ValueError("Every period must contain one return label per security")
        return_ids = [x["security_id"] for x in period["returns"]]
        if set(return_ids) != known_ids or len(return_ids) != len(set(return_ids)):
            raise ValueError("Missing or duplicate future-return label")
        if any(not math.isfinite(float(x["forward_return"])) for x in period["returns"]):
            raise ValueError("Non-finite synthetic return")
    for collection in ("industry_memberships", "theme_memberships"):
        record_ids = [x["record_id"] for x in data[collection]]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("Duplicate relationship record_id")
        for row in data[collection]:
            if row["security_id"] not in known_ids:
                raise ValueError("Relationship points to an unknown security")
            date.fromisoformat(row["effective_from"])
            date.fromisoformat(row["effective_to"])
            if row["effective_from"] >= row["effective_to"]:
                raise ValueError("Relationship interval must be non-empty and half-open")
            published, available = parse_ts(row["published_at"]), parse_ts(row["available_at"])
            if published > available:
                raise ValueError("A record cannot be received before publication")
    for row in data["theme_memberships"]:
        if not row.get("theme_id") or not row.get("source_version"):
            raise ValueError("Theme identity and source version are required")

def load_fixture(path=DATA):
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data)
    return data

def snapshot_for_period(period, data):
    """Rebuild only edges and industry mappings known before this decision."""
    validate(data)
    decision = parse_ts(period["decision_at"])
    signal_day = period["signal_at"][:10]
    securities = [x["security_id"] for x in data["securities"]]
    industry_map = {}
    for security_id in securities:
        candidates = [row for row in data["industry_memberships"]
            if row["security_id"] == security_id
            and row["effective_from"] <= signal_day < row["effective_to"]
            and parse_ts(row["published_at"]) < decision
            and parse_ts(row["available_at"]) < decision]
        if len(candidates) == 1:
            industry_map[security_id] = candidates[0]["industry_id"]
    themes_by_security = {security_id: set() for security_id in securities}
    active_edges = set()
    for row in data["theme_memberships"]:
        if (row["effective_from"] <= signal_day < row["effective_to"]
                and parse_ts(row["published_at"]) < decision
                and parse_ts(row["available_at"]) < decision):
            edge = (row["security_id"], row["theme_id"])
            if edge in active_edges:
                raise ValueError("Duplicate active security-theme edge")
            active_edges.add(edge)
            themes_by_security[row["security_id"]].add(row["theme_id"])
    breadth = Counter(theme for _, theme in active_edges)
    return {
        "period_id": period["period_id"],
        "industry_by_security": industry_map,
        "themes_by_security": themes_by_security,
        "theme_breadth": dict(breadth),
        "edges": active_edges,
        "snapshot_complete": parse_ts(period["snapshot_complete_at"]) < decision,
    }

def jaccard(left, right):
    union = set(left) | set(right)
    return len(set(left) & set(right)) / len(union) if union else 0.0

def weighted_jaccard(left, right, breadth, universe_size):
    left, right = set(left), set(right)
    union = left | right
    if not union:
        return 0.0
    weights = {theme: 1.0 + math.log((universe_size + 1) / (breadth.get(theme, 0) + 1))
               for theme in union}
    denominator = sum(weights.values())
    return sum(weights[t] for t in left & right) / denominator if denominator else 0.0

def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction

def block_bootstrap(period_values, repetitions=2000, seed=20261115):
    """Resample dates, not overlapping stock-pair rows."""
    if len(period_values) < 2:
        return None
    rng = random.Random(seed)
    samples = []
    for _ in range(repetitions):
        draw = [period_values[rng.randrange(len(period_values))]
                for _ in range(len(period_values))]
        samples.append(sum(draw) / len(draw))
    return [round(percentile(samples, 0.025), 8),
            round(percentile(samples, 0.975), 8)]

def evaluate(data):
    validate(data)
    securities = [x["security_id"] for x in data["securities"]]
    period_rows, anchor_rows, network_rows = [], [], []
    for period in data["periods"]:
        snap = snapshot_for_period(period, data)
        if not snap["snapshot_complete"]:
            raise ValueError("Theme snapshot is not complete before decision")
        returns = {x["security_id"]: float(x["forward_return"]) for x in period["returns"]}
        breadth = snap["theme_breadth"]
        theme_sets = snap["themes_by_security"]
        for anchor in securities:
            industry = snap["industry_by_security"].get(anchor)
            if industry is None:
                continue
            peers = [peer for peer in securities
                     if peer != anchor and snap["industry_by_security"].get(peer) == industry]
            anchor_themes = theme_sets[anchor]
            shared = [peer for peer in peers
                      if anchor_themes & theme_sets[peer]]
            nonshared = [peer for peer in peers
                         if not (anchor_themes & theme_sets[peer])]
            if not shared or not nonshared:
                continue
            shared_mean = sum(returns[x] for x in shared) / len(shared)
            nonshared_mean = sum(returns[x] for x in nonshared) / len(nonshared)
            industry_mean = sum(returns[x] for x in peers) / len(peers)
            similarities = [jaccard(anchor_themes, theme_sets[x]) for x in shared]
            anchor_rows.append({
                "period_id": period["period_id"], "anchor": anchor,
                "industry_id": industry, "shared_peer_ids": shared,
                "nonshared_peer_ids": nonshared,
                "shared_mean_return": round(shared_mean, 8),
                "nonshared_mean_return": round(nonshared_mean, 8),
                "industry_peer_mean_return": round(industry_mean, 8),
                "shared_minus_nonshared": round(shared_mean - nonshared_mean, 8),
                "shared_minus_industry": round(shared_mean - industry_mean, 8),
                "mean_shared_jaccard": round(sum(similarities) / len(similarities), 8)
            })
        selected = [x for x in anchor_rows if x["period_id"] == period["period_id"]]
        if not selected:
            raise ValueError("No anchor has both shared and non-shared same-industry peers")
        period_rows.append({
            "period_id": period["period_id"],
            "anchor_count": len(selected),
            "mean_shared_minus_nonshared": round(
                sum(x["shared_minus_nonshared"] for x in selected) / len(selected), 8),
            "mean_shared_minus_industry": round(
                sum(x["shared_minus_industry"] for x in selected) / len(selected), 8),
            "mean_shared_jaccard": round(
                sum(x["mean_shared_jaccard"] for x in selected) / len(selected), 8)
        })
        degrees = {security: len(theme_sets[security]) for security in securities}
        network_rows.append({
            "period_id": period["period_id"],
            "edge_count": len(snap["edges"]),
            "theme_count": len(breadth),
            "theme_breadth": dict(sorted(breadth.items())),
            "stock_theme_degree": degrees,
            "mean_stock_theme_degree": round(sum(degrees.values()) / len(degrees), 6),
            "late_edge_visible": ("S04", "T03") in snap["edges"],
            "snapshot_complete_before_decision": snap["snapshot_complete"]
        })
    period_values = [x["mean_shared_minus_nonshared"] for x in period_rows]
    by_industry = defaultdict(list)
    for row in anchor_rows:
        by_industry[row["industry_id"]].append(row["shared_minus_nonshared"])
    leave_one_industry_out = {}
    for industry in sorted(by_industry):
        remaining = [x["shared_minus_nonshared"] for x in anchor_rows
                     if x["industry_id"] != industry]
        leave_one_industry_out[industry] = round(sum(remaining) / len(remaining), 8)
    return {
        "dataset_id": DATASET_ID,
        "evidence_grade": "SYNTHETIC_ONLY",
        "periods": period_rows,
        "network_snapshots": network_rows,
        "anchor_observations": anchor_rows,
        "overall": {
            "mean_period_shared_minus_nonshared": round(
                sum(period_values) / len(period_values), 8),
            "period_block_bootstrap_95_descriptive": block_bootstrap(period_values),
            "positive_period_fraction": round(
                sum(value > 0 for value in period_values) / len(period_values), 6),
            "independent_time_blocks": len(period_rows),
            "anchor_period_observations": len(anchor_rows),
            "warning": "The bootstrap is a classroom date-block illustration, not valid inference from six synthetic periods."
        },
        "leave_one_industry_out": leave_one_industry_out,
        "market_pit_proven": False,
        "incremental_predictive_value_proven": False,
        "causal_effect_proven": False,
        "execution_proven": False,
        "interpretation": "Synthetic protocol demonstration only. Theme links and returns are artificial; no real A-share PIT, incremental alpha, causal effect or executable strategy is established."
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = evaluate(load_fixture())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for row in result["periods"]:
            print(row)
        print("overall:", result["overall"])
        print("SYNTHETIC_ONLY; no market alpha, causal effect or execution proven")

if __name__ == "__main__":
    main()
