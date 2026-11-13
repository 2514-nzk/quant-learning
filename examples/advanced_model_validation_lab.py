#!/usr/bin/env python3
"""Synthetic model-comparison lab for volume 2 chapters 09–11.

NO real A-share history, alpha, trading profitability, production OOS or
real-world market evidence is produced. Stdlib-only; deterministic fixtures.
Validation chooses a model; a later chronological segment is scored once,
using prequential training with labels available before each signal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

FEATURES = ("factor_a", "factor_b", "factor_dup")
CANDIDATES = ("factor_a", "factor_b", "equal_blend", "ridge_a_dup", "ridge_all", "pairwise")
TRAIN_PERIODS = 20
VALID_PERIODS = 10
HOLDOUT_PERIODS = 12


def moment(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be ISO text with a timezone offset")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone offset is required")
    return parsed.astimezone(timezone.utc)


def make_panel(periods: int = 42, n_stocks: int = 12) -> list[dict]:
    """Synthetic, deliberately drifting labels and inputs, NOT market data."""
    if periods < TRAIN_PERIODS + VALID_PERIODS + 2 or n_stocks < 6:
        raise ValueError("insufficient artificial dates or securities")
    tz = timezone(timedelta(hours=8))
    start = datetime(2024, 1, 5, 15, tzinfo=tz)
    rows = []
    for t in range(periods):
        signal = start + timedelta(days=7 * t)
        entry = (signal + timedelta(days=3)).replace(hour=9, minute=30)
        label_end = (signal + timedelta(days=7)).replace(hour=9, minute=30)
        label_available = label_end + timedelta(hours=1)
        for j in range(n_stocks):
            a = (math.sin((j + 2) * (t + 1) * .41)
                 + .12 * (j % 3) + (.65 if t >= 30 else 0))
            b = math.cos((j + 1) * (t + 3) * .29) - .09 * (j % 3)
            dup = a * .97 + .03 * math.sin((j + 1) * .93)
            noise = math.sin((j + 4) * (t + 2) * .77)
            # A post-development synthetic regime switch is intentional.
            future = (.014 * ((.75 if t < 30 else -.55) * a + .55 * b)
                      + .006 * noise + .002 * (j % 3 - 1))
            rows.append({
                "signal_at": signal.isoformat(), "code": f"S{j + 1:02d}",
                "industry": f"I{j % 3 + 1}",
                "feature_available_at": (signal - timedelta(minutes=5)).isoformat(),
                "decision_at": (signal + timedelta(hours=3)).isoformat(),
                "entry_at": entry.isoformat(),
                "label_end_at": label_end.isoformat(),
                "label_available_at": label_available.isoformat(),
                "factor_a": a, "factor_b": b, "factor_dup": dup,
                "future_return": future,
            })
    return rows


def validate_rows(rows: list[dict]) -> None:
    if not rows:
        raise ValueError("empty panel")
    seen = set()
    for row in rows:
        key = (row["signal_at"], row["code"])
        if key in seen:
            raise ValueError(f"duplicate row: {key}")
        seen.add(key)
        if not row["code"] or not row["industry"]:
            raise ValueError("missing code/industry")
        for field in (*FEATURES, "future_return"):
            v = row[field]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"nonfinite or nonnumeric {field}")
        a = moment(row["feature_available_at"])
        s = moment(row["signal_at"])
        d = moment(row["decision_at"])
        e = moment(row["entry_at"])
        end = moment(row["label_end_at"])
        ready = moment(row["label_available_at"])
        if not (a <= s <= d < e <= end <= ready):
            raise ValueError(f"invalid timestamp sequence: {key}")


def group_by_signal(rows: list[dict]) -> list[list[dict]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["signal_at"]].append(row)
    return [sorted(grouped[day], key=lambda r: r["code"])
            for day in sorted(grouped, key=moment)]


def midranks(values: list[float]) -> list[float]:
    pairs = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.] * len(values)
    i = 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[j][1] == pairs[i][1]:
            j += 1
        rank = (i + 1 + j) / 2
        for k in range(i, j):
            ranks[pairs[k][0]] = rank
        i = j
    return ranks


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y):
        raise ValueError("unaligned vectors")
    if len(x) < 2:
        return None
    mx, my = mean(x), mean(y)
    xx = sum((z - mx)**2 for z in x)
    yy = sum((z - my)**2 for z in y)
    return (sum((a-mx)*(b-my) for a, b in zip(x, y)) / math.sqrt(xx*yy)
            if xx > 1e-22 and yy > 1e-22 else None)


def rank_ic(x: list[float], y: list[float]) -> float | None:
    return pearson(midranks(x), midranks(y))


def normalize_training(rows: list[dict], keys: tuple[str, ...]) -> dict:
    if not rows:
        raise ValueError("cannot fit without training data")
    mu = [mean(r[key] for r in rows) for key in keys]
    sd = [pstdev(r[key] for r in rows) for key in keys]
    if any(s < 1e-12 for s in sd):
        raise ValueError("degenerate training features")
    return {"keys": keys, "means": mu, "scales": sd}


def xvec(row: dict, state: dict) -> list[float]:
    return [(row[key]-mu)/sd for key, mu, sd in
            zip(state["keys"], state["means"], state["scales"])]


def solve_system(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Small linear system, pivoted Gauss–Jordan. No external dependencies."""
    n = len(rhs)
    a = [list(line) + [rhs[i]] for i, line in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(a[i][col]))
        if abs(a[pivot][col]) <= 1e-14:
            raise ValueError("singular linear system")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [x / scale for x in a[col]]
        for i in range(n):
            if i == col:
                continue
            factor = a[i][col]
            a[i] = [x-factor*y for x, y in zip(a[i], a[col])]
    return [a[i][-1] for i in range(n)]


