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


# Stage 2: the same panel, now with diagnostics, models and an account.
# Fixed candidates and settings are classroom choices, not optimized parameters.
CANDIDATES = ("rev20", "blend", "ridge")
FEATURES = ("rev20", "mom5", "liquidity")
RIDGE_LAMBDA = 1.0


def zscore(values):
    m = mean(values)
    sd = math.sqrt(mean([(v-m)**2 for v in values]))
    return [(v-m)/sd if sd else 0.0 for v in values]


def feature_snapshot(panel, t):
    scores, _ = signal_snapshot(panel, t)
    codes = sorted(scores)
    if not codes:
        return {}
    columns = [
        [scores[k] for k in codes],
        [panel[k]["close"][t]/panel[k]["close"][t-5]-1 for k in codes],
        [math.log(mean(panel[k]["amount"][t-4:t+1])) for k in codes],
    ]
    return dict(zip(codes, zip(*(zscore(c) for c in columns))))


def factor_diagnostics(panel, weeks):
    out = []
    for w in weeks:
        t = w["signal"]
        f = feature_snapshot(panel, t)
        codes = sorted(w["labels"])
        ic = {name: spearman([f[k][j] for k in codes], [w["labels"][k] for k in codes])
              for j, name in enumerate(FEATURES)}
        groups = {}
        for k, v in f.items():
            groups.setdefault(panel[k]["industry"], []).append(v[0])
        residual = {k: v[0]-mean(groups[panel[k]["industry"]]) for k, v in f.items()}
        ic["industry_demeaned_rev20"] = spearman([residual[k] for k in codes],
                                                [w["labels"][k] for k in codes])
        ordered = sorted(f, key=lambda k: (f[k][0], k))
        bins = [ordered[i*len(ordered)//4:(i+1)*len(ordered)//4] for i in range(4)]
        group_returns = [mean(w["labels"][k] for k in b)
                         if b and all(k in w["labels"] for k in b) else None for b in bins]
        out.append(dict(signal=t, ic=ic, quartiles=group_returns,
                        factor_correlation=spearman([v[0] for v in f.values()],
                                                    [v[1] for v in f.values()]),
                        eligible=len(f), comparable=len(codes)))
    return out


def ridge_fit(rows):
    """Centered response and features; intercept unpenalized. Tiny Gaussian solver."""
    n = len(rows)
    if not n:
        raise ValueError("no training rows")
    p = len(FEATURES)
    xm = [mean(x[j] for x, _ in rows) for j in range(p)]
    ym = mean(y for _, y in rows)
    centered = [([x[j]-xm[j] for j in range(p)], y-ym) for x, y in rows]
    # Mean squared error + lambda * sum of squared slopes.
    a = [[mean(x[i]*x[j] for x, _ in centered) + (RIDGE_LAMBDA if i == j else 0)
          for j in range(p)] + [mean(x[i]*y for x, y in centered)] for i in range(p)]
    for i in range(p):
        pivot = max(range(i, p), key=lambda j: abs(a[j][i]))
        a[i], a[pivot] = a[pivot], a[i]
        scale = a[i][i]
        if abs(scale) < 1e-12:
            raise ValueError("singular ridge system")
        a[i] = [v/scale for v in a[i]]
        for j in range(p):
            if j != i:
                scale = a[j][i]
                a[j] = [v-scale*u for v, u in zip(a[j], a[i])]
    beta = [a[i][-1] for i in range(p)]
    return ym-sum(b*m for b, m in zip(beta, xm)), beta


def predict_candidates(panel, weeks, t):
    f = feature_snapshot(panel, t)
    prior = [w for w in weeks if w["signal"] < t and w["label_available"] < t]
    rows = []
    for w in prior:
        historical = feature_snapshot(panel, w["signal"])
        rows.extend((historical[k], y) for k, y in sorted(w["labels"].items()))
    intercept, beta = ridge_fit(rows)
    scores = {
        "rev20": {k: x[0] for k, x in f.items()},
        # fixed equal blend, no target-dependent choice of direction
        "blend": {k: (x[0]+x[1])/2 for k, x in f.items()},
        "ridge": {k: intercept+sum(b*v for b, v in zip(beta, x)) for k, x in f.items()},
    }
    return dict(signal=t, trained_signals=[w["signal"] for w in prior],
                training_rows=len(rows), intercept=intercept, beta=beta, scores=scores)


def evaluate_prediction(prediction, week):
    codes = sorted(week["labels"])
    result = {}
    for name, scores in prediction["scores"].items():
        ic = spearman([scores[k] for k in codes], [week["labels"][k] for k in codes])
        top = sorted(scores, key=lambda k: (-scores[k], k))[:TOP]
        result[name] = dict(rank_ic=ic, top=top,
                            top_gross=mean(week["labels"][k] for k in top)
                            if not week["missing_labels"] and len(top) == TOP else None)
    return result


def model_experiment(panel, weeks):
    # Validation labels must also have arrived before the first holdout decision.
    freeze_at = weeks[18]["signal"]
    validation = []
    for w in weeks[12:18]:
        p = predict_candidates(panel, weeks, w["signal"])
        validation.append(dict(prediction=p, evaluation=evaluate_prediction(p, w),
                               selection_eligible=w["label_available"] < freeze_at))
    selection = {}
    for name in CANDIDATES:
        vals = [v["evaluation"][name]["rank_ic"] for v in validation
                if v["selection_eligible"] and v["evaluation"][name]["rank_ic"] is not None]
        selection[name] = mean(vals) if vals else None
    valid = [k for k in CANDIDATES if selection[k] is not None]
    winner = max(valid, key=lambda k: selection[k]) if valid else "rev20"
    holdout = []
    for w in weeks[18:]:
        p = predict_candidates(panel, weeks, w["signal"])
        holdout.append(dict(prediction=p, evaluation=evaluate_prediction(p, w)))
    return dict(freeze_at=freeze_at, validation=validation,
                validation_mean_ic=selection, selected=winner, holdout=holdout)


def fees(notional, side):
    if not notional:
        return 0.0
    return max(5, .0003*notional)+.00001*notional+(.0005*notional if side == "SELL" else 0)


def blocked_side(code, day):
    """Deterministic stress cases at execution, not inferred from real OHLC."""
    if (int(code[1:])+day) % 29 == 0:
        return "BOTH"
    if (int(code[1:])+day) % 13 == 0:
        return "BUY"
    if (int(code[1:])+day) % 17 == 0:
        return "SELL"
    return None


def simulate_account(panel, targets, cost=True, stress=True, participation=.05):
    """Long-only weekly orders, close-based quantity, next-session execution.
    The fixed holdout starts after the synthetic delisting event. If a held
    security exits the listing interval, stop rather than invent a liquidation.
    """
    if not targets:
        raise ValueError("no target dates")
    if not 0 < participation <= 1:
        raise ValueError("invalid participation")
    cash = 1_000_000.0
    holdings = {}
    orders, daily = [], []
    start, end = min(targets), max(targets)+6
    if start < 4 or end >= SESSIONS:
        raise ValueError("target dates outside classroom execution horizon")
    pending = None
    lot = 100
    for day in range(start, end+1):
        for k in holdings:
            if not panel[k]["listed"] <= day < panel[k]["delisted"]:
                raise ValueError("held security exited; explicit recovery data required")
        if pending is not None:
            decision, desired = pending
            # Only sell shares held before today's buy orders.
            for side in ("SELL", "BUY"):
                for k in sorted(set(holdings)|set(desired)):
                    old = holdings.get(k, 0)
                    diff = desired.get(k, 0)-old
                    requested = -diff if side == "SELL" else diff
                    if requested <= 0:
                        continue
                    row = panel[k]
                    if not row["listed"] <= day < row["delisted"]:
                        orders.append(dict(decision=decision, day=day, code=k, side=side,
                                           requested=requested, filled=0, price=None, reference=None,
                                           notional=0, fee=0, slippage=0,
                                           reason="OUTSIDE_LISTING", cash_after=cash))
                        continue
                    ref = row["open"][day]
                    # Fixed illustrative adverse slippage; no real queue calibration.
                    px = ref*(1+(.0008 if side == "BUY" else -.0008)) if cost else ref
                    # At decision: trailing turnover proxy, not the execution day's volume.
                    cap = int(participation*mean(row["amount"][decision-4:decision+1])/px/lot)*lot
                    fill = min(requested, cap) if stress else requested
                    reason = "PARTICIPATION_CAP" if fill < requested else "FILLED"
                    if stress and blocked_side(k, day) in (side, "BOTH"):
                        fill, reason = 0, "SYNTHETIC_BLOCK"
                    if side == "BUY":
                        while fill and fill*px+(fees(fill*px, side) if cost else 0)>cash+1e-8:
                            fill -= lot
                            reason = "CASH_LIMIT"
                    amount = fill*px
                    fee = fees(amount, side) if cost else 0
                    slip = fill*abs(px-ref)
                    if side == "SELL":
                        cash += amount-fee
                        new = old-fill
                    else:
                        cash -= amount+fee
                        new = old+fill
                    if new:
                        holdings[k] = new
                    else:
                        holdings.pop(k, None)
                    orders.append(dict(decision=decision, day=day, code=k, side=side,
                                       requested=requested, filled=fill, price=px, reference=ref,
                                       notional=amount, fee=fee, slippage=slip, reason=reason,
                                       cash_after=cash))
            pending = None
        nav = cash+sum(q*panel[k]["close"][day] for k,q in holdings.items())
        if cash < -1e-6:
            raise AssertionError("negative cash")
        daily.append(dict(day=day, cash=cash, holdings=dict(holdings), nav=nav))
        if day in targets:
            weights = targets[day]
            if any(w < 0 for w in weights.values()) or sum(weights.values()) > 1+1e-8:
                raise ValueError("invalid long-only weights")
            eligible, _ = signal_snapshot(panel, day)
            if not set(weights).issubset(eligible):
                raise ValueError("target includes ineligible security")
            desired = {k: int(nav*w/panel[k]["close"][day]/lot)*lot for k,w in weights.items()}
            pending = day, desired
    navs = [d["nav"] for d in daily]
    peak = navs[0]
    drawdown = 0.0
    for nav in navs:
        peak = max(peak, nav)
        drawdown = min(drawdown, nav/peak-1)
    return dict(targets=targets, daily=daily, orders=orders, final_nav=navs[-1],
                total_return=navs[-1]/navs[0]-1, max_drawdown=drawdown,
                fees=sum(o["fee"] for o in orders), slippage=sum(o["slippage"] for o in orders),
                traded_notional=sum(o["notional"] for o in orders),
                unfilled_orders=sum(o["filled"]<o["requested"] for o in orders))


def account_experiment(panel, weeks, models):
    rev, selected, equal = {}, {}, {}
    for w, h in zip(weeks[18:], models["holdout"]):
        t = w["signal"]
        scores = h["prediction"]["scores"]
        top = lambda name: sorted(scores[name], key=lambda k: (-scores[name][k], k))[:TOP]
        for dest, names in ((rev, top("rev20")),
                            (selected, top(models["selected"])),
                            (equal, sorted(w["scores"]))):
            # fixed 95% target investment, residual cash for fees
            dest[t] = {k: .95/len(names) for k in names} if names else {}
    return {name: {case: simulate_account(panel, targets, cost=cost, stress=stress)
                   for case, cost, stress in (("ideal", False, False), ("cost_only", True, False),
                                               ("constrained", True, True))}
            for name, targets in (("rev20", rev), ("selected", selected), ("equal", equal))}


def extended_report():
    panel = make_panel()
    weeks = [observe_week(panel, t) for t in SIGNALS]
    models = model_experiment(panel, weeks)
    accounts = account_experiment(panel, weeks, models)
    base = report()
    base.update(stage="integrated_classroom_v2", diagnostics=factor_diagnostics(panel, weeks),
                models=models, accounts=accounts)
    base["boundaries"] += [
        "Stage 2 accounts are artificial next-open execution scenarios, not real fills.",
        "No real corporate actions, suspension recovery, or delisting recovery in the holdout ledger.",
        "Ideal, cost-only and constrained differences are scenario comparisons, not causal attribution.",
        "No independent market OOS, impact calibration or validated alpha."
    ]
    return base


def concise_extended(result):
    print("SYNTHETIC_ONLY: unified REV20 research and account experiment")
    print("Validation mean IC (labels known before freeze):", result["models"]["validation_mean_ic"])
    print("Frozen choice:", result["models"]["selected"])
    for name, variants in result["accounts"].items():
        for case, account in variants.items():
            print(f"{name:8s} {case:11s} NAV={account['final_nav']:,.2f} "
                  f"return={account['total_return']:.2%} drawdown={account['max_drawdown']:.2%} "
                  f"fees={account['fees']:.2f} unfilled={account['unfilled_orders']}")
    print("No real market evidence. Use --integrated --json for audit records.")


# Stage 3: risk budgets, exact accounting attribution and diagnostic scenarios.
RISK_TARGET = .009  # synthetic daily volatility target, not a market calibration
NAME_CAP = .15
INDUSTRY_CAP = .30


def risk_weights(panel, t, scores, exposure=0.95):
    """Long-only inverse-volatility weights with caps and covariance scaling.
    Unallocated weight remains cash. No claim of mean-variance optimality.
    """
    names = sorted(scores, key=lambda k: (-scores[k], k))[:TOP]
    returns = {k: [panel[k]["close"][d]/panel[k]["close"][d-1]-1
                   for d in range(t-19, t+1)] for k in names}
    vol = {k: math.sqrt(mean((x-mean(v))**2 for x in v)) for k,v in returns.items()}
    inv = {k: 1/max(vol[k], .001) for k in names}
    total = sum(inv.values())
    raw = {k: min(NAME_CAP, exposure*inv[k]/total) for k in names} if total else {}
    for g in range(5):
        group = [k for k in raw if panel[k]["industry"] == g]
        weight = sum(raw[k] for k in group)
        if weight > INDUSTRY_CAP:
            for k in group:
                raw[k] *= INDUSTRY_CAP/weight
    # Portfolio series includes cash at zero return, and all cross-covariances.
    series = [sum(raw[k]*returns[k][i] for k in raw) for i in range(20)]
    sd = math.sqrt(mean((v-mean(series))**2 for v in series))
    scale = min(1., RISK_TARGET/sd) if sd else 1.
    weights = {k: v*scale for k,v in raw.items()}
    return dict(weights=weights, historical_vol=sd, scaled_vol=sd*scale,
                stock_vol=vol, scale=scale, exposure=sum(weights.values()),
                cash_weight=1-sum(weights.values()))


def monitor_at(weeks, t):
    past = [w for w in weeks if w["label_available"] < t][-6:]
    values = [w["rank_ic"] for w in past if w["rank_ic"] is not None]
    coverage = sum(len(w["labels"]) for w in past)/sum(w["eligible"] for w in past) if past else None
    if len(values) < 6 or coverage is None or coverage < .9:
        state, scale = "INSUFFICIENT", .5
    elif mean(values) < 0:
        state, scale = "REVIEW", .5
    else:
        state, scale = "NORMAL", 1.
    return dict(signal=t, known_signals=[w["signal"] for w in past],
                mean_ic=mean(values) if values else None, coverage=coverage,
                state=state, scale=scale)


def decay_diagnostics(panel, weeks):
    """Fixed 1/5/10-session holding horizons, identical dates and stock pairs."""
    horizons = (1,5,10)
    results = []
    for w in weeks:
        t = w["signal"]
        entry = t+1
        if entry+max(horizons) >= SESSIONS:
            continue
        codes = sorted(k for k in w["scores"] if entry+max(horizons) < panel[k]["delisted"])
        score = [w["scores"][k] for k in codes]
        ic = {h: spearman(score, [panel[k]["open"][entry+h]/panel[k]["open"][entry]-1
                                 for k in codes]) for h in horizons}
        results.append(dict(signal=t, comparable=len(codes), ic=ic))
    # If a horizon's IC is undefined, exclude that date from all averages.
    paired = [r for r in results if all(v is not None for v in r["ic"].values())]
    return dict(periods=len(paired), rows=results,
                mean_ic={h: mean(r["ic"][h] for r in paired) if paired else None for h in horizons})


def overlap_diagnostics(panel, weeks):
    result = []
    last = None
    for w in weeks:
        f = feature_snapshot(panel, w["signal"])
        first = set(sorted(f, key=lambda k:(-f[k][0], k))[:TOP])
        second = set(sorted(f, key=lambda k:(-f[k][1], k))[:TOP])
        result.append(dict(signal=w["signal"],
                           rev_mom_jaccard=len(first&second)/len(first|second) if first|second else None,
                           membership_change=len(first-last)/len(first) if last is not None and first else None))
        last = first
    return result


def account_attribution(panel, account):
    """Exact additive dollar attribution across overnight and intraday legs.
    Market and industry are equal-weight synthetic reference baskets, not betas
    estimated by regression. All held and reference securities must have prices.
    """
    rows = []
    orders = {}
    for o in account["orders"]:
        orders.setdefault(o["day"], []).append(o)
    for prev, now in zip(account["daily"], account["daily"][1:]):
        day = now["day"]
        market = industry = selection = 0.
        # Known prior-close research universe, fixed for both legs of the day.
        ref_codes = sorted(signal_snapshot(panel, day-1)[0])
        # Held names may have left signal eligibility; retain them in their P&L.
        for holdings, start_field, start_day, end_field, end_day in (
            (prev["holdings"], "close", day-1, "open", day),
            (now["holdings"], "open", day, "close", day),
        ):
            if not ref_codes:
                raise ValueError("no reference universe")
            def ret(k):
                return panel[k][end_field][end_day]/panel[k][start_field][start_day]-1
            if any(not panel[k]["listed"] <= start_day <= end_day < panel[k]["delisted"] for k in ref_codes):
                raise ValueError("reference price missing; attribution requires exit data")
            m = mean(ret(k) for k in ref_codes)
            group = {g: [ret(k) for k in ref_codes if panel[k]["industry"] == g] for g in range(5)}
            for k,q in holdings.items():
                value = q*panel[k][start_field][start_day]
                peers = group[panel[k]["industry"]]
                if not peers:
                    raise ValueError("missing industry reference")
                g = mean(peers)
                market += value*m
                industry += value*(g-m)
                selection += value*(ret(k)-g)
        fee = -sum(o["fee"] for o in orders.get(day, []))
        slip = -sum(o["slippage"] for o in orders.get(day, []))
        actual = now["nav"]-prev["nav"]
        residual = actual-market-industry-selection-fee-slip
        rows.append(dict(day=day, market=market, industry=industry, selection=selection,
                         fees=fee, slippage=slip, actual=actual, residual=residual))
    keys = ("market","industry","selection","fees","slippage","actual","residual")
    return dict(daily=rows, totals={k:sum(r[k] for r in rows) for k in keys})


def risk_report():
    panel = make_panel()
    base = extended_report()
    weeks, models = base["weeks"], base["models"]
    risk, monitored, decisions = {}, {}, []
    for w,h in zip(weeks[18:],models["holdout"]):
        t = w["signal"]
        scores = h["prediction"]["scores"][models["selected"]]
        m = monitor_at(weeks,t)
        fixed = risk_weights(panel,t,scores)
        gated = risk_weights(panel,t,scores,exposure=.95*m["scale"])
        risk[t], monitored[t] = fixed["weights"], gated["weights"]
        decisions.append(dict(signal=t,risk=fixed,monitored=gated,monitor=m))
    accounts = {
        "fixed":base["accounts"]["selected"]["constrained"],
        "risk":simulate_account(panel,risk),
        "monitored":simulate_account(panel,monitored),
    }
    attribution = {k:account_attribution(panel,a) for k,a in accounts.items()}
    capacity = {p:simulate_account(panel,risk,participation=p) for p in (.01,.05,.10)}
    actual_exposure = {}
    for name,a in accounts.items():
        exposures = []
        for d in a["daily"]:
            w = {k:q*panel[k]["close"][d["day"]]/d["nav"] for k,q in d["holdings"].items()}
            groups = {g:sum(v for k,v in w.items() if panel[k]["industry"]==g) for g in range(5)}
            exposures.append(dict(day=d["day"],stock=sum(w.values()),cash=d["cash"]/d["nav"],
                                  max_name=max(w.values(),default=0.),max_industry=max(groups.values())))
        actual_exposure[name]=exposures
    return dict(stage="risk_classroom_v3",source_kind=SOURCE, data_sha256=base["data_sha256"],
                model=models["selected"], decisions=decisions, accounts=accounts,
                attribution=attribution, capacity=capacity, exposures=actual_exposure,
                decay=decay_diagnostics(panel,weeks), overlap=overlap_diagnostics(panel,weeks),
                factor_ic=[dict(signal=w["signal"],ic=w["rank_ic"],available=w["label_available"]) for w in weeks],
                boundaries=["All results are synthetic and published classroom examples.",
                            "Target caps are not guaranteed actual holdings caps.",
                            "Market/industry/selection is an exact dollar reference decomposition, not regression alpha/beta.",
                            "Overlap and membership change are proxies, not actual crowding or turnover.",
                            "Capacity scenarios vary an artificial trailing liquidity cap, not market capacity.",
                            "Monitor uses REV20 IC as a reference, not a validated selected-model shutdown rule."])


def dashboard_data(r):
    """Small browser payload; full audit remains available in JSON mode."""
    return dict(source_kind=r["source_kind"],model=r["model"],
                nav={k:[dict(day=d["day"],value=d["nav"]) for d in a["daily"]] for k,a in r["accounts"].items()},
                summary={k:{x:a[x] for x in ("final_nav","total_return","max_drawdown","fees","slippage","unfilled_orders")} for k,a in r["accounts"].items()},
                attribution={k:a["totals"] for k,a in r["attribution"].items()},
                exposure=r["exposures"],factor_ic=r["factor_ic"],decisions=r["decisions"],
                decay=r["decay"]["mean_ic"],decay_periods=r["decay"]["periods"],
                capacity=[dict(rate=p,nav=a["final_nav"],unfilled=a["unfilled_orders"],
                               traded=a["traded_notional"]) for p,a in r["capacity"].items()])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--integrated", action="store_true")
    parser.add_argument("--risk", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()
    if args.risk or args.dashboard:
        result = risk_report()
        if args.dashboard or args.json:
            print(json.dumps(dashboard_data(result) if args.dashboard else result, ensure_ascii=False, allow_nan=False))
        else:
            print("SYNTHETIC_ONLY - risk and attribution experiment")
            print(json.dumps(dashboard_data(result)["summary"], ensure_ascii=False, indent=2))
            print("Dollar attribution:", json.dumps(dashboard_data(result)["attribution"], ensure_ascii=False))
            print("Use --risk --json for complete audit.")
        return
    result = extended_report() if args.integrated else report()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    elif args.integrated:
        concise_extended(result)
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
