#!/usr/bin/env python3
"""Volume III microcap lesson lab. Synthetic-only; standard library."""
from __future__ import annotations
import argparse, json, math
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "teaching" / "volume3_microcap_synthetic_v1.json"
def moment(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("All teaching timestamps must include a UTC offset")
    return result
def validate(data: dict) -> None:
    if data.get("dataset_id") != "volume3-microcap-synthetic-v1" or data.get("evidence_grade") != "SYNTHETIC_ONLY":
        raise ValueError("Only the declared synthetic teaching dataset is accepted")
    dates = data.get("rebalance_dates", [])
    if len(dates) != 3 or len(set(dates)) != len(dates):
        raise ValueError("Expected three distinct artificial rebalance dates")
    rules = data["rules"]
    if int(rules["target_count"]) <= 0 or set(data["decision_at"]) != set(dates):
        raise ValueError("Invalid target count or decision-time map")
    seen = set()
    for row in data["observations"]:
        key = (row["date"], row["security_id"])
        if key in seen: raise ValueError("Duplicate security/date observation")
        seen.add(key)
        if row["date"] not in dates: raise ValueError("Observation outside teaching calendar")
        moment(data["decision_at"][row["date"]])
        moment(row["financial_available_at"])
        if row["size_rank"] <= 0 or row["listing_days"] < 0: raise ValueError("Invalid size rank or listing age")
        for field in ("quality_score", "backup_score"):
            value = row[field]
            if value is not None and not math.isfinite(float(value)): raise ValueError("Non-finite score")
        if not isinstance(row["liquidity_ok"], bool): raise ValueError("liquidity_ok must be explicit")
        if not isinstance(row["suspended"], bool) or not isinstance(row["limit_down"], bool):
            raise ValueError("Trading-state fields must be explicit booleans")
def load(path: Path = DATA) -> dict:
    data = json.loads(path.read_text(encoding="utf-8")); validate(data); return data
def run(data: dict) -> dict:
    validate(data); rules=data["rules"]; k=int(rules["target_count"]); previous={}; reports=[]
    for date in data["rebalance_dates"]:
        rows=[r for r in data["observations"] if r["date"]==date]; by_id={r["security_id"]:r for r in rows}
        decision=moment(data["decision_at"][date]); eligible=[]
        for row in rows:
            if row["size_rank"]>rules["max_size_rank"] or row["listing_days"]<rules["min_listing_days"] or not row["liquidity_ok"]: continue
            if not moment(row["financial_available_at"])<decision: continue
            eligible.append(row)
        primary_pool=[r for r in eligible if r["quality_score"] is not None]
        primary=sorted(primary_pool,key=lambda r:(-float(r["quality_score"]),r["security_id"]))[:k]
        chosen={r["security_id"]:r for r in primary}; backup=[]
        if len(chosen)<k:
            pool=[r for r in eligible if r["security_id"] not in chosen and r["backup_score"] is not None]
            backup=sorted(pool,key=lambda r:(-float(r["backup_score"]),r["security_id"]))[:k-len(chosen)]
            chosen.update({r["security_id"]:r for r in backup})
        target={sid:1.0/k for sid in chosen}; blocked=[]; locked={}
        blocked_exits=set(data["blocked_exits"].get(date,[]))
        for sid,weight in previous.items():
            row=by_id.get(sid)
            if row is None:
                locked[sid]=weight; blocked.append({"security_id":sid,"reason":"STATE_UNKNOWN"})
            elif sid in chosen and (row["suspended"] or row["limit_down"]):
                locked[sid]=weight; blocked.append({"security_id":sid,"reason":"HELD_UNCHANGED"})
            elif sid not in chosen and sid in blocked_exits:
                locked[sid]=weight; blocked.append({"security_id":sid,"reason":"EXIT_NOT_FILLED"})
        budget=max(0.0,1.0-sum(locked.values())); per_name=budget/k; constrained=dict(locked)
        for sid,row in chosen.items():
            if row["suspended"] or row["limit_down"]:
                if sid not in locked:
                    blocked.append({"security_id":sid,"reason":"SUSPENDED" if row["suspended"] else "LIMIT_DOWN"})
                continue
            constrained[sid]=per_name
        invested=sum(constrained.values())
        if invested>1.0+1e-12: raise ValueError("Illustrative holdings exceed NAV")
        cash=max(0.0,1.0-invested)
        reports.append({"date":date,"eligible":[r["security_id"] for r in eligible],
            "primary":[r["security_id"] for r in primary],"backup":[r["security_id"] for r in backup],
            "target_weights":target,"constrained_weights":constrained,"blocked_orders":blocked,
            "cash_weight":cash,"source_kind":"SYNTHETIC_ONLY"})
        previous=constrained
    return {"dataset_id":data["dataset_id"],"evidence_grade":"SYNTHETIC_ONLY",
        "market_pit_proven":False,"real_OOS_proven":False,"execution_proven":False,"reports":reports}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--json",action="store_true");a=p.parse_args();result=run(load())
    if a.json: print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    else:
        for r in result["reports"]: print(r["date"],"primary=",r["primary"],"backup=",r["backup"],"cash=",round(r["cash_weight"],4))
if __name__=="__main__": main()