def fit_model(name: str, training: list[dict]) -> dict:
    if name not in CANDIDATES:
        raise ValueError("unknown model name")
    if name in ("factor_a", "factor_b", "equal_blend"):
        return {"name": name, "fit_rows": 0}
    keys = ("factor_a", "factor_dup") if name == "ridge_a_dup" else FEATURES
    state = normalize_training(training, keys)
    vectors = [xvec(row, state) for row in training]
    if name.startswith("ridge"):
        y_mean = mean(r["future_return"] for r in training)
        target = [r["future_return"]-y_mean for r in training]
        n, p = len(vectors), len(keys)
        # Ridge objective: (1/n)||y-Xw||^2 + lambda||w||^2.
        penalty = .15
        a = [[sum(v[i]*v[j] for v in vectors)/n +
              (penalty if i == j else 0) for j in range(p)] for i in range(p)]
        rhs = [sum(v[i]*y for v, y in zip(vectors, target))/n for i in range(p)]
        weights = solve_system(a, rhs)
        return {"name": name, "state": state, "weights": weights,
                "intercept": y_mean, "fit_rows": n}
    # Pairwise logistic learning-to-rank: only comparisons from SAME signal.
    grouped = defaultdict(list)
    for row, vector in zip(training, vectors):
        grouped[row["signal_at"]].append((row["future_return"], vector))
    pairs = []
    for items in grouped.values():
        for i in range(len(items)):
            for j in range(i+1, len(items)):
                yi, xi = items[i]
                yj, xj = items[j]
                if abs(yi-yj) < 1e-12:
                    continue
                sign = 1 if yi > yj else -1
                pairs.append([sign*(a-b) for a, b in zip(xi, xj)])
    if not pairs:
        raise ValueError("no comparable training pairs")
    weights = [0.] * len(keys)
    for _ in range(90):
        grad = [.04*w for w in weights]
        for diff in pairs:
            margin = max(-30., min(30., sum(w*x for w, x in zip(weights, diff))))
            scale = 1 / (1 + math.exp(margin))
            for j, value in enumerate(diff):
                grad[j] -= scale * value / len(pairs)
        weights = [w-.3*g for w, g in zip(weights, grad)]
    return {"name": name, "state": state, "weights": weights,
            "intercept": 0., "fit_rows": len(training),
            "pair_count": len(pairs)}


def predict_group(model: dict, rows: list[dict]) -> dict[str, float]:
    """Predictions read FEATURES only; current/future labels are never read."""
    name = model["name"]
    if name in ("factor_a", "factor_b"):
        return {r["code"]: r[name] for r in rows}
    if name == "equal_blend":
        result = {}
        vals = {k: [r[k] for r in rows] for k in ("factor_a", "factor_b")}
        means = {k: mean(v) for k, v in vals.items()}
        stds = {k: pstdev(v) for k, v in vals.items()}
        if any(z < 1e-12 for z in stds.values()):
            raise ValueError("constant same-day factor")
        for row in rows:
            result[row["code"]] = sum((row[k]-means[k])/stds[k]
                                      for k in vals)/2
        return result
    state = model["state"]
    return {row["code"]: model["intercept"] +
            sum(w*x for w, x in zip(model["weights"], xvec(row, state)))
            for row in rows}


def group_ic(prediction: dict[str, float], group: list[dict]) -> float:
    if set(prediction) != {r["code"] for r in group}:
        raise ValueError("prediction/label universe mismatch")
    ic = rank_ic([prediction[row["code"]] for row in group],
                 [row["future_return"] for row in group])
    if ic is None:
        raise ValueError("undefined period RankIC")
    return ic


def eligible_before(rows: list[dict], cutoff: str) -> list[dict]:
    instant = moment(cutoff)
    return [r for r in rows
            if moment(r["signal_at"]) < instant and
            moment(r["label_available_at"]) < instant]


