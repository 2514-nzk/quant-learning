#!/usr/bin/env python3
"""Local descriptive cross-section research. No data download or upload.
Requires trade_date, ts_code, open, close. CSV stdlib; Parquet optional pyarrow.
Prices, observed calendar and membership are not independently PIT-verified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from statistics import mean

FACTORS = ("REV5", "REV20", "MOM20")


def day(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    return date.fromisoformat(text[:10]).isoformat()


def rows(path, columns):
    if path.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(columns=columns, batch_size=65536):
            yield from batch.to_pylist()
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not set(columns).issubset(reader.fieldnames or []):
                raise ValueError("Required columns missing")
            for row in reader:
                yield {key: row[key] for key in columns}
    else:
        raise ValueError("Expected .csv or .parquet")


def positive(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def endpoints(days, signal, label):
    i = days.index(signal)
    exit_offset = 1 if label == "intraday" else 6
    if i < 20 or i + exit_offset >= len(days):
        raise ValueError("Insufficient observed dates for " + signal)
    return days[i-20], days[i-5], signal, days[i+1], days[i+exit_offset]


def average_ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        for k in range(i, j):
            ranks[order[k]] = (i+j-1)/2
        i = j
    return ranks


def rank_ic(x, y):
    if len(x) < 2 or len(x) != len(y):
        return None
    a, b = average_ranks(x), average_ranks(y)
    m = (len(x)-1)/2
    aa = sum((v-m)**2 for v in a)
    bb = sum((v-m)**2 for v in b)
    return sum((u-m)*(v-m) for u,v in zip(a,b))/math.sqrt(aa*bb) if aa and bb else None


def evaluate(panel, days, signals, ks, label):
    if label not in ("intraday", "next_open_5"):
        raise ValueError("Unknown label")
    if not signals or len(set(signals)) != len(signals) or not ks or min(ks) < 1 or len(set(ks)) != len(ks):
        raise ValueError("Require unique signals and positive unique K")
    rounds = []
    for signal in sorted(signals):
        long, short, _, entry, exit_ = endpoints(days, signal, label)
        scores = []
        # Freeze the candidate set using only signal and past prices.
        for code, (_, close) in panel[signal].items():
            p20 = panel[long].get(code, (None, None))[1]
            p5 = panel[short].get(code, (None, None))[1]
            if close is None or p20 is None or p5 is None:
                continue
            m5, m20 = close/p5-1, close/p20-1
            if not math.isfinite(m5) or not math.isfinite(m20):
                continue
            scores.append((code, {"REV5":-m5, "REV20":-m20, "MOM20":m20}))
        # Future prices are joined only after candidate scores have been frozen.
        ys = {}
        for code, _ in scores:
            buy = panel[entry].get(code,(None,None))[0]
            sell = panel[exit_].get(code,(None,None))[1 if label=="intraday" else 0]
            if buy is not None and sell is not None:
                ret = sell/buy-1
                if math.isfinite(ret):
                    ys[code] = ret
        paired = [(code, val) for code,val in scores if code in ys]
        benchmark = mean(ys.values()) if ys else None
        row = {"signal_date":signal,"entry_date":entry,"exit_date":exit_,
               "base20_date":long,"base5_date":short,
               "valid_scores":len(scores),"valid_labels":len(ys),
               "benchmark_observed_gross":benchmark,"factors":{}}
        for factor in FACTORS:
            order = sorted(scores, key=lambda r:(-r[1][factor],r[0]))
            top = []
            for k in ks:
                chosen = order[:k]
                realized = [ys[code] for code,_ in chosen if code in ys]
                gross = mean(realized) if len(realized)==k else None
                top.append({"k":k,"selected":len(chosen),"valid_labels":len(realized),
                            "gross":gross,"excess":gross-benchmark if gross is not None else None})
            row["factors"][factor] = {
                "rank_ic":rank_ic([v[factor] for code,v in paired],[ys[code] for code,_ in paired]),
                "top":top}
        rounds.append(row)

    def complete(r, j):
        return all(r["factors"][f]["top"][j]["gross"] is not None for f in FACTORS)

    def summarize(j, subset):
        return {f:mean(r["factors"][f]["top"][j]["excess"] for r in subset)
                if subset else None for f in FACTORS}

    common_all = [r for r in rounds if all(complete(r,j) for j in range(len(ks)))]
    return {"label":label,"rounds":rounds,
            "mean_rank_ic":{f:mean(vals) if (vals := [r["factors"][f]["rank_ic"] for r in rounds
                            if r["factors"][f]["rank_ic"] is not None]) else None for f in FACTORS},
            "common_by_k":[{"k":k,"dates":[r["signal_date"] for r in subset],
                            "mean_excess":summarize(j,subset)}
                           for j,k in enumerate(ks)
                           for subset in [[r for r in rounds if complete(r,j)]]],
            "common_all_k":{"dates":[r["signal_date"] for r in common_all],
                            "mean_excess_by_k":[{"k":k,"mean_excess":summarize(j,common_all)}
                                                for j,k in enumerate(ks)]},
            "evidence":"DESCRIPTIVE_PRICE_OBSERVATION_ONLY",
            "limitations":["observed input dates are not verified exchange calendar",
                           "price adjustment and corporate actions not independently checked",
                           "not historical PIT membership; not executable account return",
                           "intraday label is not a new-buy same-day sell strategy under A-share T+1",
                           "missing outcomes may bias paired RankIC and observed benchmark"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--signal",nargs="+",required=True)
    p.add_argument("--k",nargs="+",type=int,default=[10,20,30,50,100,200])
    p.add_argument("--label",choices=["intraday","next_open_5"],default="next_open_5")
    p.add_argument("--output",type=Path,required=True)
    a = p.parse_args()
    if a.output.resolve()==a.input.resolve() or a.output.exists():
        p.error("Choose a new output file")
    signals = [day(d) for d in a.signal]
    days = sorted({day(r["trade_date"]) for r in rows(a.input,["trade_date"])})
    needed = {d for signal in signals for d in endpoints(days,signal,a.label)}
    panel = {d:{} for d in needed}
    for r in rows(a.input,["trade_date","ts_code","open","close"]):
        d = day(r["trade_date"])
        if d not in needed:
            continue
        code = str(r["ts_code"]).strip() if r["ts_code"] is not None else ""
        if not code or code in panel[d]:
            raise ValueError("Missing or duplicate security key on selected date")
        panel[d][code] = (positive(r["open"]),positive(r["close"]))
    result = evaluate(panel,days,signals,a.k,a.label)
    digest = hashlib.sha256()
    with a.input.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            digest.update(block)
    result["input_sha256"] = digest.hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("x",encoding="utf-8") as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2,allow_nan=False)
    print("Saved descriptive report:",a.output)


if __name__ == "__main__":
    main()
