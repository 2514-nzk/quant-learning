"""A single reproducible classroom REV20 panel; not a market backtest."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from statistics import mean

SEED = 20261124
STOCKS = 40
SESSIONS = 142
SIGNALS = tuple(range(20, 136, 5))
TOP = 8
SOURCE = "SYNTHETIC_ONLY"


def make_panel():
    """Synthetic session numbers, no exchange calendar or real securities."""
    rng = random.Random(SEED)
    common = [rng.uniform(-.015, .015) for _ in range(SESSIONS)]
    sector = [[rng.uniform(-.012, .012) for _ in range(SESSIONS)] for _ in range(5)]
    panel = {}
    for i in range(STOCKS):
        code = f"S{i+1:02d}"
        opens, closes, amounts = [], [], []
        price = 10 + i / 2
        for t in range(SESSIONS):
            op = price * (1 + common[t] / 2 + rng.uniform(-.012, .012))
            price = op * (1 + common[t] / 2 + sector[i % 5][t] + rng.uniform(-.03, .03))
            opens.append(round(op, 6))
            closes.append(round(price, 6))
            amounts.append(rng.randint(1_000_000, 30_000_000))
        panel[code] = dict(industry=i % 5, listed=50 if i == 38 else 0,
                           delisted=95 if i == 39 else SESSIONS,
                           st_from=80 if i == 37 else SESSIONS,
                           open=opens, close=closes, amount=amounts)
    return panel


def signal_snapshot(panel, t):
    """Eligibility and scores read only observations through session t."""
    scores, excluded = {}, {}
    for code, row in sorted(panel.items()):
        if not row["listed"] <= t < row["delisted"]:
            excluded[code] = "OUTSIDE_LISTING"
        elif t - row["listed"] < 20:
            excluded[code] = "SHORT_HISTORY"
        elif t >= row["st_from"]:
            excluded[code] = "ST_POLICY"
        elif mean(row["amount"][t-4:t+1]) < 8_000_000:
            excluded[code] = "LOW_LIQUIDITY_POLICY"
        else:
            scores[code] = -(row["close"][t] / row["close"][t-20] - 1)
    return scores, excluded


def rank(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(order)
    lo = 0
    while lo < len(order):
        hi = lo + 1
        while hi < len(order) and values[order[hi]] == values[order[lo]]:
            hi += 1
        for j in range(lo, hi):
            out[order[j]] = (lo + hi - 1) / 2
        lo = hi
    return out


def spearman(a, b):
    if len(a) != len(b) or len(a) < 2:
        return None
    x, y = rank(a), rank(b)
    mx, my = mean(x), mean(y)
    xx, yy = sum((v-mx)**2 for v in x), sum((v-my)**2 for v in y)
    if not xx or not yy:
        return None
    return sum((u-mx)*(v-my) for u, v in zip(x, y)) / math.sqrt(xx*yy)


def observe_week(panel, t):
    scores, excluded = signal_snapshot(panel, t)
    selected = sorted(scores, key=lambda k: (-scores[k], k))[:TOP]
    entry, exit_ = t+1, t+6
    labels = {}
    for code in scores:
        row = panel[code]
        if exit_ < row["delisted"] and entry >= row["listed"]:
            labels[code] = row["open"][exit_] / row["open"][entry] - 1
    missing = sorted(scores.keys() - labels.keys())
    comparable = sorted(labels)
    ic = spearman([scores[k] for k in comparable], [labels[k] for k in comparable])
    # Do not silently drop a missing label and reweight the portfolios.
    complete = not missing and len(selected) == TOP
    top = mean(labels[k] for k in selected) if complete else None
    base = mean(labels.values()) if complete else None
    return dict(signal=t, entry=entry, exit=exit_, label_available=exit_,
                eligible=len(scores), excluded=excluded, scores=scores,
                top=selected, labels=labels, missing_labels=missing,
                rank_ic=ic, top_gross=top, equal_gross=base,
                gross_difference=top-base if complete else None)


def trainable(weeks, signal):
    return [w["signal"] for w in weeks
            if w["signal"] < signal and w["label_available"] < signal]


def financial_asof(events, cutoff):
    eligible = [e for e in events if e["available"] <= cutoff and e["period"] <= cutoff]
    return max(eligible, key=lambda e: (e["period"], e["available"], e["revision"])) if eligible else None


def pitfalls():
    """Small independent counterexamples with explicit, artificial assumptions."""
    events = [dict(period=0, available=4, revision=1, roe=.10),
              dict(period=0, available=12, revision=2, roe=.15)]
    # Split 2-for-1: no wealth change at the theoretical ex-event price.
    old_price, new_price, shares = 100, 50, 100
    # Cash dividend: no tax, no other price movement, cash credited for teaching.
    cash_dividend = 1
    # Order handling: a sealed board has no opposing liquidity in this example.
    buy_blocked = dict(requested=100, opposing_shares=0, filled=0,
                       reason="NO_OPPOSING_LIQUIDITY")
    # Artificial fee schedule, not current exchange or broker tariff.
    buy_value, sell_value = 1000, 1010
    commission = lambda value: max(5, value*.0003)
    other_rate, sell_tax = .00001, .0005
    fees = commission(buy_value)+commission(sell_value)
    fees += (buy_value+sell_value)*other_rate + sell_value*sell_tax
    return dict(pit=dict(correct=financial_asof(events, 8)["roe"], wrong_latest=events[-1]["roe"]),
                split=dict(raw_return=new_price/old_price-1,
                           adjusted_return=(2*new_price)/old_price-1,
                           before=old_price*shares, after=new_price*shares*2),
                dividend=dict(raw_return=9/10-1, total_return=(9+cash_dividend)/10-1,
                              stock_value=9*shares, cash=cash_dividend*shares),
                blocked_buy=buy_blocked,
                fee_example=dict(gross_pnl=sell_value-buy_value, fees=fees,
                                 net_pnl=sell_value-buy_value-fees))


def summarize(weeks):
    valid_ic = [w["rank_ic"] for w in weeks if w["rank_ic"] is not None]
    diffs = [w["gross_difference"] for w in weeks if w["gross_difference"] is not None]
    return dict(periods=len(weeks), defined_ic=len(valid_ic),
                mean_ic=mean(valid_ic) if valid_ic else None,
                complete_gross_periods=len(diffs),
                mean_gross_difference=mean(diffs) if diffs else None)


def report():
    panel = make_panel()
    weeks = [observe_week(panel, t) for t in SIGNALS]
    return dict(study_id="rev20-classroom-v1", source_kind=SOURCE, seed=SEED,
                securities=STOCKS, industries=5, synthetic_sessions=SESSIONS,
                initial_reference_cash=1_000_000, top_n=TOP,
                data_sha256=hashlib.sha256(json.dumps(panel, sort_keys=True).encode()).hexdigest(),
                blocks=dict(development=summarize(weeks[:12]), validation=summarize(weeks[12:18]),
                            demonstration_holdout=summarize(weeks[18:])),
                trainable_at_first_validation=trainable(weeks[:12], weeks[12]["signal"]),
                weeks=weeks, pitfalls=pitfalls(),
                boundaries=["Synthetic sessions and prices; no real market calendar.",
                            "Observed-price gross comparison only; no order or portfolio ledger.",
                            "Missing labels retained; IC computed on comparable pairs.",
                            "Published holdout is a demonstration, not independent market OOS."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = report()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        print(result["study_id"], result["source_kind"])
        print("40 synthetic securities; 24 signal periods; gross observations only.")
        for name, block in result["blocks"].items():
            print(name, json.dumps(block, ensure_ascii=False))
        print("First validation: eligible prior signal sessions:", result["trainable_at_first_validation"])
        print("Pitfall examples:", json.dumps(result["pitfalls"], ensure_ascii=False))
        print("Not a market backtest or trading recommendation.")


if __name__ == "__main__":
    main()