def fingerprint(rows: list[dict]) -> str:
    # Includes PAST labels. A future change must not change current fingerprint.
    items = [{k: r[k] for k in
              ("signal_at", "label_available_at", "code", *FEATURES,
               "future_return")} for r in
             sorted(rows, key=lambda row: (moment(row["signal_at"]), row["code"]))]
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def select_on_validation(rows: list[dict]) -> dict:
    """Single frozen development train/validation; NO final holdout labels."""
    validate_rows(rows)
    periods = group_by_signal(rows)
    if len(periods) < TRAIN_PERIODS + VALID_PERIODS:
        raise ValueError("need at least 30 dated periods")
    train_raw = [r for group in periods[:TRAIN_PERIODS] for r in group]
    validation = periods[TRAIN_PERIODS:TRAIN_PERIODS+VALID_PERIODS]
    cutoff = validation[0][0]["signal_at"]
    train = eligible_before(train_raw, cutoff)
    if not train:
        raise ValueError("no complete training labels by validation")
    scores = {}
    for name in CANDIDATES:
        model = fit_model(name, train)
        scores[name] = mean([group_ic(predict_group(model, group), group)
                             for group in validation])
    # Candidate order is a deterministic tie-breaker. A family was fixed first.
    chosen = max(CANDIDATES, key=lambda name: scores[name])
    return {"selected": chosen, "validation_ic": scores,
            "validation_increment_ridge_all_minus_ablation":
            scores["ridge_all"]-scores["ridge_a_dup"],
            "train_label_max_at": max(r["label_available_at"] for r in train),
            "validation_first_signal_at": cutoff, "train_rows": len(train),
            "policy": "maximize mean validation RankIC among six predeclared candidates"}


def run_prequential(rows: list[dict], selected: str) -> dict:
    """Predict then score each future artificial date; refit only on past labels."""
    if selected not in CANDIDATES:
        raise ValueError("selected model is not a predeclared candidate")
    validate_rows(rows)
    periods = group_by_signal(rows)
    first = TRAIN_PERIODS + VALID_PERIODS
    if len(periods) <= first:
        raise ValueError("no holdout periods")
    details = []
    for group in periods[first:]:
        cutoff = group[0]["signal_at"]
        prior = eligible_before(rows, cutoff)
        if not prior:
            raise ValueError("no prior eligible training labels")
        model = fit_model(selected, prior)
        pred = predict_group(model, group)
        baseline = predict_group(fit_model("factor_a", prior), group)
        details.append({
            "signal_at": cutoff, "fit_rows": len(prior),
            "last_train_label_available_at": max(
                prior, key=lambda r: moment(r["label_available_at"])
            )["label_available_at"],
            "train_fingerprint": fingerprint(prior),
            "selected_ic": group_ic(pred, group),
            "baseline_ic": group_ic(baseline, group),
            "prediction_scores": pred,
        })
    return {"folds": details,
            "selected_mean_ic": mean(f["selected_ic"] for f in details),
            "baseline_mean_ic": mean(f["baseline_ic"] for f in details)}


def drift_diagnostic(rows: list[dict]) -> dict:
    """Post-hoc input shift, NOT used in selection or during prediction."""
    periods = group_by_signal(rows)
    development = [r for group in periods[:30] for r in group]
    later = [r for group in periods[30:] for r in group]
    shifts = {}
    for name in FEATURES:
        base = [r[name] for r in development]
        current = [r[name] for r in later]
        deviation = pstdev(base)
        shifts[name] = ((mean(current)-mean(base))/deviation
                        if deviation > 1e-12 else None)
    return {"standardized_mean_shift_posthoc": shifts,
            "interpretation": "input distribution shift only; not an alpha or cause test"}


def run_lab(rows: list[dict] | None = None) -> dict:
    observations = make_panel() if rows is None else rows
    validate_rows(observations)
    selection = select_on_validation(observations)
    holdout = run_prequential(observations, selection["selected"])
    drift = drift_diagnostic(observations)
    return {
        "source_kind": "SYNTHETIC_ONLY_NOT_REAL_OOS_OR_A_SHARE_ALPHA",
        "total_rows": len(observations),
        "total_periods": len(group_by_signal(observations)),
        "development": selection,
        "simulated_prequential": holdout,
        "drift_posthoc": drift,
        "limitations": [
            "Synthetic data deliberately contains a late regime shift.",
            "Validation selected model family; final segment did not select it.",
            "Prequential fits only prior known labels, not same/future outcomes.",
            "A chronological simulation is not independent real-market OOS evidence.",
            "RankIC scores are not post-cost returns or real fills.",
            "Repeatedly inspecting this example has no confirmatory OOS status.",
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
        dev = report["development"]
        hold = report["simulated_prequential"]
        print("SYNTHETIC ONLY — no real A-share or tradable result")
        print("Chosen using development validation:", dev["selected"])
        print("Holdout weeks:", len(hold["folds"]))
        print("Synthetic prequential RankIC:", round(hold["selected_mean_ic"], 4))
        print("Synthetic baseline RankIC:", round(hold["baseline_mean_ic"], 4))
        print("Models and performance may drift; no trading recommendation.")


if __name__ == "__main__":
    main()
