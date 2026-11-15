#!/usr/bin/env python3
"""Synthetic, standard-library lab for volume 2 chapters 06–08.

Demonstrates forward-only event-time purge, cross-sectional factor processing,
industry/size neutralization, RankIC, quartiles, HAC and block bootstrap.
Every observation and return is GENERATED; nothing measures A-share alpha.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, stdev


def moment(value: str) -> datetime:
    """Require timezone-aware ISO timestamps; compare absolute instants."""
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string with timezone")
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO timestamp: {value!r}") from exc
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("timezone offset is mandatory")
    return ts.astimezone(timezone.utc)


def stamp(ts: datetime) -> str:
    return ts.isoformat(timespec="minutes")


def make_synthetic_panel(periods: int = 12, stocks: int = 12) -> list[dict]:
    """Create deliberate *non-market* observations on a weekly calendar."""
    if periods < 6 or stocks < 8 or stocks % 4 != 0 or stocks % 3 != 0:
        raise ValueError("periods >=6; stocks must be divisible by 12")
    tz = timezone(timedelta(hours=8))
    first = datetime(2024, 1, 5, 15, tzinfo=tz)
    result = []
    for t in range(periods):
        signal = first + timedelta(days=7 * t)
        entry = (signal + timedelta(days=3)).replace(hour=9, minute=30)
        label_end = (signal + timedelta(days=7)).replace(hour=9, minute=30)
        label_available = label_end + timedelta(hours=1)
        for j in range(stocks):
            industry = ("I1", "I2", "I3")[j % 3]
            log_size = 10 + 0.19 * (j // 3) + 0.08 * (j % 3) + 0.015 * t
            base = math.sin((j + 2) * (t + 1) * 0.61)
            factor = 0.85 * base + 0.30 * (j % 3 - 1) + 0.11 * log_size
            # Artificial returns intentionally combine signal/noise/industry.
            sign = 1 if t % 4 != 3 else -1
            future_return = (
                sign * 0.008 * base
                + 0.011 * math.cos((j + 1) * (t + 3) * 0.47)
                + 0.004 * (j % 3 - 1)
            )
            result.append({
                "code": f"S{j + 1:02d}",
                "industry": industry,
                "signal_at": stamp(signal),
                "feature_available_at": stamp(signal - timedelta(minutes=5)),
                "decision_at": stamp(signal + timedelta(hours=3)),
                "entry_at": stamp(entry),
                "label_end_at": stamp(label_end),
                "label_available_at": stamp(label_available),
                "factor_raw": factor,
                "log_mcap": log_size,
                "future_return": future_return,
            })
    return result


def validate_panel(rows: list[dict]) -> None:
    if not rows:
        raise ValueError("empty panel")
    seen = set()
    for row in rows:
        key = (row["signal_at"], row["code"])
        if key in seen:
            raise ValueError(f"duplicate signal/code: {key}")
        seen.add(key)
        for k in ("factor_raw", "log_mcap", "future_return"):
            v = row[k]
            if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v):
                raise ValueError(f"non-finite/non-numeric {k} for {key}")
        if not row["industry"] or not row["code"]:
            raise ValueError("missing industry/code")
        info = moment(row["feature_available_at"])
        signal = moment(row["signal_at"])
        decision = moment(row["decision_at"])
        entry = moment(row["entry_at"])
        end = moment(row["label_end_at"])
        ready = moment(row["label_available_at"])
        if not (info <= signal <= decision < entry <= end <= ready):
            raise ValueError(f"invalid information/label time order: {key}")


def purge_forward(
    train: list[dict], valid: list[dict], safety_gap_minutes: int = 0
) -> dict:
    """Forward-only split: retain labels *available* strictly before valid signal.

    Safety gap is an additional research-specific buffer, NOT a general
    bidirectional embargo implementation.
    """
    if not valid or not train:
        raise ValueError("both train and validation observations required")
    if not isinstance(safety_gap_minutes, int) or safety_gap_minutes < 0:
        raise ValueError("nonnegative integer safety gap required")
    validate_panel(train)
    validate_panel(valid)
    first_valid = min(moment(r["signal_at"]) for r in valid)
    kept, removed = [], []
    for row in train:
        if moment(row["signal_at"]) >= first_valid:
            raise ValueError("not a forward-only split")
        ready = moment(row["label_available_at"])
        if ready + timedelta(minutes=safety_gap_minutes) < first_valid:
            kept.append(row)
        else:
            removed.append({"signal_at": row["signal_at"], "code": row["code"],
                            "label_available_at": row["label_available_at"]})
    return {"kept": kept, "removed": removed, "valid_first_signal_at": stamp(first_valid),
            "safety_gap_minutes": safety_gap_minutes}


def quantile(values: list[float], p: float) -> float:
    if not values or not 0 <= p <= 1:
        raise ValueError("nonempty values and 0 <= p <= 1 required")
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    return ordered[lo] + (idx - lo) * (ordered[hi] - ordered[lo])


def mean_var(values: list[float]) -> tuple[float, float]:
    mu = mean(values)
    return mu, mean([(v - mu) ** 2 for v in values])


def transform_factor_day(rows: list[dict], lower: float = .10, upper: float = .90) -> list[dict]:
    """Cross-sectional, same-day quantile clip -> zscore -> industry+size OLS.

    Solves industry fixed effects + common within-industry size slope using
    Frisch-Waugh-Lovell residualization, equal-stock weights, no ridge.
    Does not access future_return; the proof is in a regression test.
    """
    if len(rows) < 8 or len({r["signal_at"] for r in rows}) != 1:
        raise ValueError("one signal date and >=8 securities required")
    if not 0 <= lower < upper <= 1:
        raise ValueError("invalid clipping quantiles")
    for row in rows:
        if not math.isfinite(row["factor_raw"]) or not math.isfinite(row["log_mcap"]):
            raise ValueError("non-finite factor/size")
        if not row["industry"]:
            raise ValueError("unknown industry: do not invent industry exposure")
    raw = [r["factor_raw"] for r in rows]
    a, b = quantile(raw, lower), quantile(raw, upper)
    clipped = [max(a, min(b, v)) for v in raw]
    mu, var = mean_var(clipped)
    if var <= 1e-24:
        raise ValueError("constant factor on this date")
    z = [(x - mu) / math.sqrt(var) for x in clipped]
    groups: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        groups[row["industry"]].append(i)
    z_within, size_within = [0.0] * len(rows), [0.0] * len(rows)
    for indices in groups.values():
        zbar = mean([z[i] for i in indices])
        sbar = mean([rows[i]["log_mcap"] for i in indices])
        for i in indices:
            z_within[i] = z[i] - zbar
            size_within[i] = rows[i]["log_mcap"] - sbar
    denom = sum(v * v for v in size_within)
    if denom <= 1e-24:
        raise ValueError("size exposure collinear with industry: cannot identify slope")
    beta = sum(x * y for x, y in zip(z_within, size_within)) / denom
    residuals = [v - beta * x for v, x in zip(z_within, size_within)]
    residual_mean, residual_var = mean_var(residuals)
    if residual_var <= 1e-24:
        raise ValueError("factor explained completely by industry and size")
    return [
        {**row, "factor_clipped": clipped[i], "factor_z": z[i],
         "factor_neutral": (residuals[i] - residual_mean) / math.sqrt(residual_var)}
        for i, row in enumerate(rows)
    ]


def ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda p: p[1])
    result = [0.0] * len(values)
    k = 0
    while k < len(values):
        j = k + 1
        while j < len(values) and indexed[k][1] == indexed[j][1]:
            j += 1
        score = (k + 1 + j) / 2
        for m in range(k, j):
            result[indexed[m][0]] = score
        k = j
    return result


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y):
        raise ValueError("unaligned vector lengths")
    if len(x) < 2:
        return None
    mx, my = mean(x), mean(y)
    xx = sum((z - mx) ** 2 for z in x)
    yy = sum((z - my) ** 2 for z in y)
    return (sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(xx * yy)
            if xx > 1e-24 and yy > 1e-24 else None)


def rank_ic(x: list[float], y: list[float]) -> float | None:
    return pearson(ranks(x), ranks(y))


def describe_day(rows: list[dict], factor_key: str = "factor_neutral") -> dict:
    if len(rows) < 8 or len(rows) % 4:
        raise ValueError("teaching quartiles require a multiple of four, >=8")
    ordered = sorted(rows, key=lambda r: (r[factor_key], r["code"]))
    n = len(rows) // 4
    groups = [ordered[q*n:(q+1)*n] for q in range(4)]
    ret = [mean([r["future_return"] for r in group]) for group in groups]
    selected = [r["code"] for r in groups[-1]]
    return {
        "signal_at": rows[0]["signal_at"], "n_stocks": len(rows),
        "rank_ic": rank_ic([r[factor_key] for r in rows],
                           [r["future_return"] for r in rows]),
        "quartile_returns": ret, "gross_q4_minus_q1": ret[3]-ret[0],
        "gross_q4": ret[3], "top_codes": sorted(selected),
        "tie_count": len(rows) - len({r[factor_key] for r in rows}),
    }


def hac_mean_se(series: list[float], lags: int = 2) -> float:
    """Bartlett Newey-West approximation of the SE of a sample mean."""
    n = len(series)
    if n < 2 or isinstance(lags, bool) or not 0 <= lags < n:
        raise ValueError("HAC: require at least 2 periods and 0<=lags<n")
    mu = mean(series)
    residual = [x - mu for x in series]
    long_run = sum(x*x for x in residual) / n
    for lag in range(1, lags + 1):
        gamma = sum(residual[t] * residual[t-lag] for t in range(lag, n)) / n
        long_run += 2 * (1 - lag / (lags + 1)) * gamma
    if long_run < -1e-12:
        raise ValueError("negative long-run variance")
    return math.sqrt(max(long_run, 0.0) / n)


def moving_block_ci(
    series: list[float], block: int = 3, reps: int = 1000,
    seed: int = 20261113, alpha: float = .05
) -> list[float]:
    """Circular moving-block percentile CI for the *mean*, fixed seed."""
    n = len(series)
    if n < 3 or not 1 <= block <= n or reps < 100 or not 0 < alpha < 1:
        raise ValueError("invalid block bootstrap design")
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        draws = []
        while len(draws) < n:
            start = rng.randrange(n)
            draws.extend(series[(start + k) % n] for k in range(block))
        means.append(mean(draws[:n]))
    return [quantile(means, alpha / 2), quantile(means, 1 - alpha / 2)]


def holm_adjust(p_values: list[float]) -> list[float]:
    """Family-wise error adjustment; for illustrative pre-specified p-values."""
    if not p_values or any(not math.isfinite(p) or p < 0 or p > 1 for p in p_values):
        raise ValueError("p-values must be in [0,1]")
    ordering = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    for rank, original in enumerate(ordering):
        running = max(running, min(1.0, (len(p_values)-rank)*p_values[original]))
        adjusted[original] = running
    return adjusted


def run_lab() -> dict:
    rows = make_synthetic_panel()
    validate_panel(rows)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["signal_at"]].append(row)
    dates = sorted(grouped, key=moment)
    periods = [transform_factor_day(grouped[day]) for day in dates]
    stats = [describe_day(data) for data in periods]
    ic = [x["rank_ic"] for x in stats if x["rank_ic"] is not None]
    if len(ic) != len(stats):
        raise ValueError("undefined IC: report data coverage before inference")
    quartiles = [mean([x["quartile_returns"][q] for x in stats]) for q in range(4)]
    turnover = [1-len(set(stats[t]["top_codes"]) & set(stats[t-1]["top_codes"])) /
                len(stats[t]["top_codes"]) for t in range(1, len(stats))]
    train = [row for group in periods[:9] for row in group]
    valid = [row for group in periods[9:] for row in group]
    clean_split = purge_forward(train, valid)
    # A *separate* altered fixture exercises a real overlap, not the IC data.
    broken = [dict(row) for row in train]
    bad = broken[-1]
    far = moment(valid[0]["signal_at"]) + timedelta(days=1)
    bad["label_end_at"] = stamp(far)
    bad["label_available_at"] = stamp(far + timedelta(hours=1))
    purge_example = purge_forward(broken, valid)
    return {
        "source_kind": "SYNTHETIC_ONLY_NO_REAL_A_SHARE_ALPHA",
        "periods": len(stats), "rows": len(rows), "stocks_per_period": len(periods[0]),
        "ic_mean": mean(ic), "icir_unannualized": mean(ic)/stdev(ic) if stdev(ic) else None,
        "hac_mean_se_lag2": hac_mean_se(ic, 2),
        "block_ci_95_block3": moving_block_ci(ic),
        "quartile_gross_returns": quartiles,
        "gross_top_mean": quartiles[3],
        "gross_spread_q4_minus_q1": quartiles[3]-quartiles[0],
        "membership_turnover_proxy": mean(turnover),
        "purge_demo": {"clean_removed": len(clean_split["removed"]),
                       "overlap_removed": len(purge_example["removed"]),
                       "cutoff": clean_split["valid_first_signal_at"]},
        "illustrative_holm": holm_adjust([.01, .03, .08]),
        "limitations": [
            "Synthetic returns only; no model selection, true OOS or causal claim.",
            "HAC and block bootstrap are illustrative on just 12 synthetic periods.",
            "Quartile returns and turnover are pre-cost, idealized and NOT executable.",
            "Forward-only purge is not a universal bidirectional embargo algorithm.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run_lab()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Synthetic-only research lab; NOT a real-market result.")
        print(f"Periods={report['periods']}, stocks/period={report['stocks_per_period']}")
        print(f"Mean RankIC={report['ic_mean']:.4f}, HAC SE={report['hac_mean_se_lag2']:.4f}")
        print("Block CI (synthetic):", report["block_ci_95_block3"])
        print("Purge check:", report["purge_demo"])
        print("Quartile returns are gross observation returns, not fills.")


if __name__ == "__main__":
    main()
