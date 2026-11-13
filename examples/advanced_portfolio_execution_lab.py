#!/usr/bin/env python3
"""Volume 2 chapters 12–14: SYNTHETIC constrained portfolio and order ledger.

Standard-library-only teaching implementation. All prices, signals, sector labels,
liquidity, suspensions and returns are GENERATED and do not represent A shares.
The exchange-like restrictions are deliberately simplified and date-agnostic.
NO actual fills, performance evidence, capacity analysis, or trading advice.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

CONFIG = {
    "study_id": "toy_portfolio_execution_v1",
    "source_kind": "SYNTHETIC_ONLY_NOT_REAL_A_SHARE_PERFORMANCE",
    "initial_cash": 100000.0,
    "lot_size": 100,
    "grid_step": 0.1,
    "max_stock_weight": 0.4,
    "max_sector_weight": 0.6,
    "max_gross_weight": 1.0,
    "max_weight_l1_change": 1.6,
    "risk_aversion": 8.0,
    "trade_penalty": 0.001,
    "shrinkage_to_diagonal": 0.3,
    "risk_lookback_days": 5,
    "slippage": 0.001,
    "impact_coefficient": 0.02,
    "max_volume_participation": 0.08,
    "commission_rate": 0.0003,
    "minimum_commission": 0.5,
    "sell_tax_rate": 0.0005,
}
EXPECTED_CODES = tuple(f"S{k:02d}" for k in range(1, 7))


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()


def moment(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("aware timestamp string required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid ISO timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed.astimezone(timezone.utc)


def synthetic_market(days: int = 14) -> list[list[dict]]:
    if days < 8:
        raise ValueError("need >= 8 synthetic market days")
    tz = timezone(timedelta(hours=8))
    first = date(2024, 7, 1)
    calendar = []
    cursor = first
    while len(calendar) < days:
        if cursor.weekday() < 5:
            calendar.append(cursor)
        cursor += timedelta(days=1)
    result = []
    for t, trading_day in enumerate(calendar):
        rows = []
        for j, code in enumerate(EXPECTED_CODES):
            price = (12.0 + 3.1*j) * (1 + 0.002*t +
                    0.015*math.sin((j+1)*(t+1)*.31))
            close = price * (1 + 0.008*math.sin((j+3)*(t+1)*.48))
            state = "normal"
            if (t, code) in ((3, "S01"), (10, "S04")):
                state = "buy_block"
            elif (t, code) == (6, "S02"):
                state = "sell_block"
            elif (t, code) == (9, "S03"):
                state = "suspended"
            rows.append({
                "date": trading_day.isoformat(), "code": code,
                "sector": f"I{j % 3 + 1}",
                "open": round(price, 4), "close": round(close, 4),
                "volume_shares": 100000 + 12000*j + 1800*t,
                "score": 0.7*math.cos((j+2)*(t+1)*.29)
                         + .17*math.sin((j+1)*.7) - .22*(j % 3 == 2),
                "state": state,
                "score_known_at": datetime.combine(
                    trading_day, datetime.min.time(), tzinfo=tz
                ).replace(hour=15, minute=5).isoformat(),
                "decision_at": datetime.combine(
                    trading_day, datetime.min.time(), tzinfo=tz
                ).replace(hour=18).isoformat(),
                "open_at": datetime.combine(
                    trading_day, datetime.min.time(), tzinfo=tz
                ).replace(hour=9, minute=30).isoformat(),
            })
        result.append(rows)
    return result


def validate_market(market: list[list[dict]]) -> None:
    if len(market) < 2:
        raise ValueError("at least two market days required")
    last = None
    sectors = {}
    for rows in market:
        if not rows or tuple(sorted(r["code"] for r in rows)) != EXPECTED_CODES:
            raise ValueError("missing/duplicate/inconsistent universe")
        day = rows[0]["date"]
        if any(row["date"] != day for row in rows):
            raise ValueError("mixed trading dates")
        today = date.fromisoformat(day)
        if last is not None and today <= last:
            raise ValueError("market days must be strictly increasing")
        last = today
        for row in rows:
            if row["code"] in sectors and row["sector"] != sectors[row["code"]]:
                raise ValueError("changing sector needs PIT membership table")
            sectors[row["code"]] = row["sector"]
            for key in ("open", "close", "volume_shares", "score"):
                value = row[key]
                if (isinstance(value, bool) or not isinstance(value, (float, int))
                        or not math.isfinite(value)):
                    raise ValueError(f"nonfinite {key}")
            if min(row["open"], row["close"]) <= 0 or row["volume_shares"] <= 0:
                raise ValueError("invalid price or volume")
            if row["state"] not in ("normal", "buy_block", "sell_block", "suspended"):
                raise ValueError("unrecognized synthetic trade restriction")
            info = moment(row["score_known_at"])
            decision = moment(row["decision_at"])
            open_time = moment(row["open_at"])
            if not (open_time < info <= decision):
                raise ValueError("signal not available at decision")


def covariance_at_decision(history: list[list[dict]], config: dict) -> tuple[list[list[float]], dict]:
    """Trailing close-to-close covariance with diagonal shrinkage, no future."""
    n = len(EXPECTED_CODES)
    log_returns = []
    for before, after in zip(history[:-1], history[1:]):
        pb = {r["code"]: r["close"] for r in before}
        pa = {r["code"]: r["close"] for r in after}
        log_returns.append([math.log(pa[code]/pb[code]) for code in EXPECTED_CODES])
    samples = log_returns[-int(config["risk_lookback_days"]):]
    if len(samples) < 2:
        return [[0.0004 if i == j else 0.0 for j in range(n)]
                for i in range(n)], {
                    "sample_count": len(samples), "method": "declared_diagonal_fallback",
                    "latest_used_date": history[-1][0]["date"]
                }
    mu = [mean(x[j] for x in samples) for j in range(n)]
    raw = [[sum((v[i]-mu[i])*(v[j]-mu[j]) for v in samples) /
            (len(samples)-1) for j in range(n)] for i in range(n)]
    lam = config["shrinkage_to_diagonal"]
    cov = [[raw[i][j] if i == j else (1-lam)*raw[i][j]
            for j in range(n)] for i in range(n)]
    return cov, {"sample_count": len(samples),
                 "method": "trailing_sample_covariance_diagonal_shrinkage",
                 "latest_used_date": history[-1][0]["date"]}


def optimize_weights(rows: list[dict], history: list[list[dict]],
                     current: dict[str, float], config: dict) -> dict:
    """Exact maximizer on a *coarse discrete grid*, NOT continuous optimum."""
    if rows != history[-1]:
        raise ValueError("historical risk data may not extend beyond decision")
    codes = [r["code"] for r in rows]
    if tuple(codes) != EXPECTED_CODES:
        raise ValueError("risk/score alignment mismatch")
    cov, provenance = covariance_at_decision(history, config)
    step = config["grid_step"]
    max_slot = int(config["max_stock_weight"]/step + 1e-9)
    max_total = int(config["max_gross_weight"]/step + 1e-9)
    sector_limits = config["max_sector_weight"]
    expected = [0.015*r["score"] for r in rows]  # pedagogical score mapping
    old = [current.get(code, 0.0) for code in codes]
    best = None
    best_slots = None
    considered = 0
    for slots in itertools.product(range(max_slot+1), repeat=len(codes)):
        if sum(slots) > max_total:
            continue
        sector = defaultdict(float)
        for count, row in zip(slots, rows):
            sector[row["sector"]] += count*step
        if any(v > sector_limits + 1e-10 for v in sector.values()):
            continue
        weights = [count*step for count in slots]
        changed = sum(abs(a-b) for a, b in zip(weights, old))
        if changed > config["max_weight_l1_change"] + 1e-10:
            continue
        considered += 1
        raw_score = sum(w*m for w, m in zip(weights, expected))
        variance = sum(weights[i]*weights[j]*cov[i][j]
                       for i in range(len(codes)) for j in range(len(codes)))
        objective = (raw_score - config["risk_aversion"]*variance
                     - config["trade_penalty"]*changed)
        if best is None or objective > best + 1e-15:
            best, best_slots = objective, slots
    if best_slots is None:
        raise ValueError("no feasible grid portfolio under declared limits")
    result = {code: round(k*step, 10) for code, k in zip(codes, best_slots)}
    return {"target": result, "objective": best, "candidates_checked": considered,
            "risk_data": provenance, "target_cash_weight": 1-sum(result.values()),
            "weight_l1_change": sum(abs(result[c]-current.get(c, 0)) for c in codes)}


def holdings_qty(lots: dict[str, list[dict]], code: str) -> int:
    return sum(lot["qty"] for lot in lots.get(code, []))


def settled_qty(lots: dict[str, list[dict]], code: str, trading_day: str) -> int:
    return sum(lot["qty"] for lot in lots.get(code, [])
               if lot["acquired_on"] < trading_day)


def commission(notional: float, config: dict) -> float:
    return max(config["minimum_commission"], notional*config["commission_rate"])


def _fill_price(side: str, quote: float, fill_qty: int,
                volume: int, config: dict) -> float:
    adverse = config["slippage"] + config["impact_coefficient"]*fill_qty/volume
    return quote * (1+adverse if side == "BUY" else 1-adverse)


def apply_order(side: str, code: str, requested: int, row: dict,
                cash: float, lots: dict[str, list[dict]], config: dict) -> tuple[float, dict]:
    """Execute one synthetic opening order; log partial/rejected fills."""
    if side not in ("BUY", "SELL") or not isinstance(requested, int) or requested < 1:
        raise ValueError("order requires side and positive integer shares")
    if row["code"] != code:
        raise ValueError("order code/quote mismatch")
    if side == "BUY" and requested % config["lot_size"]:
        raise ValueError("buy request not a full lot")
    reason = "OK"
    eligible = requested
    if row["state"] == "suspended":
        reason, eligible = "SUSPENDED", 0
    elif side == "BUY" and row["state"] == "buy_block":
        reason, eligible = "BUY_LOCKED", 0
    elif side == "SELL" and row["state"] == "sell_block":
        reason, eligible = "SELL_LOCKED", 0
    if side == "SELL" and eligible:
        settle = settled_qty(lots, code, row["date"])
        if settle == 0:
            reason, eligible = "T_PLUS_1", 0
        elif settle < eligible:
            reason, eligible = "T_PLUS_1_PARTIAL", settle
    cap = int(row["volume_shares"] * config["max_volume_participation"])
    if side == "BUY":
        cap -= cap % config["lot_size"]
    if eligible > cap:
        eligible = cap
        reason = "VOLUME_CAP" if eligible else "VOLUME_CAP_ZERO"
    if side == "BUY":
        eligible -= eligible % config["lot_size"]
        # Buy affordability includes both modeled adverse execution and fees.
        while eligible > 0:
            price = _fill_price(side, row["open"], eligible,
                                row["volume_shares"], config)
            notional = price*eligible
            if notional+commission(notional, config) <= cash+1e-9:
                break
            eligible -= config["lot_size"]
            reason = "CASH_LIMIT"
    qty = max(eligible, 0)
    execution = (_fill_price(side, row["open"], qty, row["volume_shares"], config)
                 if qty else None)
    notional = execution*qty if qty else 0.0
    fee = commission(notional, config) if qty else 0.0
    tax = notional*config["sell_tax_rate"] if side == "SELL" else 0.0
    if qty:
        if side == "BUY":
            cash -= notional+fee
            lots.setdefault(code, []).append({"acquired_on": row["date"], "qty": qty})
        else:
            cash += notional-fee-tax
            to_sell = qty
            for lot in lots.get(code, []):
                if lot["acquired_on"] >= row["date"]:
                    continue
                take = min(to_sell, lot["qty"])
                lot["qty"] -= take
                to_sell -= take
                if not to_sell:
                    break
            if to_sell:
                raise AssertionError("settlement accounting mismatch")
            lots[code] = [lot for lot in lots.get(code, []) if lot["qty"] > 0]
    if cash < -1e-7:
        raise AssertionError("negative cash after trade")
    return cash, {
        "date": row["date"], "code": code, "side": side,
        "requested_qty": requested, "filled_qty": qty,
        "status": "FILLED" if qty == requested else ("PARTIAL" if qty else "REJECTED"),
        "reason": ("OK" if qty == requested else reason if reason != "OK" else "CAP"),
        "quote_open": row["open"], "execution_price": execution,
        "notional": notional, "commission": fee, "tax": tax,
        "cash_after": cash, "position_after": holdings_qty(lots, code),
    }


def trade_to_target(rows: list[dict], weights: dict[str, float], cash: float,
                    lots: dict[str, list[dict]], config: dict) -> tuple[float, list[dict]]:
    by_code = {r["code"]: r for r in rows}
    equity = cash + sum(holdings_qty(lots, c)*r["open"] for c, r in by_code.items())
    orders = []
    for code in sorted(by_code):
        current = holdings_qty(lots, code)
        target = max(0, math.floor((equity*weights.get(code, 0.0)/
                                    by_code[code]["open"]) / config["lot_size"])
                     * config["lot_size"])
        delta = target-current
        if delta:
            orders.append(("BUY" if delta > 0 else "SELL", code, abs(delta)))
    events = []
    # Sell first; this might create funding for new purchases.
    for side, code, qty in sorted(orders, key=lambda v: (v[0] != "SELL", v[1])):
        cash, event = apply_order(side, code, qty, by_code[code], cash, lots, config)
        events.append(event)
    return cash, events


def current_weights(rows: list[dict], cash: float,
                    lots: dict[str, list[dict]]) -> dict[str, float]:
    nav = cash + sum(holdings_qty(lots, r["code"])*r["close"] for r in rows)
    if nav <= 0:
        raise ValueError("nonpositive portfolio equity")
    return {r["code"]: holdings_qty(lots, r["code"])*r["close"]/nav for r in rows}


def mark_to_market(rows: list[dict], cash: float,
                   lots: dict[str, list[dict]]) -> dict:
    positions = {r["code"]: holdings_qty(lots, r["code"]) for r in rows}
    prices = {r["code"]: r["close"] for r in rows}
    value = sum(positions[code]*prices[code] for code in positions)
    return {"date": rows[0]["date"], "cash": cash,
            "positions": positions, "marks": prices, "stock_value": value,
            "nav": cash+value}


def simulate(market: list[list[dict]], config: dict,
             policy: str = "optimized") -> dict:
    if policy not in ("optimized", "equal_weight", "cash"):
        raise ValueError("unknown policy")
    validate_market(market)
    cash = float(config["initial_cash"])
    lots: dict[str, list[dict]] = defaultdict(list)
    ledger, snapshots, decisions = [], [], []
    for index, rows in enumerate(market):
        if index:
            target = decisions[-1]["target"]
            cash, events = trade_to_target(rows, target, cash, lots, config)
            ledger.extend(events)
        snapshots.append(mark_to_market(rows, cash, lots))
        if index == len(market)-1:
            continue
        if policy == "optimized":
            selection = optimize_weights(
                rows, market[:index+1], current_weights(rows, cash, lots), config)
            target = selection["target"]
            risk_data = selection["risk_data"]
            optimizer = {"objective": selection["objective"],
                         "candidates_checked": selection["candidates_checked"],
                         "target_cash_weight": selection["target_cash_weight"],
                         "weight_l1_change": selection["weight_l1_change"]}
        elif policy == "equal_weight":
            target = {code: 1/len(EXPECTED_CODES) for code in EXPECTED_CODES}
            risk_data = {"method": "not_used"}
            optimizer = None
        else:
            target = {code: 0.0 for code in EXPECTED_CODES}
            risk_data = {"method": "not_used"}
            optimizer = None
        decision_at = moment(rows[0]["decision_at"])
        next_open = moment(market[index+1][0]["open_at"])
        if not decision_at < next_open:
            raise ValueError("decision is not earlier than next open")
        decisions.append({
            "date": rows[0]["date"], "decision_at": rows[0]["decision_at"],
            "execute_date": market[index+1][0]["date"],
            "execute_at": market[index+1][0]["open_at"],
            "latest_feature_known_at": max(r["score_known_at"] for r in rows),
            "risk_history_last_date": risk_data.get("latest_used_date"),
            "policy": policy, "target": target, "optimizer": optimizer,
            "risk_data": risk_data,
        })
    return {"policy": policy, "ledger": ledger, "snapshots": snapshots,
            "decisions": decisions,
            "final_nav": snapshots[-1]["nav"],
            "simple_total_return": snapshots[-1]["nav"]/config["initial_cash"]-1,
            "fill_count": sum(e["filled_qty"] > 0 for e in ledger),
            "reject_count": sum(e["filled_qty"] == 0 for e in ledger),
            "partial_count": sum(e["status"] == "PARTIAL" for e in ledger),
            "commission_paid": sum(e["commission"] for e in ledger),
            "tax_paid": sum(e["tax"] for e in ledger)}


def audit_simulation(out: dict, config: dict) -> dict:
    """Cash conservation and daily close marks; independent ledger algebra."""
    cash = config["initial_cash"]
    for event in out["ledger"]:
        money = event["notional"]
        if event["side"] == "BUY":
            cash -= money+event["commission"]+event["tax"]
        else:
            cash += money-event["commission"]-event["tax"]
        if abs(cash-event["cash_after"]) > 1e-7:
            raise ValueError("ledger cash does not reconcile")
    end = out["snapshots"][-1]
    if abs(cash-end["cash"]) > 1e-7:
        raise ValueError("terminal cash does not reconcile")
    for snapshot in out["snapshots"]:
        recomputed = snapshot["cash"]+sum(
            snapshot["positions"][code]*snapshot["marks"][code]
            for code in EXPECTED_CODES)
        if abs(snapshot["nav"]-recomputed) > 1e-7:
            raise ValueError("NAV/positions/marks mismatch")
    if any(snapshot["cash"] < -1e-7 for snapshot in out["snapshots"]):
        raise ValueError("negative cash found")
    for decision in out["decisions"]:
        if moment(decision["decision_at"]) >= moment(decision["execute_at"]):
            raise ValueError("future execution before decision")
        if moment(decision["latest_feature_known_at"]) > moment(decision["decision_at"]):
            raise ValueError("future feature enters decision")
        if decision["risk_history_last_date"] is not None:
            if decision["risk_history_last_date"] > decision["date"]:
                raise ValueError("future risk history")
    return {"cash_reconciles": True, "nav_reconciles": True,
            "decision_timing_reconciles": True,
            "reconciled_ledger_events": len(out["ledger"])}


def run_lab(config: dict | None = None, market: list[list[dict]] | None = None) -> dict:
    spec = dict(CONFIG if config is None else config)
    prices = synthetic_market() if market is None else market
    validate_market(prices)
    cases = {policy: simulate(prices, spec, policy)
             for policy in ("cash", "equal_weight", "optimized")}
    audit = {policy: audit_simulation(out, spec) for policy, out in cases.items()}
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {
        "source_kind": "SYNTHETIC_ONLY_NOT_REAL_A_SHARE_PERFORMANCE",
        "study_id": spec["study_id"], "config_sha256": digest(spec),
        "input_sha256": digest(prices), "code_sha256": source_hash,
        "config": spec, "input_days": len(prices), "codes": list(EXPECTED_CODES),
        "cases": cases, "audit": audit,
        "limitations": [
            "All prices, sectors, volume, blocked states and signals are synthetic.",
            "The grid search is exact only on its coarse declared weight grid.",
            "Risk estimates are a short teaching sample, not a calibrated risk model.",
            "T+1, fees and price restrictions are simplified, not dated rulebooks.",
            "Open-price adverse fills are hypothetical and not order-book fills.",
            "No real future labels, corporate actions, order queue or capacity proof.",
            "Do not interpret any synthetic net return as A-share alpha.",
        ],
    }
    result["report_sha256"] = digest(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print full audit")
    parser.add_argument("--output", type=Path, help="Create immutable JSON report")
    args = parser.parse_args()
    result = run_lab()
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        if args.output.exists():
            raise FileExistsError("refusing to overwrite existing research artifact")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload+"\n", encoding="utf-8")
        print(f"Created synthetic audit artifact: {args.output}")
    elif args.json:
        print(payload)
    else:
        print("SYNTHETIC ONLY — no real A-share trading evidence.")
        for policy, out in result["cases"].items():
            print(f"{policy}: final_NAV={out['final_nav']:.2f}, "
                  f"hypothetical_net_return={out['simple_total_return']:.4%}, "
                  f"fills={out['fill_count']}, rejects={out['reject_count']}")
        print(f"Contract/report fingerprint: {result['report_sha256'][:16]}")


if __name__ == "__main__":
    main()
