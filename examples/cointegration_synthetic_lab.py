#!/usr/bin/env python3
"""Deterministic synthetic cointegration control experiment. SYNTHETIC_ONLY.

Constructs one pair with a shared random-walk trend plus a stationary AR(1)
spread, and one unrelated random-walk control pair. This validates the teaching
pipeline and known data-generating process; it is not market evidence.
"""
from __future__ import annotations
import argparse
import json
import math
import random

SEED = 20261116
N = 300
TRAIN = 200

def generate(seed: int = SEED, n: int = N):
    if n <= 20:
        raise ValueError("Need more than 20 observations")
    rng = random.Random(seed)
    trend = 100.0
    spread = 0.0
    x, y, u, v = [], [], [], []
    unrelated_x = 80.0
    unrelated_y = 120.0
    for _ in range(n):
        trend += rng.gauss(0, 1.0)
        spread = 0.72 * spread + rng.gauss(0, 0.8)
        x_value = trend + rng.gauss(0, 0.15)
        y_value = 5.0 + 1.4 * trend + spread
        unrelated_x += rng.gauss(0, 1.0)
        unrelated_y += rng.gauss(0, 1.0)
        x.append(x_value)
        y.append(y_value)
        u.append(unrelated_x)
        v.append(unrelated_y)
    return {"x": x, "y": y, "control_x": u, "control_y": v}

def mean(values):
    return sum(values) / len(values)

def fit_ols(x, y):
    if len(x) != len(y) or len(x) < 3:
        raise ValueError("Equal samples of at least three values are required")
    mx, my = mean(x), mean(y)
    denom = sum((a - mx) ** 2 for a in x)
    if denom <= 1e-12:
        raise ValueError("Regressor has no variation")
    beta = sum((a - mx) * (b - my) for a, b in zip(x, y)) / denom
    return my - beta * mx, beta

def ar1_diagnostic(values):
    if len(values) < 4:
        raise ValueError("Need at least four spread observations")
    x, y = values[:-1], values[1:]
    intercept, phi = fit_ols(x, y)
    half_life = math.log(0.5) / math.log(phi) if 0 < phi < 1 else None
    return {"ar1_phi": phi, "half_life_observations": half_life,
            "stationary_ar1_parameter_region": bool(abs(phi) < 1)}

def evaluate(payload=None):
    data = generate() if payload is None else payload
    if set(data) != {"x", "y", "control_x", "control_y"}:
        raise ValueError("Unexpected synthetic fixture fields")
    lengths = {len(v) for v in data.values()}
    if len(lengths) != 1 or next(iter(lengths)) != N:
        raise ValueError(f"Expected four series with exactly {N} observations")
    if not all(math.isfinite(z) for series in data.values() for z in series):
        raise ValueError("All observations must be finite")
    train = slice(0, TRAIN)
    holdout = slice(TRAIN, N)
    alpha, beta = fit_ols(data["x"][train], data["y"][train])
    spread_train = [b - alpha - beta * a for a, b in zip(data["x"][train], data["y"][train])]
    spread_holdout = [b - alpha - beta * a for a, b in zip(data["x"][holdout], data["y"][holdout])]
    mu, sd = mean(spread_train), math.sqrt(sum((z - mean(spread_train))**2 for z in spread_train)/(len(spread_train)-1))
    if sd <= 1e-12:
        raise ValueError("Training spread dispersion is zero")
    holdout_z = [(z - mu) / sd for z in spread_holdout]
    c_alpha, c_beta = fit_ols(data["control_x"][train], data["control_y"][train])
    control_train = [b - c_alpha - c_beta*a for a,b in zip(data["control_x"][train],data["control_y"][train])]
    control_diag = ar1_diagnostic(control_train)
    pair_diag = ar1_diagnostic(spread_train)
    return {
        "evidence_grade":"SYNTHETIC_ONLY", "seed":SEED, "observations":N,
        "train_observations":TRAIN, "holdout_observations":N-TRAIN,
        "fit":{"intercept":alpha,"beta":beta},
        "train_spread":{"mean":mu,"sample_sd":sd,**pair_diag},
        "holdout":{"mean_abs_z":mean([abs(z) for z in holdout_z]),
                   "max_abs_z":max(abs(z) for z in holdout_z)},
        "independent_random_walk_control":{"fit":{"intercept":c_alpha,"beta":c_beta},
                                           "train_spread":control_diag},
        "data_generating_process_known":True,
        "market_cointegration_proven":False,
        "market_alpha_proven":False,
        "execution_proven":False,
        "interpretation":"A controlled code-path example with a known stationary AR(1) spread; the finite-sample diagnostic is not a formal Engle-Granger test and says nothing about real securities."
    }

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json",action="store_true")
    args=parser.parse_args()
    result=evaluate()
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True) if args.json else
          f"SYNTHETIC_ONLY: beta={result['fit']['beta']:.3f}; "
          f"spread AR(1) phi={result['train_spread']['ar1_phi']:.3f}; "
          f"control phi={result['independent_random_walk_control']['train_spread']['ar1_phi']:.3f}")

if __name__=="__main__":
    main()
