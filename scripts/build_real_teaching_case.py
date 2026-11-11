#!/usr/bin/env python3
"""Create a deterministic, real-price four-stock teaching exercise.

No synthetic OHLC, earnings or model scores are substituted for market data.
The small four-name sample is NOT a point-in-time market universe or a tested alpha.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "real_a_share"
STOCKS = {
    "600519": "贵州茅台",
    "688256": "寒武纪",
    "300750": "宁德时代",
    "002594": "比亚迪",
}
BUDGET = 1_000_000
SIGNAL_DATE = "2024-06-21"
ROUND_STEP = 6
HORIZON = 5


def load_bars(root: Path = DATA) -> dict[str, dict[str, dict]]:
    result = {}
    for symbol in STOCKS:
        file = root / f"{symbol}.csv"
        with file.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        values = {}
        for row in rows:
            day = row["trade_date"]
            if day in values:
                raise ValueError(f"Duplicate day {day} for {symbol}")
            o, h, l, c = (float(row[x]) for x in ("open", "high", "low", "close"))
            if not all(math.isfinite(v) and v > 0 for v in (o, h, l, c)):
                raise ValueError("Nonfinite or zero price")
            if h < max(o,c) or l > min(o,c):
                raise ValueError(f"Bad bar {symbol} {day}")
            values[day] = {
                "date":day, "open":o, "high":h, "low":l, "close":c,
                "volume_lots":float(row["volume_lots"]),
            }
        result[symbol] = values
    return result


def round_to_money(value: float) -> float:
    return round(value + 1e-9, 2)


def calculate_case(bars: dict[str, dict[str, dict]]) -> dict:
    # Intersect existing exchange-trading days to avoid comparing mismatched dates
    # if the source contains a suspension or missing daily bar.
    days = sorted(set.intersection(*(set(v) for v in bars.values())))
    if SIGNAL_DATE not in days:
        raise ValueError("A known example signal date is missing from the data")
    fixed = days.index(SIGNAL_DATE)
    if fixed + HORIZON >= len(days):
        raise ValueError("Need five future trading days after the fixed signal date")
    positions = list(range(fixed, 4, -ROUND_STEP))[::-1]
    round_data = []
    for number, idx in enumerate(positions, start=1):
        signal, entry, exit_ = days[idx], days[idx + 1], days[idx + HORIZON]
        entries = []
        for symbol, name in STOCKS.items():
            s, p, e, x = (
                bars[symbol][signal], bars[symbol][days[idx-5]],
                bars[symbol][entry], bars[symbol][exit_]
            )
            mom = s["close"] / p["close"] - 1
            future = x["close"] / e["open"] - 1
            ma5 = sum(bars[symbol][d]["close"] for d in days[idx-4:idx+1]) / 5
            entries.append({
                "symbol": symbol, "name": name,
                "signal_date": signal,
                "momentum_base_date": days[idx-5],
                "momentum_base_close":p["close"],
                "signal_close": s["close"],
                "ma5": round(ma5, 6),
                "mom5": round(mom, 9),
                "entry_date":entry, "entry_open":e["open"],
                "exit_date":exit_, "exit_close":x["close"],
                "forward_return":round(future, 9),
                "signal_volume_lots":s["volume_lots"]
            })
        entries.sort(key=lambda z:(-z["mom5"],z["symbol"]))
        for index, row in enumerate(entries):
            row["rank"] = index + 1
            row["selected"] = index < 2
        gross = sum(e["forward_return"] for e in entries[:2]) / 2
        benchmark = sum(e["forward_return"] for e in entries) / 4
        # A 100-share lot example ignores commission and sell-side taxes.
        # It is a physically plausible execution quantity, *not* a fill guarantee.
        cash = BUDGET
        shares = {}
        for e in entries[:2]:
            planned = BUDGET / 2
            n = int(planned // (e["entry_open"] * 100)) * 100
            shares[e["symbol"]] = n
            cash -= n * e["entry_open"]
        real_lot_final = cash + sum(
            shares.get(e["symbol"], 0) * e["exit_close"] for e in entries[:2]
        )
        round_data.append({
            "round_id": number, "signal_date": signal,
            "entry_date": entry, "exit_date": exit_,
            "rows": entries,
            "top2_gross": round(gross, 9),
            "all4_gross": round(benchmark, 9),
            "theoretical_end":round_to_money(BUDGET * (1+gross)),
            "benchmark_end":round_to_money(BUDGET * (1+benchmark)),
            "lot_shares":shares,
            "lot_uninvested_cash":round_to_money(cash),
            "lot_end":round_to_money(real_lot_final),
            "lot_return":round(real_lot_final/BUDGET-1,9)
        })
    intro = round_data[-1]
    if intro["signal_date"] != SIGNAL_DATE:
        raise ValueError("Wrong example date")
    return {
        "type":"fixed real OHLC teaching exercise, unadjusted close and open",
        "stocks":STOCKS, "budget":BUDGET,
        "period":"2024-01-02 to 2024-06-28",
        "example_signal_date":SIGNAL_DATE,
        "intro":intro, "rounds":round_data,
        "limitations": [
            "Named companies were chosen retrospectively: this is not an unbiased historical stock universe",
            "Uses unadjusted daily data; does not include dividends or stock splits in wealth returns",
            "Top-2 is a deliberately simple teaching rule, not a validated tradable signal",
            "Lot illustration is a quantity check, not an actual order fill, commission or tax ledger",
            "Only a few non-overlapping historical periods, too few for stable model generalization",
            "All inputs use the closing price after the signal day ended, trading only the next open"
        ],
    }


def write_case(case: dict, output: Path = DATA) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output/"teaching_case.json").write_text(
        json.dumps(case,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    columns = [
        "round_id","signal_date","entry_date","exit_date","symbol","name",
        "rank","selected","momentum_base_date","momentum_base_close",
        "signal_close","ma5","mom5","entry_open","exit_close",
        "forward_return","signal_volume_lots"
    ]
    with (output/"teaching_rounds.csv").open("w",encoding="utf-8",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=columns,lineterminator="\n")
        writer.writeheader()
        for item in case["rounds"]:
            for stock in item["rows"]:
                writer.writerow({k:stock[k] if k in stock else item[k] for k in columns})


def main() -> None:
    case=calculate_case(load_bars())
    write_case(case)
    row=case["intro"]
    print(f"Real data: {len(case['rounds'])} complete nonoverlapping study periods")
    print(f"Signal {row['signal_date']}, enter {row['entry_date']}, exit {row['exit_date']}")
    for x in row["rows"]:
        print(f"  {x['name']}({x['symbol']}): MOM5 {x['mom5']*100:+.2f}%, "
              f"entry {x['entry_open']:.2f}, exit {x['exit_close']:.2f}, "
              f"future {x['forward_return']*100:+.2f}%")
    print(f"Top-2 theoretical ending amount: {row['theoretical_end']:,.2f}")
    print(f"Top-2 by board lots, no fee: {row['lot_end']:,.2f}")
    print("Market sample is for teaching only, not a strategy efficacy claim")


if __name__ == "__main__":
    main()
