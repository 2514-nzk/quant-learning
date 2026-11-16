#!/usr/bin/env python3
"""Audit a normalized synthetic L2 event ledger. SYNTHETIC_ONLY; stdlib only."""
from __future__ import annotations
import argparse
import json
import math
from datetime import datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/teaching/volume3_l2_synthetic_v1.json"
DATASET_ID = "volume3-l2-synthetic-v1"

def parse_ts(value):
    try:
        result = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ISO timestamp: {value!r}") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Every timestamp must include an explicit UTC offset")
    return result

def _positive_int(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")

def load_fixture(path=DATA):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate(data)
    return data

def validate(data):
    if data.get("dataset_id") != DATASET_ID or data.get("evidence_grade") != "SYNTHETIC_ONLY":
        raise ValueError("Only the declared SYNTHETIC_ONLY teaching fixture is accepted")
    if data.get("calendar") != "ARTIFICIAL_SESSION_CLOCK_NO_EXCHANGE_CALENDAR":
        raise ValueError("The teaching clock must not be mistaken for an exchange calendar")
    source = data.get("source_contract", {})
    if source.get("is_exchange_raw") is not False or source.get("is_qmt_tick") is not False:
        raise ValueError("The fixture must remain explicitly separate from exchange raw feeds and QMT Tick")
    session = data.get("session", {})
    if session.get("venue") != "SSE":
        raise ValueError("Unexpected venue reference in teaching fixture")
    if session.get("trade_date") != "2099-01-01":
        raise ValueError("Unexpected synthetic date")
    date = session["trade_date"]
    auction = session.get("auction_snapshots", [])
    if len(auction) != 3:
        raise ValueError("Expected exactly three opening-auction indicative snapshots")
    prior = None
    for row in auction:
        stamp = parse_ts(row["exchange_time"])
        received = parse_ts(row["receive_time"])
        if stamp.date().isoformat() != date or received < stamp:
            raise ValueError("Auction event date or receive-time ordering is invalid")
        if prior is not None and stamp <= prior:
            raise ValueError("Auction snapshots must be strictly ordered")
        prior = stamp
        local = stamp.timetz().replace(tzinfo=None)
        cancelable = local < time(9, 20)
        if row["rule_derived_cancel_allowed"] is not cancelable:
            raise ValueError("Auction cancel flag disagrees with the frozen 09:20 cutoff")
        for key in ("indicative_price_ticks", "indicative_matched_qty",
                    "unmatched_buy_qty", "unmatched_sell_qty"):
            if isinstance(row[key], bool) or not isinstance(row[key], int) or row[key] < 0:
                raise ValueError(f"Invalid auction field: {key}")
    result = session["auction_result"]
    result_time = parse_ts(result["result_time"])
    if result_time.date().isoformat() != date or result_time.timetz().replace(tzinfo=None) != time(9,25):
        raise ValueError("Opening auction result must be timestamped at 09:25 in the synthetic clock")
    _positive_int(result["opening_price_ticks"], "opening_price_ticks")
    _positive_int(result["matched_qty"], "auction matched_qty")

    events = session.get("order_trade_events", [])
    if len(events) != data.get("expected_order_events"):
        raise ValueError("Unexpected event count")
    if [x["sequence_no"] for x in events] != list(range(1, len(events)+1)):
        raise ValueError("Event sequence numbers must be unique and contiguous")
    event_ids = [x["event_id"] for x in events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("Duplicate event_id")
    prior_stamp = None
    orders = {}
    trade_ids = set()
    for event in events:
        stamp, received = parse_ts(event["exchange_time"]), parse_ts(event["receive_time"])
        if stamp.date().isoformat() != date or received < stamp:
            raise ValueError("Event date or receive-time ordering is invalid")
        if prior_stamp is not None and stamp < prior_stamp:
            raise ValueError("Exchange event time must be nondecreasing by sequence")
        prior_stamp = stamp
        if event["event_type"] == "ORDER_ADD":
            order_id = event["order_id"]
            if order_id in orders:
                raise ValueError("Duplicate order_id")
            if event["side"] not in ("BUY", "SELL"):
                raise ValueError("Order side must be BUY or SELL")
            _positive_int(event["price_ticks"], "order price_ticks")
            _positive_int(event["quantity"], "order quantity")
            orders[order_id] = {
                "side":event["side"], "price_ticks":event["price_ticks"],
                "submitted":event["quantity"], "cancelled":0, "executed":0,
                "remaining":event["quantity"]
            }
        elif event["event_type"] == "ORDER_CANCEL":
            order = orders.get(event["order_id"])
            if order is None:
                raise ValueError("Cancellation references an unknown order")
            _positive_int(event["cancelled_qty"], "cancelled_qty")
            if event["cancelled_qty"] > order["remaining"]:
                raise ValueError("Cancellation exceeds remaining order quantity")
            order["cancelled"] += event["cancelled_qty"]
            order["remaining"] -= event["cancelled_qty"]
        elif event["event_type"] == "TRADE":
            trade_id = event["trade_id"]
            if trade_id in trade_ids:
                raise ValueError("Duplicate trade_id")
            trade_ids.add(trade_id)
            _positive_int(event["price_ticks"], "trade price_ticks")
            _positive_int(event["quantity"], "trade quantity")
            buy, sell = orders.get(event["buy_order_id"]), orders.get(event["sell_order_id"])
            if buy is None or sell is None:
                raise ValueError("Trade references an unknown order")
            if buy["side"] != "BUY" or sell["side"] != "SELL":
                raise ValueError("Trade order-side linkage is invalid")
            if buy["price_ticks"] < event["price_ticks"] or sell["price_ticks"] > event["price_ticks"]:
                raise ValueError("Trade price violates a linked limit price")
            if event["quantity"] > buy["remaining"] or event["quantity"] > sell["remaining"]:
                raise ValueError("Trade quantity exceeds remaining order quantity")
            for order in (buy, sell):
                order["executed"] += event["quantity"]
                order["remaining"] -= event["quantity"]
        else:
            raise ValueError(f"Unsupported event type: {event['event_type']}")
    if len(orders) != data.get("expected_orders") or len(trade_ids) != data.get("expected_trades"):
        raise ValueError("Order/trade counts do not match the fixture contract")
    for order in orders.values():
        if order["submitted"] != order["cancelled"] + order["executed"] + order["remaining"]:
            raise ValueError("Order lifecycle conservation failed")

    snapshots = session.get("book_snapshots", [])
    if len(snapshots) < 2:
        raise ValueError("At least two book snapshots are required for OFI")
    prior_stamp, prior_watermark = None, -1
    for snap in snapshots:
        stamp, received = parse_ts(snap["exchange_time"]), parse_ts(snap["receive_time"])
        if stamp.date().isoformat() != date or received < stamp:
            raise ValueError("Book snapshot date or receive-time ordering is invalid")
        if prior_stamp is not None and stamp <= prior_stamp:
            raise ValueError("Book snapshots must be strictly ordered")
        if snap["event_sequence_watermark"] <= prior_watermark:
            raise ValueError("Book event-sequence watermarks must increase")
        prior_stamp, prior_watermark = stamp, snap["event_sequence_watermark"]
        for side in ("bids", "asks"):
            levels = snap[side]
            if len(levels) != 5:
                raise ValueError("Teaching snapshots must contain exactly five levels per side")
            prices = [x["price_ticks"] for x in levels]
            if any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in prices):
                raise ValueError("Book prices must be positive integer ticks")
            if any(x["quantity"] <= 0 for x in levels):
                raise ValueError("Book quantities must be positive")
            expected = sorted(prices, reverse=(side == "bids"))
            if prices != expected or len(prices) != len(set(prices)):
                raise ValueError("Book levels must be unique and correctly ordered")
        if snap["bids"][0]["price_ticks"] >= snap["asks"][0]["price_ticks"]:
            raise ValueError("A published post-match book snapshot cannot be crossed")
        if snap["event_sequence_watermark"] > len(events):
            raise ValueError("Book snapshot watermark exceeds the event ledger")

    cases = data.get("measurement_cases", [])
    if len(cases) != 5:
        raise ValueError("Expected five explicit measurement-semantics examples")
    case_ids = [x["case_id"] for x in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Duplicate measurement case id")

def classify_measurement(numerator, denominator, source_coverage_complete, applicable):
    if not applicable:
        return {"value":None,"status":"NOT_APPLICABLE"}
    if not source_coverage_complete:
        return {"value":None,"status":"MISSING_SOURCE_COVERAGE"}
    if numerator is None or denominator is None:
        return {"value":None,"status":"MISSING_FIELD"}
    if denominator == 0:
        return {"value":None,"status":"UNDEFINED_ZERO_DENOMINATOR"}
    value = numerator / denominator
    return {"value":value,"status":"OBSERVED_ZERO" if numerator == 0 else "OBSERVED"}

def _ratio(numerator, denominator):
    return classify_measurement(numerator, denominator, True, True)

def build_order_ledger(events, threshold):
    orders = {}
    trades = []
    for event in events:
        kind = event["event_type"]
        if kind == "ORDER_ADD":
            orders[event["order_id"]] = {
                "side":event["side"], "bucket":"LARGE" if event["quantity"] >= threshold else "SMALL",
                "submitted":event["quantity"], "cancelled":0, "executed":0,
                "open":event["quantity"]
            }
        elif kind == "ORDER_CANCEL":
            row = orders[event["order_id"]]
            row["cancelled"] += event["cancelled_qty"]
            row["open"] -= event["cancelled_qty"]
        else:
            trades.append(event)
            for order_id in (event["buy_order_id"], event["sell_order_id"]):
                row = orders[order_id]
                row["executed"] += event["quantity"]
                row["open"] -= event["quantity"]
    def aggregate(rows):
        submitted = sum(x["submitted"] for x in rows)
        cancelled = sum(x["cancelled"] for x in rows)
        executed = sum(x["executed"] for x in rows)
        opened = sum(x["open"] for x in rows)
        return {
            "orders":len(rows),"submitted_qty":submitted,"cancelled_qty":cancelled,
            "executed_qty":executed,"open_qty":opened,
            "cancelled_to_submitted":_ratio(cancelled,submitted),
            "cancelled_to_terminal_qty":_ratio(cancelled,cancelled+executed),
            "lifecycle_reconciles":submitted == cancelled + executed + opened
        }
    by_side = {}
    by_bucket = {}
    for side in ("BUY","SELL"):
        side_rows = [x for x in orders.values() if x["side"] == side]
        by_side[side] = aggregate(side_rows)
        for bucket in ("LARGE","SMALL"):
            by_bucket[f"{side}_{bucket}"] = aggregate(
                [x for x in side_rows if x["bucket"] == bucket]
            )
    return {"order_count":len(orders),"trade_count":len(trades),
            "unique_trade_qty":sum(x["quantity"] for x in trades),
            "by_side":by_side,"by_size_bucket":by_bucket}

def _depth_imbalance(bids, asks, levels):
    bid_qty = sum(x["quantity"] for x in bids[:levels])
    ask_qty = sum(x["quantity"] for x in asks[:levels])
    result = _ratio(bid_qty-ask_qty,bid_qty+ask_qty)
    return {"value":result["value"],"status":result["status"],
            "bid_depth_qty":bid_qty,"ask_depth_qty":ask_qty}

def _side_ofi(current_price, current_qty, previous_price, previous_qty, side):
    if side == "BID":
        if current_price > previous_price:
            return current_qty
        if current_price == previous_price:
            return current_qty - previous_qty
        return -previous_qty
    if current_price > previous_price:
        return -current_qty
    if current_price == previous_price:
        return current_qty - previous_qty
    return previous_qty

def build_book_features(snapshots):
    output, previous = [], None
    for snap in snapshots:
        bids, asks = snap["bids"], snap["asks"]
        bid, ask = bids[0], asks[0]
        spread = ask["price_ticks"] - bid["price_ticks"]
        row = {
            "snapshot_id":snap["snapshot_id"],
            "exchange_time":snap["exchange_time"],
            "best_bid_ticks":bid["price_ticks"],"best_bid_qty":bid["quantity"],
            "best_ask_ticks":ask["price_ticks"],"best_ask_qty":ask["quantity"],
            "spread_ticks":spread,
            "mid_price_ticks":(bid["price_ticks"]+ask["price_ticks"])/2,
            "top1_imbalance":_depth_imbalance(bids,asks,1),
            "top5_imbalance":_depth_imbalance(bids,asks,5)
        }
        if previous is None:
            row["ofi_shares"] = None
            row["ofi_status"] = "NOT_APPLICABLE_FIRST_SNAPSHOT"
        else:
            prev_bid, prev_ask = previous["bids"][0], previous["asks"][0]
            eb = _side_ofi(bid["price_ticks"],bid["quantity"],
                           prev_bid["price_ticks"],prev_bid["quantity"],"BID")
            ea = _side_ofi(ask["price_ticks"],ask["quantity"],
                           prev_ask["price_ticks"],prev_ask["quantity"],"ASK")
            row["ofi_shares"] = eb - ea
            row["ofi_status"] = "OBSERVED"
        output.append(row)
        previous = snap
    return output

def evaluate(data=None):
    if data is None:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    validate(data)
    session = data["session"]
    auction_rows = []
    for row in session["auction_snapshots"]:
        numerator = row["unmatched_buy_qty"] - row["unmatched_sell_qty"]
        denominator = row["unmatched_buy_qty"] + row["unmatched_sell_qty"]
        ratio = _ratio(numerator,denominator)
        auction_rows.append({
            "snapshot_id":row["snapshot_id"],"exchange_time":row["exchange_time"],
            "indicative_price_ticks":row["indicative_price_ticks"],
            "indicative_matched_qty":row["indicative_matched_qty"],
            "unmatched_buy_qty":row["unmatched_buy_qty"],
            "unmatched_sell_qty":row["unmatched_sell_qty"],
            "net_unmatched_buy_qty":numerator,
            "imbalance_ratio":ratio
        })
    final = session["auction_result"]
    last = auction_rows[-1]
    ledger = build_order_ledger(session["order_trade_events"],data["large_order_threshold_shares"])
    book = build_book_features(session["book_snapshots"])
    quality = []
    for row in data["measurement_cases"]:
        status = classify_measurement(row["numerator"],row["denominator"],
                                      row["source_coverage_complete"],row["applicable"])
        quality.append({"case_id":row["case_id"],"metric":row["metric"],**status})
    buy, sell = ledger["by_side"]["BUY"], ledger["by_side"]["SELL"]
    audit = [
        {"metric":"buy_cancelled_to_submitted","unit":"ratio",**buy["cancelled_to_submitted"]},
        {"metric":"sell_cancelled_to_submitted","unit":"ratio",**sell["cancelled_to_submitted"]},
        {"metric":"last_auction_unmatched_imbalance","unit":"ratio",**last["imbalance_ratio"]},
        {"metric":"institutional_identity_or_capital_flow","unit":"not_observable","value":None,"status":"NOT_OBSERVABLE_FROM_THIS_SCHEMA"}
    ]
    return {
        "dataset_id":data["dataset_id"],"evidence_grade":data["evidence_grade"],
        "source_contract":data["source_contract"],
        "auction":{
            "snapshots":auction_rows,"final_opening_price_ticks":final["opening_price_ticks"],
            "final_matched_qty":final["matched_qty"],
            "last_indicative_minus_final_price_ticks":last["indicative_price_ticks"]-final["opening_price_ticks"]
        },
        "order_lifecycle":ledger,
        "book_features":book,
        "measurement_audit":audit,
        "measurement_semantics":quality,
        "claims":{
            "real_market_L2_validated":False,"qmt_tick_equivalence_proven":False,
            "institutional_flow_identified":False,"strategy_alpha_proven":False,
            "execution_proven":False
        },
        "interpretation":"A deterministic teaching audit of a normalized synthetic event ledger and synthetic snapshots. It verifies accounting and feature calculations only; it does not validate an exchange feed, QMT Tick equivalence, market predictability, investor identity or executable returns."
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json",action="store_true",help="Print the complete machine-readable audit")
    args = parser.parse_args()
    result = evaluate()
    if args.json:
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    else:
        buy = result["order_lifecycle"]["by_side"]["BUY"]
        sell = result["order_lifecycle"]["by_side"]["SELL"]
        print("SYNTHETIC_ONLY — no real market or QMT Tick evidence")
        print(f"Events: {result['order_lifecycle']['order_count']} orders, {result['order_lifecycle']['trade_count']} trades")
        print(f"Buy cancelled/submitted: {buy['cancelled_to_submitted']['value']:.3%}")
        print(f"Sell cancelled/submitted: {sell['cancelled_to_submitted']['value']:.3%}")
        print("OFI (shares): " + ", ".join("NA" if x["ofi_shares"] is None else str(x["ofi_shares"]) for x in result["book_features"]))
        print("The output checks a synthetic ledger, not a trading signal.")

if __name__ == "__main__":
    main()
