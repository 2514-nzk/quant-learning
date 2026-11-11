#!/usr/bin/env python3
"""Read the checked-in *real* AKShare historical daily bars without installing pandas.

This is a teaching exercise, not a trading signal or a total-return backtest.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {"000001": "平安银行", "600519": "贵州茅台", "300750": "宁德时代"}


def explain(symbol: str, date: str | None = None, root: Path = ROOT) -> dict:
    if symbol not in SAMPLES:
        raise ValueError("Only 000001, 600519 and 300750 are in this fixed teaching snapshot")
    path = root / "data" / "real_a_share" / f"{symbol}.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 20:
        raise ValueError("A 20-day moving average requires at least 20 records")
    days = [r["trade_date"] for r in rows]
    if days != sorted(set(days)):
        raise ValueError("Dates must be unique and increasing")
    if date is None:
        i = len(rows) - 1
    else:
        if date not in days:
            raise ValueError(f"{date} is not a recorded trading day for {symbol}")
        i = days.index(date)
    if i < 19:
        raise ValueError("Choose a date with at least 20 complete trading-day records")
    selected = rows[i]
    closes = [float(r["close"]) for r in rows]
    o, h, l, c = (float(selected[k]) for k in ("open", "high", "low", "close"))
    if l > min(o, c) or h < max(o, c):
        raise ValueError("Invalid K line OHLC")
    return {
        "name": SAMPLES[symbol], "symbol": symbol, "date": selected["trade_date"],
        "open": o, "high": h, "low": l, "close": c,
        "ma5": sum(closes[i-4:i+1]) / 5,
        "ma20": sum(closes[i-19:i+1]) / 20,
        "mom5_pct": (closes[i] / closes[i-5] - 1) * 100,
        "volume_lots": float(selected["volume_lots"]),
        "turnover_pct": float(selected["turnover_pct"]) if selected["turnover_pct"] else None,
        "note": "Historical unadjusted bars; not total return or guaranteed fill prices",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", choices=list(SAMPLES), default="000001")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD, default final recorded day")
    args = parser.parse_args()
    result = explain(args.symbol, args.date)
    print(f"真实日 K 线：{result['name']} ({result['symbol']}) / {result['date']}")
    print("开 {open:.2f}　高 {high:.2f}　低 {low:.2f}　收 {close:.2f} 元".format(**result))
    print("MA5 {ma5:.3f} 元　MA20 {ma20:.3f} 元　MOM5 {mom5_pct:+.2f}%".format(**result))
    print(f"成交量 {result['volume_lots']:,.2f} 手")
    print("注意：不复权日线仅用于读图和计算，不是含分红的真实总收益。")


if __name__ == "__main__":
    main()
