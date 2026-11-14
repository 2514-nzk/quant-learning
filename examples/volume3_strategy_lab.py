#!/usr/bin/env python3
"""Third-volume strategy methods on the textbook's own SYNTHETIC_ONLY fixture.

NO real equity quotes, historical Shenwan classifications, live exchange calendar,
investment recommendation, execution fills, or real-market OOS evidence.
Python standard library only; requires no local research database.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "teaching" / "volume3_weekly_v1.json"
DATASET_ID = "volume3-weekly-synthetic-v1"


def moment(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("All market/feature/label times must include UTC offset")
    return result


def load_fixture(path: Path = DATA) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_fixture(payload)
    return payload


def validate_fixture(payload: dict) -> None:
    if payload.get("dataset_id") != DATASET_ID or payload.get("evidence_grade") != "SYNTHETIC_ONLY":
        raise ValueError("The lab accepts only the declared textbook synthetic dataset")
    weeks = payload.get("weeks", [])
    if len(weeks) != 16 or payload.get("development_weeks") != 8:
        raise ValueError("Expected exactly 16 weeks with first 8 in development")
    if payload.get("transaction_cost_per_turnover_unit", -1) < 0:
        raise ValueError("Invalid hypothetical turnover fee")
    previous = None
    for k, week in enumerate(weeks):
        if week["week_no"] != k + 1:
            raise ValueError("Missing or duplicate synthetic week number")
        s = moment(week["signal_at"])
        cutoff = moment(week["feature_cutoff_at"])
        d = moment(week["decision_at"])
        entry = moment(week["entry_at"])
        exit_at = moment(week["exit_at"])
        available = moment(week["label_available_at"])
        if not (cutoff <= s <= d < entry < exit_at <= available):
            raise ValueError("Violation of event/label timing contract")
        if previous is not None and s <= previous:
            raise ValueError("Signals are not strictly ordered")
        previous = s
        if moment(week["market"]["known_at"]) > cutoff:
            raise ValueError("Market regime features were not available")
        version = "TEACH_OLD" if k < 8 else "TEACH_NEW"
        prefix = "O_" if k < 8 else "N_"
        if week["taxonomy_version"] != version:
            raise ValueError("Artificial industry taxonomy version mismatch")
        industry_codes = [i["industry_code"] for i in week["industries"]]
        if len(industry_codes) != 4 or len(set(industry_codes)) != 4:
            raise ValueError("Exactly four distinct industries are required")
        if any(not c.startswith(prefix) for c in industry_codes):
            raise ValueError("Old/new industry taxonomy codes cannot be mixed")
        for item in week["industries"]:
            if item["taxonomy_version"] != version or moment(item["feature_known_at"]) > cutoff:
                raise ValueError("Industry feature from the future or wrong taxonomy")
            if not all(math.isfinite(item[key]) for key in ("strength_score", "following_period_return")):
                raise ValueError("Non-finite industry value")
        stocks = week["stocks"]
        ids = [x["security_id"] for x in stocks]
        if len(stocks) != 8 or len(set(ids)) != 8:
            raise ValueError("Exactly eight stable, distinct mock stocks are required")
        for stock in stocks:
            moment(stock["membership_known_at"])
            if stock["industry_code"] not in industry_codes:
                raise ValueError("Security references an unknown industry version")
            if not all(math.isfinite(stock[key]) for key in
                       ("price_t", "price_reference_momentum", "price_reference_reversal",
                        "following_period_return")):
                raise ValueError("Non-finite stock data")
            if min(stock["price_t"], stock["price_reference_momentum"],
                   stock["price_reference_reversal"]) <= 0:
                raise ValueError("Prices must be positive")


def regime(week: dict) -> str:
    """Pre-registered classroom rule; NO use of future returns."""
    if moment(week["market"]["known_at"]) > moment(week["feature_cutoff_at"]):
        raise ValueError("Future market data")
    m = week["market"]
    return ("RISK_ON" if m["trend_score"] > 0 and
            m["breadth"] >= 0.5 and m["risk_score"] < 0.5
            else "RISK_OFF")


def ranked_industries(week: dict) -> list[str]:
    cutoff = moment(week["feature_cutoff_at"])
    if any(moment(i["feature_known_at"]) > cutoff for i in week["industries"]):
        raise ValueError("A future industry feature reached the ranking")
    return [i["industry_code"] for i in sorted(
        week["industries"], key=lambda v: (-v["strength_score"], v["industry_code"]))]


def asof_members(week: dict) -> list[dict]:
    """A late membership record is UNKNOWN, not a verified ineligible stock."""
    cutoff = moment(week["feature_cutoff_at"])
    return [v for v in week["stocks"]
            if moment(v["membership_known_at"]) <= cutoff]


def score_reversal(stock: dict) -> float:
    """Reverse past declared-window raw price change; it is NOT a realized return label."""
    return -(stock["price_t"] / stock["price_reference_reversal"] - 1.0)


def score_momentum(stock: dict) -> float:
    return stock["price_t"] / stock["price_reference_momentum"] - 1.0


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    result = [0.0] * len(values)
    start = 0
    while start < len(values):
        stop = start + 1
        while stop < len(values) and values[order[stop]] == values[order[start]]:
            stop += 1
        midrank = (start + 1 + stop) / 2
        for offset in range(start, stop):
            result[order[offset]] = midrank
        start = stop
    return result


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 3:
        return None
    a, b = ranks(x), ranks(y)
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    cov = sum((u - mean_a) * (v - mean_b) for u, v in zip(a, b))
    aa = sum((u - mean_a) ** 2 for u in a)
    bb = sum((v - mean_b) ** 2 for v in b)
    if aa <= 0 or bb <= 0:
        return None
    return cov / math.sqrt(aa * bb)


def eligible_training_weeks(weeks: list[dict], current_week: dict) -> list[int]:
    """Purge by actual label availability, never by arbitrary row count."""
    signal = moment(current_week["signal_at"])
    return [w["week_no"] for w in weeks
            if moment(w["signal_at"]) < signal and
            moment(w["label_available_at"]) < signal]


def target_weights(week: dict, strategy: str) -> dict[str, float]:
    selected = ranked_industries(week)
    if strategy == "always_top":
        return {selected[0]: 1.0}
    if strategy == "regime_gated_top":
        return {selected[0]: 1.0} if regime(week) == "RISK_ON" else {}
    if strategy == "equal_four":
        return {code: .25 for code in selected}
    if strategy == "cash":
        return {}
    raise ValueError("Unknown, unregistered classroom strategy")


def turnover_l1(previous: dict[str, float], current: dict[str, float]) -> float:
    return sum(abs(current.get(k, 0.0) - previous.get(k, 0.0))
               for k in set(previous) | set(current))


def run_strategy(weeks: list[dict], strategy: str, fee_per_turnover: float) -> list[dict]:
    if fee_per_turnover < 0:
        raise ValueError("Negative artificial fee")
    previous = {}
    output = []
    for w in weeks:
        weights = target_weights(w, strategy)
        if any(v < 0 for v in weights.values()) or sum(weights.values()) > 1.0000001:
            raise AssertionError("Invalid target weights")
        # The next-period return is used ONLY in the hindsight evaluation, not selection.
        return_by_industry = {v["industry_code"]: v["following_period_return"]
                              for v in w["industries"]}
        gross = sum(weight * return_by_industry[code]
                    for code, weight in weights.items())
        turnover = turnover_l1(previous, weights)
        proxy_fee = fee_per_turnover * turnover
        output.append({
            "week_no": w["week_no"], "taxonomy": w["taxonomy_version"],
            "regime": regime(w), "chosen": sorted(weights),
            "gross_observation": round(gross, 10),
            "turnover_l1_proxy": round(turnover, 6),
            "synthetic_cost_proxy": round(proxy_fee, 10),
            "synthetic_net_observation": round(gross - proxy_fee, 10),
            "member_unknown_count": len(w["stocks"]) - len(asof_members(w)),
        })
        previous = weights
    return output


def reversal_diagnostic(weeks: list[dict]) -> dict:
    strong, weak, overall = [], [], []
    for w in weeks:
        top2 = set(ranked_industries(w)[:2])
        stocks = asof_members(w)
        for bucket, group in ((strong, [v for v in stocks if v["industry_code"] in top2]),
                              (weak, [v for v in stocks if v["industry_code"] not in top2]),
                              (overall, stocks)):
            ic = spearman([score_reversal(x) for x in group],
                          [x["following_period_return"] for x in group])
            if ic is not None:
                bucket.append(ic)
    return {
        "factor": "reversal score_RAW_UNADJUSTED_SYNTHETIC_ONLY",
        "strong_industry_mean_rankic": round(sum(strong) / len(strong), 6) if strong else None,
        "weak_industry_mean_rankic": round(sum(weak) / len(weak), 6) if weak else None,
        "all_stocks_mean_rankic": round(sum(overall) / len(overall), 6) if overall else None,
        "strong_valid_periods": len(strong), "weak_valid_periods": len(weak),
        "warning": "These are invented labels and preselected conditions, NOT A-share effects",
    }


def summarize(rows: list[dict], split: int) -> dict:
    def avg(items, field):
        return round(sum(x[field] for x in items) / len(items), 8)
    dev, later = rows[:split], rows[split:]
    return {
        "development": {"n": len(dev),
                        "mean_synthetic_gross": avg(dev, "gross_observation"),
                        "mean_synthetic_net_proxy": avg(dev, "synthetic_net_observation")},
        "later_artificial": {"n": len(later),
                             "mean_synthetic_gross": avg(later, "gross_observation"),
                             "mean_synthetic_net_proxy": avg(later, "synthetic_net_observation")},
        "all": {"n": len(rows),
                "mean_synthetic_gross": avg(rows, "gross_observation"),
                "mean_synthetic_net_proxy": avg(rows, "synthetic_net_observation")},
    }


def evaluate(payload: dict) -> dict:
    validate_fixture(payload)
    weeks = payload["weeks"]
    strategies = ("always_top", "regime_gated_top", "equal_four", "cash")
    fee = payload["transaction_cost_per_turnover_unit"]
    return {
        "dataset_id": DATASET_ID,
        "source_kind": "SYNTHETIC_ONLY",
        "market_pit_proven": False,
        "real_market_OOS_proven": False,
        "execution_proven": False,
        "weeks": len(weeks),
        "artificial_development_weeks": payload["development_weeks"],
        "taxonomies": sorted({w["taxonomy_version"] for w in weeks}),
        "unknown_members": sum(len(w["stocks"]) - len(asof_members(w)) for w in weeks),
        "market_regime_counts": {r: sum(regime(w) == r for w in weeks)
                                 for r in ("RISK_ON", "RISK_OFF")},
        "eligible_training_week_ids_at_week_3":
            eligible_training_weeks(weeks, weeks[2]),
        "strategies": {s: {
            "summary": summarize(run_strategy(weeks, s, fee), payload["development_weeks"]),
            "periods": run_strategy(weeks, s, fee),
        } for s in strategies},
        "reversal_diagnostic": reversal_diagnostic(weeks),
        "limitations": [
            "Invented stock prices, industry returns, membership timestamps and market state",
            "Synthetic old/new industry taxonomy is not historical SW2014/SW2021",
            "Artificial Friday/Monday dates ignore real exchange holiday calendars",
            "Subsequent returns are observational labels, not actual fills",
            "L1 target-weight difference is a turnover/cost proxy, not a trade ledger",
            "Artificial later eight weeks are not independent real-market OOS",
            "No statistical confirmation, trade queue, corporate actions or borrow constraints",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--input", type=Path, default=DATA,
                        help="Optional own teaching fixture; must match declared synthetic ID")
    args = parser.parse_args()
    report = evaluate(load_fixture(args.input))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Volume III 01–04 | SYNTHETIC_ONLY | 16 artificial weeks")
        print("Real-market PIT/OOS/execution: NOT PROVEN")
        for name, item in report["strategies"].items():
            print(name, item["summary"])


if __name__ == "__main__":
    main()
