#!/usr/bin/env python3
"""Volume 2 chapters 02-04: mathematics, time series and historical-rule gates.

SYNTHETIC DATA ONLY. No source data, trading returns or P&L in this lab
represent actual A-share securities. Rule examples are narrow, time-versioned
teaching profiles backed by explicitly named exchange notices; not a complete
exchange rule engine or execution/eligibility service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean, stdev

SOURCES = {
    "SSE_2023": "https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20250612_10824490.shtml",
    "SSE_2026": "https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml",
    "SSE_CHANGE_2026": "https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml",
    "SZSE_2023": "https://www.szse.cn/www/investor/knowledge/t20230306_599093.html",
    "SZSE_2026": "https://www.szse.cn/lawrules/rule/trade/current/t20260424_620190.html",
    "SZSE_WARNING_2026": "https://www.szse.cn/lawrules/service/member/t20260630_621404.html",
    "SSE_STAR": "https://edu.sse.com.cn/tib/",
    "SZSE_GEM": "https://www.szse.cn/www/investor/knowledge/t20200805_580244.html",
    "BSE_2026": "https://www.bse.cn/jygl_list/200028217.html",
}
SOURCE_KIND = "SYNTHETIC_TUTORIAL_AND_VERSIONED_RULE_EXAMPLES_NOT_MARKET_EVIDENCE"
REVISION_START = date(2026, 7, 6)
FIRST_SUPPORTED = date(2023, 4, 10)


def fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _finite_numbers(values: list[float]) -> None:
    if not values or any(isinstance(v, bool) or not isinstance(v, (float, int))
                         or not math.isfinite(v) for v in values):
        raise ValueError("nonempty finite numeric sample required")


def sample_covariance(x: list[float], y: list[float]) -> float:
    """Unbiased sample covariance; no assumptions about market return IID."""
    _finite_numbers(x)
    _finite_numbers(y)
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("paired observations, n>=2 required")
    xbar, ybar = mean(x), mean(y)
    return sum((a-xbar)*(b-ybar) for a, b in zip(x, y))/(len(x)-1)


def conditional_mean(values: list[float], flags: list[bool]) -> float:
    _finite_numbers(values)
    if len(values) != len(flags) or any(type(f) is not bool for f in flags):
        raise ValueError("condition and values are not aligned")
    selected = [v for v, f in zip(values, flags) if f]
    if not selected:
        raise ValueError("undefined conditional mean for empty event")
    return mean(selected)


def ols_1d(x: list[float], y: list[float]) -> dict:
    """Intercept and slope of Y on [1,X], valid only if Var(X)>0."""
    _finite_numbers(x)
    _finite_numbers(y)
    slope = sample_covariance(x, y)/sample_covariance(x, x)
    return {"intercept": mean(y)-slope*mean(x), "slope": slope}


def ridge_1d(x: list[float], y: list[float], penalty: float) -> dict:
    """Center X,Y; penalize slope only, objective mean squared error + λβ²."""
    _finite_numbers(x)
    _finite_numbers(y)
    if len(x) != len(y) or len(x) < 2 or not math.isfinite(penalty) or penalty < 0:
        raise ValueError("invalid ridge samples or penalty")
    mx, my = mean(x), mean(y)
    variance = sum((v-mx)**2 for v in x)/len(x)
    covariance = sum((v-mx)*(z-my) for v, z in zip(x, y))/len(x)
    if variance < 1e-15:
        raise ValueError("constant predictor")
    slope = covariance/(variance+penalty)
    return {"intercept": my-slope*mx, "slope": slope, "penalty": penalty}


def ridge_gradient_check(x: list[float], y: list[float], penalty: float,
                         learning_rate: float = .05, steps: int = 1500) -> float:
    """Gradient descent on centered one-dimensional ridge, compare to closed form."""
    closed = ridge_1d(x, y, penalty)
    mx, my = mean(x), mean(y)
    variance = mean([(v-mx)**2 for v in x])
    covariance = mean([(v-mx)*(z-my) for v, z in zip(x, y)])
    if learning_rate <= 0 or steps <= 0:
        raise ValueError("invalid gradient descent settings")
    slope = 0.0
    for _ in range(steps):
        slope -= learning_rate*2*(slope*(variance+penalty)-covariance)
        if not math.isfinite(slope):
            raise ValueError("diverging optimizer")
    return abs(slope-closed["slope"])


def two_asset_grid(mu: list[float], covariance: list[list[float]],
                   lam: float = 6.0, step: float = .1) -> dict:
    """Exact search on declared cash/long-only grid; NOT a continuous optimum."""
    _finite_numbers(mu)
    if len(mu) != 2 or len(covariance) != 2 or any(len(row) != 2 for row in covariance):
        raise ValueError("two assets required")
    for row in covariance:
        _finite_numbers(row)
    if not 0 < step <= 1 or abs(1/step-round(1/step)) > 1e-8 or lam < 0:
        raise ValueError("invalid grid parameters")
    if abs(covariance[0][1]-covariance[1][0]) > 1e-12:
        raise ValueError("covariance must be symmetric")
    n = round(1/step)
    best = None
    for a in range(n+1):
        for b in range(n-a+1):
            w = [a*step, b*step]
            risk = sum(w[i]*covariance[i][j]*w[j] for i in range(2) for j in range(2))
            score = sum(w[i]*mu[i] for i in range(2))-lam*risk
            if best is None or score > best["objective"]:
                best = {"weights": w, "cash": 1-sum(w), "objective": score,
                        "risk_proxy": risk}
    assert best is not None
    return best


def synthetic_ar1(n: int = 160, phi: float = .72, seed: int = 2206,
                  break_at: int = 112) -> list[float]:
    """Deliberately autocorrelated and mean-shifting GENERATIVE process."""
    if not 15 <= n <= 5000 or not -0.95 < phi < .95 or not 3 <= break_at <= n-3:
        raise ValueError("invalid synthetic AR1 parameters")
    rng = random.Random(seed)
    last = 0.0
    out = []
    for t in range(n):
        target = 0.035 if t >= break_at else 0.0
        last = target + phi*(last-target) + rng.gauss(0, .025)
        out.append(last)
    return out


def simple_return(p0: float, p1: float) -> float:
    if not 0 < p0 < float("inf") or not 0 < p1 < float("inf"):
        raise ValueError("positive finite prices required")
    return p1/p0-1


def log_return(p0: float, p1: float) -> float:
    return math.log1p(simple_return(p0, p1))


def autocorrelation(x: list[float], lag: int = 1) -> float:
    _finite_numbers(x)
    n = len(x)
    if isinstance(lag, bool) or not 1 <= lag < n:
        raise ValueError("lag must be 1..n-1")
    mu = mean(x)
    denominator = sum((v-mu)**2 for v in x)
    if denominator <= 1e-16:
        raise ValueError("undefined autocorrelation for constant series")
    return sum((x[t]-mu)*(x[t-lag]-mu) for t in range(lag, n))/denominator


def iid_mean_se(x: list[float]) -> float:
    _finite_numbers(x)
    if len(x) < 2:
        raise ValueError("n>=2")
    return stdev(x)/math.sqrt(len(x))


def hac_mean_se(x: list[float], lags: int = 4) -> float:
    """Bartlett weighted lag-window SE for series mean, teaching approximation."""
    _finite_numbers(x)
    n = len(x)
    if isinstance(lags, bool) or not 0 <= lags < n or n < 2:
        raise ValueError("invalid HAC lags")
    centered = [v-mean(x) for v in x]
    long_run = sum(v*v for v in centered)/n
    for j in range(1, lags+1):
        auto_cov = sum(centered[t]*centered[t-j] for t in range(j, n))/n
        long_run += 2*(1-j/(lags+1))*auto_cov
    if long_run < -1e-12:
        raise ValueError("negative long-run variance")
    return math.sqrt(max(0., long_run)/n)


def circular_block_ci(x: list[float], block: int = 8, n_boot: int = 1500,
                      seed: int = 2206, alpha: float = .05) -> list[float]:
    _finite_numbers(x)
    n = len(x)
    if n < 4 or not 1 <= block <= n or n_boot < 100 or not 0 < alpha < 1:
        raise ValueError("invalid bootstrap settings")
    rng = random.Random(seed)
    values = []
    for _ in range(n_boot):
        drawn = []
        while len(drawn) < n:
            j = rng.randrange(n)
            drawn.extend(x[(j+k) % n] for k in range(block))
        values.append(mean(drawn[:n]))
    values.sort()
    def quantile(p: float) -> float:
        i = (len(values)-1)*p
        lower, upper = math.floor(i), math.ceil(i)
        return values[lower] + (i-lower)*(values[upper]-values[lower])
    return [quantile(alpha/2), quantile(1-alpha/2)]


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    try:
        v = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise ValueError("invalid ISO event timestamp") from err
    if v.utcoffset() is None:
        raise ValueError("timezone is mandatory")
    return v.astimezone(timezone.utc)


def known_before_decision(known_at: str, decision_at: str) -> bool:
    """Equal-time records allowed in this toy; systems can demand latency buffer."""
    return timestamp(known_at) <= timestamp(decision_at)


def next_session(calendar: list[str], signal_date: str) -> str:
    """Only an explicitly supplied EXCHANGE calendar counts; weekends insufficient."""
    if not calendar or len(set(calendar)) != len(calendar):
        raise ValueError("nonempty, duplicate-free exchange calendar required")
    parsed = [date.fromisoformat(value) for value in calendar]
    if parsed != sorted(parsed):
        raise ValueError("exchange calendar must be sorted")
    signal = date.fromisoformat(signal_date)
    for d in parsed:
        if d > signal:
            return d.isoformat()
    raise ValueError("no later exchange session in provided calendar")


def trading_rule(venue: str, board: str, on: str, risk_warning: bool = False,
                 ipo_session: int | None = None) -> dict:
    """NARROW 2023+/2026 price-band and BUY-size examples; fail on unknown.

    Not an exhaustive, authoritative dated engine. IPO exemptions require
    externally verified IPO session count, status and identity.
    """
    d = date.fromisoformat(on)
    key = (venue.upper(), board.upper())
    valid = {("SSE","MAIN"), ("SSE","STAR"), ("SZSE","MAIN"),
             ("SZSE","GEM"), ("BSE","STOCK")}
    if key not in valid or d < FIRST_SUPPORTED:
        raise ValueError("unsupported venue/board/date; manual rule review needed")
    if key[0] == "BSE" and d < REVISION_START:
        raise ValueError("BSE pre-2026 rules not encoded")
    if risk_warning and board.upper() != "MAIN":
        raise ValueError("this teaching table does not cover non-main risk warning")
    if ipo_session is not None and (type(ipo_session) is not int or ipo_session < 1):
        raise ValueError("IPO session must be a verified positive integer")
    rate = .10
    lot = 100
    increment = 100
    source = SOURCES["SSE_2026"] if key[0] == "SSE" and d >= REVISION_START else SOURCES["SSE_2023"] if key[0] == "SSE" else SOURCES["SZSE_2026"] if d >= REVISION_START and key[0] == "SZSE" else SOURCES["SZSE_2023"]
    if key == ("SSE","STAR"):
        rate, lot, increment = .20, 200, 1
        source = SOURCES["SSE_2026"] if d >= REVISION_START else SOURCES["SSE_STAR"]
    elif key == ("SZSE","GEM"):
        rate = .20
        source = SOURCES["SZSE_2026"] if d >= REVISION_START else SOURCES["SZSE_GEM"]
    elif key == ("BSE","STOCK"):
        rate, lot, increment, source = .30, 100, 1, SOURCES["BSE_2026"]
    elif risk_warning:
        rate = .05 if d < REVISION_START else .10
        source = SOURCES["SSE_CHANGE_2026"] if key[0] == "SSE" and d >= REVISION_START else SOURCES["SZSE_WARNING_2026"] if key[0] == "SZSE" and d >= REVISION_START else source
    # Price-limit exemptions depend on verified actual consecutive trading sessions.
    exempt = ipo_session is not None and (
        ipo_session <= (1 if key[0] == "BSE" else 5))
    return {
        "venue": key[0], "board": key[1], "on": on,
        "risk_warning": risk_warning, "ipo_session": ipo_session,
        "price_limit_pct": None if exempt else rate,
        "price_band_exemption": "VERIFIED_IPO_SESSION" if exempt else None,
        "min_buy_shares": lot, "buy_increment": increment,
        "reference_url": source, "rule_revision": (
            "2026-07-06-or-later" if d >= REVISION_START else
            "pre-2026-07-06-selected-scope"),
        "evidence_limits": "other status exceptions, rounding, queue and dated transition rules omitted",
    }


def validate_buy_size(rule: dict, shares: int) -> bool:
    if type(shares) is not int or shares < rule["min_buy_shares"]:
        return False
    return (shares-rule["min_buy_shares"]) % rule["buy_increment"] == 0


def price_band(rule: dict, previous_close: str) -> dict:
    if rule["price_limit_pct"] is None:
        return {"lower": None, "upper": None, "meaning": "NO_BAND_NOT_GUARANTEED_FILL"}
    last = Decimal(previous_close)
    if not last.is_finite() or last <= 0:
        raise ValueError("positive reference close required")
    pct = Decimal(str(rule["price_limit_pct"]))
    # Exchange tick treatment is more intricate; this is NOT a fill model.
    q = Decimal("0.01")
    return {"lower": str((last*(1-pct)).quantize(q, rounding=ROUND_HALF_UP)),
            "upper": str((last*(1+pct)).quantize(q, rounding=ROUND_HALF_UP)),
            "meaning": "TEACHING_CENT_ROUNDING_ONLY_NOT_EXECUTION"}


def run_lab() -> dict:
    x = [0., 1., 2., 3., 4., 5.]
    y = [1., 2., 4., 4., 6., 8.]
    linear = ols_1d(x, y)
    regularized = ridge_1d(x, y, .3)
    synthetic = synthetic_ar1()
    n = len(synthetic)
    sig = "2026-11-13T18:00:00+08:00"
    before = "2026-11-12T16:00:00-05:00"
    after = "2026-11-13T16:00:00-05:00"
    rules = [
        trading_rule("SSE", "MAIN", "2026-07-03", risk_warning=True),
        trading_rule("SSE", "MAIN", "2026-07-06", risk_warning=True),
        trading_rule("SZSE", "MAIN", "2026-07-03", risk_warning=True),
        trading_rule("SZSE", "MAIN", "2026-07-06", risk_warning=True),
        trading_rule("SSE", "STAR", "2026-09-08"),
        trading_rule("SZSE", "GEM", "2026-09-08"),
        trading_rule("BSE", "STOCK", "2026-09-08"),
    ]
    data = {
        "source_kind": SOURCE_KIND,
        "math": {
            "sample_covariance": sample_covariance(x, y),
            "ols": linear, "ridge": regularized,
            "gradient_slope_error": ridge_gradient_check(x, y, .3),
            "conditional_mean": conditional_mean(y, [v >= 3 for v in x]),
            "two_asset_grid": two_asset_grid([.025, .015],
                                             [[.0015,.0003],[.0003,.0008]]),
        },
        "time_series": {
            "n": n, "sample_kind": "DELIBERATELY_AUTOCORRELATED_AND_SHIFTING",
            "overall_mean": mean(synthetic),
            "lag1_autocorrelation": autocorrelation(synthetic),
            "naive_iid_mean_se": iid_mean_se(synthetic),
            "hac_mean_se_lag4": hac_mean_se(synthetic, 4),
            "circular_block_95ci_block8": circular_block_ci(synthetic),
            "mean_first_112": mean(synthetic[:112]),
            "mean_last_48": mean(synthetic[112:]),
            "simple_one_step": simple_return(100., 110.),
            "log_one_step": log_return(100., 110.),
        },
        "market_rules": {
            "versioned_profiles": rules,
            "cross_border_known_before_china_decision": {
                "prior_us_close": known_before_decision(before, sig),
                "same_us_day_close": known_before_decision(after, sig),
            },
            "listed_next_session": next_session(
                ["2026-09-30", "2026-10-09", "2026-10-12"], "2026-09-30"),
            "case_not_fills": "PRICE_BAND_AND_BUY_SIZE_VALIDATION_ARE_NOT_FILL_CERTIFICATES",
            "rule_sources": SOURCES,
        },
        "limitations": [
            "Mathematics, prices and time series are fully synthetic.",
            "HAC/Bootstrap are demonstrations, not formal inference under regime breaks.",
            "All rule profiles are narrow educational selections, not full trading rules.",
            "2026-07-06 is a real rule-version boundary; earlier years require a fuller rule archive.",
            "An IPO price-limit exemption is not evidence an order will fill.",
            "No provider PIT, corporate action, actual order book, fee archive or OOS backtest.",
        ],
    }
    data["report_sha256"] = fingerprint(data)
    return data


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="full synthetic report")
    args = p.parse_args()
    result = run_lab()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("SYNTHETIC mathematics and dated market-rule GATES; NOT market returns.")
        print("OLS slope:", round(result["math"]["ols"]["slope"], 6))
        print("Autocorrelation:", round(result["time_series"]["lag1_autocorrelation"], 4))
        print("SSE risk warning before/after 2026-07-06:",
              [r["price_limit_pct"] for r in
               result["market_rules"]["versioned_profiles"][:2]])
        print("Audit digest:", result["report_sha256"][:16])


if __name__ == "__main__":
    main()
