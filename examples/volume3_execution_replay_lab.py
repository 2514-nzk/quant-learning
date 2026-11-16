#!/usr/bin/env python3
"""Deterministic queue-aware execution replay. SYNTHETIC_ONLY; stdlib only."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/teaching/volume3_execution_synthetic_v1.json"
DATASET_ID = "volume3-execution-synthetic-v1"

def parse_ts(value):
    try:
        result = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ISO timestamp: {value!r}") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Every timestamp must include an explicit UTC offset")
    return result

def positive_int(value, label, allow_zero=False):
    valid = isinstance(value, int) and not isinstance(value, bool) and (value >= 0 if allow_zero else value > 0)
    if not valid:
        raise ValueError(f"{label} must be {'a nonnegative' if allow_zero else 'a positive'} integer")

def load_fixture(path=DATA):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate(data)
    return data

def validate(data):
    if data.get("dataset_id") != DATASET_ID or data.get("evidence_grade") != "SYNTHETIC_ONLY":
        raise ValueError("Only the declared SYNTHETIC_ONLY execution fixture is accepted")
    if data.get("calendar") != "ARTIFICIAL_SESSION_CLOCK_NO_EXCHANGE_CALENDAR":
        raise ValueError("Teaching timestamps must not be mistaken for an exchange calendar")
    source = data.get("source_contract", {})
    if any(source.get(k) is not False for k in ("is_exchange_raw", "is_qmt_tick", "is_real_market_data")):
        raise ValueError("Synthetic fixture must remain separate from exchange raw, QMT Tick and real data")
    if source.get("queue_coverage") != "COMPLETE_SYNTHETIC_QUEUE_AHEAD_ORDER_IDS":
        raise ValueError("Queue coverage must be explicit")
    assumptions = data.get("assumptions", {})
    if assumptions.get("tick_size_cny") != 0.01 or assumptions.get("commission_bps") is None:
        raise ValueError("Missing frozen teaching tick-size or fee assumption")
    orders = data.get("orders", [])
    if len(orders) != data.get("expected_order_plans"):
        raise ValueError("Unexpected number of order plans")
    ids = [x.get("order_id") for x in orders]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate order_id")
    by_id = {x["order_id"]: x for x in orders}
    dates = set()
    for order in orders:
        oid = order["order_id"]
        if order.get("mode") not in ("PASSIVE_LIMIT", "IOC_LIMIT"):
            raise ValueError(f"Unsupported order mode for {oid}")
        if order.get("side") not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side for {oid}")
        positive_int(order.get("quantity"), f"{oid}.quantity")
        positive_int(order.get("limit_price_ticks"), f"{oid}.limit_price_ticks")
        positive_int(order.get("max_quote_age_ms"), f"{oid}.max_quote_age_ms", allow_zero=True)
        positive_int(order.get("decision_mid_ticks"), f"{oid}.decision_mid_ticks")
        signal = parse_ts(order["signal_time"])
        signal_available = parse_ts(order["signal_available_at"])
        decision = parse_ts(order["decision_time"])
        submit = parse_ts(order["submit_time"])
        expiry = parse_ts(order["expiry_time"])
        dates.add(signal.date().isoformat())
        if not signal <= signal_available <= decision <= submit < expiry:
            raise ValueError(f"Signal/availability/decision/submit/expiry chronology is invalid for {oid}")
        grid = order.get("latency_grid_ms", [])
        if not grid or len(grid) != len(set(grid)):
            raise ValueError(f"Latency grid must be nonempty and unique for {oid}")
        for latency in grid:
            positive_int(latency, f"{oid}.latency_ms", allow_zero=True)
            if submit + timedelta(milliseconds=latency) >= expiry:
                raise ValueError(f"Order arrival must precede expiry for {oid}")
        snapshots = order.get("book_snapshots", [])
        if not snapshots:
            raise ValueError(f"No book snapshots for {oid}")
        previous_available = None
        all_queue_ids = set()
        for snap in snapshots:
            ex, received, available = (parse_ts(snap[k]) for k in ("exchange_time", "receive_time", "available_at"))
            dates.add(ex.date().isoformat())
            if not ex <= received <= available:
                raise ValueError(f"Snapshot exchange/receive/available chronology invalid for {oid}")
            if previous_available is not None and available <= previous_available:
                raise ValueError(f"Snapshots must be ordered by available_at for {oid}")
            previous_available = available
            bid, ask = snap["best_bid_ticks"], snap["best_ask_ticks"]
            positive_int(bid, f"{oid}.best_bid_ticks")
            positive_int(ask, f"{oid}.best_ask_ticks")
            if bid >= ask:
                raise ValueError(f"Crossed or locked book in {oid}")
            for side in ("bids", "asks"):
                levels = snap[side]
                if not levels:
                    raise ValueError(f"Empty {side} depth in {oid}")
                prices = [x["price_ticks"] for x in levels]
                expected = sorted(prices, reverse=(side == "bids"))
                if prices != expected or len(prices) != len(set(prices)):
                    raise ValueError(f"Unsorted or duplicate {side} levels in {oid}")
                for level in levels:
                    positive_int(level["price_ticks"], f"{oid}.{side}.price_ticks")
                    positive_int(level["quantity"], f"{oid}.{side}.quantity")
            queue = snap.get("queue_ahead_orders", [])
            qids = [x["order_id"] for x in queue]
            if len(qids) != len(set(qids)):
                raise ValueError(f"Duplicate queue order id in {oid}")
            if order["mode"] == "PASSIVE_LIMIT":
                expected_best = snap["best_bid_ticks"] if order["side"] == "BUY" else snap["best_ask_ticks"]
                if snap.get("queue_price_ticks") != order["limit_price_ticks"] or expected_best != order["limit_price_ticks"]:
                    raise ValueError(f"Passive queue snapshot must be at the order's best-price level for {oid}")
                for q in queue:
                    positive_int(q["remaining_qty"], f"{oid}.queue.remaining_qty")
                    if q["price_ticks"] != order["limit_price_ticks"] or parse_ts(q["accepted_at"]) > ex:
                        raise ValueError(f"Queue-ahead order price/time is invalid for {oid}")
                    all_queue_ids.add(q["order_id"])
            elif queue:
                raise ValueError(f"IOC teaching orders do not use passive queue snapshots: {oid}")
        events = order.get("events", [])
        if [x["sequence_no"] for x in events] != list(range(1, len(events)+1)):
            raise ValueError(f"Event sequence must be contiguous for {oid}")
        prior_event = None
        for event in events:
            ex, received, available = (parse_ts(event[k]) for k in ("exchange_time", "receive_time", "available_at"))
            dates.add(ex.date().isoformat())
            if not ex <= received <= available:
                raise ValueError(f"Event exchange/receive/available chronology invalid for {oid}")
            if prior_event is not None and ex < prior_event:
                raise ValueError(f"Events must be ordered by exchange time for {oid}")
            prior_event = ex
            if event["event_type"] == "TRADE":
                positive_int(event.get("price_ticks"), f"{oid}.trade.price_ticks")
                positive_int(event.get("quantity"), f"{oid}.trade.quantity")
                if event.get("aggressor_side") not in ("BUY", "SELL"):
                    raise ValueError(f"Invalid aggressor side in {oid}")
            elif event["event_type"] == "CANCEL_AHEAD":
                positive_int(event.get("cancelled_qty"), f"{oid}.cancelled_qty")
                if event.get("order_id") not in all_queue_ids:
                    raise ValueError(f"Cancellation does not identify an ahead order in {oid}")
            else:
                raise ValueError(f"Unsupported event type in {oid}: {event['event_type']}")
        markout_time = parse_ts(order["markout_time"])
        if markout_time <= expiry:
            raise ValueError(f"Markout must be after order expiry for {oid}")
        if not isinstance(order["markout_mid_ticks"], (int, float)) or order["markout_mid_ticks"] <= 0:
            raise ValueError(f"Invalid post-trade markout mid for {oid}")
    if len(dates) != 1:
        raise ValueError("All teaching records must use one artificial session date")
    for order in orders:
        parent_id = order.get("parent_order_id")
        if parent_id:
            parent = by_id.get(parent_id)
            if parent is None or parent.get("mode") != "PASSIVE_LIMIT":
                raise ValueError(f"Unknown cancel/replace parent for {order['order_id']}")
            ack = parse_ts(order["parent_cancel_ack_time"])
            if ack < parse_ts(parent["expiry_time"]) or parse_ts(order["submit_time"]) <= ack:
                raise ValueError("Replacement must be submitted after the old order's cancel acknowledgement")
            if parent["side"] != order["side"] or parent["limit_price_ticks"] == order["limit_price_ticks"]:
                raise ValueError("Teaching cancel/replace must keep side and demonstrate a changed limit price")

def _arrival(order, latency_ms):
    return parse_ts(order["submit_time"]) + timedelta(milliseconds=latency_ms)

def _select_snapshot(order, arrival):
    candidates = [s for s in order["book_snapshots"] if parse_ts(s["available_at"]) <= arrival]
    if not candidates:
        return None, None
    snap = candidates[-1]
    age = (arrival - parse_ts(snap["available_at"])).total_seconds() * 1000
    return snap, age

def _finish_metrics(order, fills, snap, age_ms, data):
    filled = sum(x["quantity"] for x in fills)
    qty = order["quantity"]
    if filled == 0:
        return {"filled_qty":0,"unfilled_qty":qty,"fill_ratio":0.0,
                "vwap_ticks":None,"price_shortfall_bps":None,"delay_cost_bps":None,
                "execution_vs_arrival_bps":None,"fee_bps":None,"total_cost_bps":None,
                "markout_bps":None,"fee_cny":0.0}
    vwap = sum(x["price_ticks"] * x["quantity"] for x in fills) / filled
    sign = 1 if order["side"] == "BUY" else -1
    decision_mid = float(order["decision_mid_ticks"])
    arrival_mid = (snap["best_bid_ticks"] + snap["best_ask_ticks"]) / 2
    shortfall = sign * (vwap - decision_mid) / decision_mid * 10000
    delay = sign * (arrival_mid - decision_mid) / decision_mid * 10000
    execution = sign * (vwap - arrival_mid) / decision_mid * 10000
    fee_bps = float(data["assumptions"]["commission_bps"])
    notional = vwap * data["assumptions"]["tick_size_cny"] * filled
    fee = notional * fee_bps / 10000
    markout = sign * sum(
        ((order["markout_mid_ticks"] - x["price_ticks"]) / x["price_ticks"] * 10000) * x["quantity"]
        for x in fills
    ) / filled
    return {"filled_qty":filled,"unfilled_qty":qty-filled,"fill_ratio":filled/qty,
            "vwap_ticks":vwap,"price_shortfall_bps":shortfall,"delay_cost_bps":delay,
            "execution_vs_arrival_bps":execution,"fee_bps":fee_bps,
            "total_cost_bps":shortfall+fee_bps,"fee_cny":fee,"markout_bps":markout}

def replay_passive(order, latency_ms, credit_identified_cancels, data):
    arrival = _arrival(order, latency_ms)
    expiry = parse_ts(order["expiry_time"])
    snap, age = _select_snapshot(order, arrival)
    base = {"order_id":order["order_id"],"mode":order["mode"],"latency_ms":latency_ms,
            "arrival_time":arrival.isoformat(timespec="milliseconds"),
            "cancel_credit_identified_ahead":credit_identified_cancels}
    if snap is None:
        return {**base,"status":"NO_VALID_BOOK","quote_age_ms":None,
                **_finish_metrics(order,[],None,None,data),"initial_queue_ahead_qty":None,
                "queue_ahead_remaining_qty":None,"cancel_credit_qty":0,
                "touch_only_assumed_qty":0,"fills":[]}
    if age > order["max_quote_age_ms"]:
        return {**base,"status":"STALE_BOOK_REJECTED","quote_age_ms":age,
                **_finish_metrics(order,[],snap,age,data),"initial_queue_ahead_qty":None,
                "queue_ahead_remaining_qty":None,"cancel_credit_qty":0,
                "touch_only_assumed_qty":0,"fills":[]}
    queue = [{"order_id":x["order_id"],"remaining_qty":x["remaining_qty"]}
             for x in snap["queue_ahead_orders"]]
    initial_queue = sum(x["remaining_qty"] for x in queue)
    own_remaining = order["quantity"]
    fills, cancel_credit, trade_volume = [], 0, 0
    touch = False
    contra = "SELL" if order["side"] == "BUY" else "BUY"
    for event in order["events"]:
        event_time = parse_ts(event["exchange_time"])
        if event_time < arrival or event_time > expiry:
            continue
        if event["event_type"] == "CANCEL_AHEAD":
            if not credit_identified_cancels:
                continue
            match = next((x for x in queue if x["order_id"] == event["order_id"]), None)
            if match is not None:
                if event["cancelled_qty"] > match["remaining_qty"]:
                    raise ValueError(f"Ahead cancellation exceeds remaining queue for {order['order_id']}")
                match["remaining_qty"] -= event["cancelled_qty"]
                cancel_credit += event["cancelled_qty"]
            continue
        if event["price_ticks"] != order["limit_price_ticks"] or event["aggressor_side"] != contra:
            continue
        touch = True
        trade_volume += event["quantity"]
        volume_left = event["quantity"]
        for ahead in queue:
            consumed = min(ahead["remaining_qty"], volume_left)
            ahead["remaining_qty"] -= consumed
            volume_left -= consumed
            if volume_left == 0:
                break
        fill_qty = min(own_remaining, volume_left)
        if fill_qty:
            fills.append({"exchange_time":event["exchange_time"],
                          "price_ticks":order["limit_price_ticks"],"quantity":fill_qty})
            own_remaining -= fill_qty
        if own_remaining == 0:
            break
    remaining_queue = sum(x["remaining_qty"] for x in queue)
    status = "FILLED" if own_remaining == 0 else ("PARTIALLY_FILLED_CANCELLED" if own_remaining < order["quantity"] else "CANCELLED_UNFILLED")
    metrics = _finish_metrics(order,fills,snap,age,data)
    return {**base,"status":status,"quote_age_ms":age,
            **metrics,"initial_queue_ahead_qty":initial_queue,
            "queue_ahead_remaining_qty":remaining_queue,"cancel_credit_qty":cancel_credit,
            "trade_volume_at_limit_qty":trade_volume,
            "touch_only_assumed_qty":order["quantity"] if touch else 0,"fills":fills}

def replay_ioc(order, latency_ms, data):
    arrival = _arrival(order,latency_ms)
    snap, age = _select_snapshot(order,arrival)
    base = {"order_id":order["order_id"],"mode":order["mode"],"latency_ms":latency_ms,
            "arrival_time":arrival.isoformat(timespec="milliseconds")}
    if snap is None:
        return {**base,"status":"NO_VALID_BOOK","quote_age_ms":None,
                **_finish_metrics(order,[],None,None,data),"fills":[],"touch_only_assumed_qty":None}
    if age > order["max_quote_age_ms"]:
        return {**base,"status":"STALE_BOOK_REJECTED","quote_age_ms":age,
                **_finish_metrics(order,[],snap,age,data),"fills":[],"touch_only_assumed_qty":None}
    levels = snap["asks"] if order["side"] == "BUY" else snap["bids"]
    fills, remaining = [], order["quantity"]
    for level in levels:
        price = level["price_ticks"]
        eligible = price <= order["limit_price_ticks"] if order["side"] == "BUY" else price >= order["limit_price_ticks"]
        if not eligible:
            break
        take = min(remaining,level["quantity"])
        if take:
            fills.append({"exchange_time":arrival.isoformat(timespec="milliseconds"),
                          "price_ticks":price,"quantity":take})
            remaining -= take
        if remaining == 0:
            break
    status = "FILLED" if remaining == 0 else ("PARTIALLY_FILLED_IOC_CANCELLED" if remaining < order["quantity"] else "UNFILLED_IOC_CANCELLED")
    return {**base,"status":status,"quote_age_ms":age,
            **_finish_metrics(order,fills,snap,age,data),"fills":fills,
            "touch_only_assumed_qty":None,"visible_opposite_depth_qty":sum(x["quantity"] for x in levels)}

def evaluate(data=None):
    if data is None:
        data = load_fixture()
    validate(data)
    outcomes = []
    for order in data["orders"]:
        for latency in order["latency_grid_ms"]:
            if order["mode"] == "PASSIVE_LIMIT":
                outcomes.append(replay_passive(order,latency,True,data))
                outcomes.append(replay_passive(order,latency,False,data))
            else:
                outcomes.append(replay_ioc(order,latency,data))
    main = [x for x in outcomes if x["order_id"] == "P_MAIN"]
    by_latency = {}
    for row in main:
        by_latency.setdefault(str(row["latency_ms"]),{})[
            "identified_ahead_cancel_credit" if row["cancel_credit_identified_ahead"] else "no_cancel_credit"
        ] = {"filled_qty":row["filled_qty"],"fill_ratio":row["fill_ratio"],
             "touch_only_assumed_qty":row["touch_only_assumed_qty"]}
    replacements = {x["order_id"]:x for x in outcomes if x["order_id"] in ("R_OLD","R_NEW") and x.get("cancel_credit_identified_ahead") is True}
    return {
        "dataset_id":data["dataset_id"],"evidence_grade":data["evidence_grade"],
        "source_contract":data["source_contract"],"assumptions":data["assumptions"],
        "execution_outcomes":outcomes,
        "latency_sensitivity":by_latency,
        "cancel_replace":{"old_order_filled_qty":replacements["R_OLD"]["filled_qty"],
                          "old_order_cancel_ack_time":data["orders"][1]["cancel_ack_time"],
                          "replacement_filled_qty":replacements["R_NEW"]["filled_qty"],
                          "replacement_queue_ahead_qty":replacements["R_NEW"]["initial_queue_ahead_qty"],
                          "replacement_parent_id":"R_OLD"},
        "claims":{"real_market_execution_proven":False,"real_fill_probability_calibrated":False,
                  "qmt_tick_equivalence_proven":False,"real_queue_position_reconstructed":False,
                  "strategy_alpha_proven":False,"real_fee_schedule_applied":False},
        "interpretation":"A deterministic synthetic execution replay. Queue fills, latency, visible-depth walking and cost arithmetic are teaching demonstrations only; no real order, exchange feed, calibrated fill probability, QMT Tick equivalence or strategy alpha is established."
    }

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json",action="store_true",help="Print the complete machine-readable replay")
    args=parser.parse_args()
    result=evaluate()
    if args.json:
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    else:
        print("SYNTHETIC_ONLY — no real execution or QMT Tick evidence")
        for latency, row in result["latency_sensitivity"].items():
            print(f"P_MAIN latency={latency}ms: queue-aware={row['identified_ahead_cancel_credit']['filled_qty']} shares; conservative={row['no_cancel_credit']['filled_qty']} shares; touch-only={row['identified_ahead_cancel_credit']['touch_only_assumed_qty']} shares")
        print(f"Cancel/replace: old={result['cancel_replace']['old_order_filled_qty']}, replacement={result['cancel_replace']['replacement_filled_qty']} shares")
        print("The replay validates mechanics, not live fill probabilities or profitability.")

if __name__ == "__main__":
    main()
