#!/usr/bin/env python3
"""Collect a historical AKShare A-share learning snapshot and render honest SVG K lines.

- Fixed dates and known stocks; NOT a live feed or a backtest universe.
- Unadjusted daily OHLC prices; dividends/corporate actions are not included.
- Source, library version, timestamp and CSV checksums are written to manifest.
- AKShare must be installed to fetch; rendering itself uses only the stdlib.

Outputs:
  data/real_a_share/{symbol}.csv, manifest.json
  reader/assets/real-a-share/{symbol}.svg
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCKS = {
    "000001": "平安银行",
    "600519": "贵州茅台",
    "300750": "宁德时代",
}
START, END = "20240102", "20240628"
FIELDS = ["trade_date", "symbol", "name", "open", "high", "low", "close",
          "volume_lots", "amount_yuan", "turnover_pct"]
AMOUNT_FIELDS = ("成交额", "amount")
VOL_FIELDS = ("成交量", "volume")


def number(raw, field: str, allow_empty: bool = False) -> float | None:
    if raw is None or str(raw).strip() in ("", "nan", "None"):
        if allow_empty:
            return None
        raise ValueError(f"Missing {field}")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"Non-finite {field}: {raw!r}")
    return value


def standardized_rows(df, symbol: str, name: str, source: str) -> list[dict]:
    """Normalize dataframe rows with explicit source-dependent volume units."""
    chinese = source == "akshare.stock_zh_a_hist"
    fields = {
        "date": "日期" if chinese else "date",
        "open": "开盘" if chinese else "open",
        "high": "最高" if chinese else "high",
        "low": "最低" if chinese else "low",
        "close": "收盘" if chinese else "close",
        "volume": "成交量" if chinese else "volume",
        "amount": "成交额" if chinese else "amount",
        "turnover": "换手率" if chinese else "turnover",
    }
    required = [fields[key] for key in ("date", "open", "high", "low", "close", "volume")]
    missing = [field for field in required if field not in df.columns]
    if missing:
        raise ValueError(f"{symbol} missing columns: {missing}")
    first, last = date.fromisoformat("2024-01-02"), date.fromisoformat("2024-06-28")
    result = []
    for raw in df.to_dict("records"):
        day = date.fromisoformat(str(raw[fields["date"]])[:10])
        if not first <= day <= last:
            continue
        o, h, l, c = (number(raw[fields[key]], key) for key in ("open", "high", "low", "close"))
        if min(o, h, l, c) <= 0 or l > min(o, c) or h < max(o, c) or h < l:
            raise ValueError(f"Invalid OHLC at {symbol}/{day}: {o},{h},{l},{c}")
        volume = number(raw[fields["volume"]], "volume")
        if volume < 0:
            raise ValueError("Negative volume")
        # AKShare Eastmoney 成交量 is lots (手); Sina daily volume is shares (股).
        lots = volume if chinese else volume / 100.0
        amount = number(raw.get(fields["amount"]), "amount", allow_empty=True)
        turnover = number(raw.get(fields["turnover"]), "turnover", allow_empty=True)
        if amount is not None and amount < 0:
            raise ValueError("Negative turnover amount")
        result.append({
            "trade_date": day.isoformat(), "symbol": symbol, "name": name,
            "open": f"{o:.3f}", "high": f"{h:.3f}", "low": f"{l:.3f}", "close": f"{c:.3f}",
            "volume_lots": f"{lots:.2f}",
            "amount_yuan": "" if amount is None else f"{amount:.2f}",
            "turnover_pct": "" if turnover is None else f"{turnover:.4f}",
        })
    result.sort(key=lambda x: x["trade_date"])
    if len(result) < 45:
        raise ValueError(f"{symbol} only {len(result)} days; expected >= 45")
    if len(set(x["trade_date"] for x in result)) != len(result):
        raise ValueError(f"{symbol} duplicated trading day")
    return result


def collect_one(ak, symbol: str, name: str) -> tuple[list[dict], str]:
    providers = [
        ("akshare.stock_zh_a_hist", lambda: ak.stock_zh_a_hist(
            symbol=symbol, period="daily", start_date=START, end_date=END,
            adjust="", timeout=20,
        )),
        ("akshare.stock_zh_a_daily", lambda: ak.stock_zh_a_daily(
            symbol=("sh" if symbol.startswith("6") else "sz") + symbol,
            start_date="2024-01-02", end_date="2024-06-28", adjust="",
        )),
    ]
    errors = []
    for label, supplier in providers:
        for attempt in range(2):
            try:
                frame = supplier()
                rows = standardized_rows(frame, symbol, name, label)
                print(f"{symbol} {name}: {len(rows)} rows via {label}", flush=True)
                return rows, label
            except Exception as exc:
                errors.append(f"{label}: {type(exc).__name__}: {exc}")
                print(f"{symbol} {label} attempt {attempt + 1} failed: {exc}", flush=True)
                time.sleep(2)
    raise RuntimeError(f"Could not obtain {symbol}; " + "; ".join(errors))


def moving_average(data: list[float], period: int) -> list[float | None]:
    values = []
    for i in range(len(data)):
        values.append(sum(data[i - period + 1:i + 1]) / period if i + 1 >= period else None)
    return values


def render_svg(rows: list[dict], symbol: str, name: str, provider: str) -> str:
    """Safe static chart: last 55 candles, using only historical prices."""
    view = rows[-55:]
    W, H = 1080, 588
    L, R, T, B = 78, 1025, 118, 418
    VT, VB = 468, 538
    opens, highs, lows, closes = [
        [float(r[k]) for r in view] for k in ("open", "high", "low", "close")
    ]
    volumes = [float(r["volume_lots"]) for r in view]
    lower, upper = min(lows), max(highs)
    pad = max((upper - lower) * .08, .2)
    lower -= pad
    upper += pad
    def py(price):
        return B - (price - lower) / (upper - lower) * (B - T)
    def px(i):
        return L + (i + .5) * (R - L) / len(view)
    def fmt(v):
        return f"{v:,.2f}"
    red, green, orange, blue = "#cf5651", "#249777", "#d39035", "#537ca5"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(name)} {symbol} 历史日K线与成交量">',
        '<rect x="0" y="0" width="1080" height="588" fill="#fbfbf8" rx="13"/>',
        f'<text x="{L}" y="42" font-family="sans-serif" font-size="24" fill="#172b2a" font-weight="700">{html.escape(name)} · {symbol}</text>',
        '<text x="78" y="68" font-family="sans-serif" font-size="12" fill="#687b79">2024 上半年真实日线 · 不复权 · 红涨绿跌 · 图形仅供教学</text>',
        f'<text x="{R}" y="44" text-anchor="end" font-size="14" font-family="sans-serif" fill="#253e39">末日 {view[-1]["trade_date"]}  收 {fmt(closes[-1])} 元</text>',
        f'<text x="{L}" y="95" font-size="12" font-family="sans-serif" fill="{orange}">━ MA5</text>',
        f'<text x="{L+85}" y="95" font-size="12" font-family="sans-serif" fill="{blue}">━ MA20</text>',
        f'<text x="{L+180}" y="95" font-size="12" font-family="sans-serif" fill="#758582">│ 当日高低价　▮ 开收盘价</text>',
    ]
    for j in range(5):
        price = lower + (upper - lower) * j / 4
        y = py(price)
        parts.append(f'<line x1="{L}" x2="{R}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e2e9e5"/>')
        parts.append(f'<text x="{L-12}" y="{y+4:.1f}" text-anchor="end" fill="#647775" font-size="11" font-family="sans-serif">{fmt(price)}</text>')
    step = (R - L) / len(view)
    body_width = min(11, max(5, step * .65))
    max_volume = max(volumes) or 1
    for i, (o, h, l, c, volume) in enumerate(zip(opens, highs, lows, closes, volumes)):
        x, color = px(i), red if c >= o else green
        parts.append(f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{py(h):.2f}" y2="{py(l):.2f}" stroke="{color}" stroke-width="1.35"/>')
        top, bottom = py(max(o,c)), py(min(o,c))
        parts.append(f'<rect x="{x-body_width/2:.2f}" y="{top:.2f}" width="{body_width:.2f}" height="{max(1.6,bottom-top):.2f}" fill="{color}" rx=".7"/>')
        vh = volume / max_volume * (VB - VT)
        parts.append(f'<rect x="{x-body_width/2:.2f}" y="{VB-vh:.2f}" width="{body_width:.2f}" height="{vh:.2f}" fill="{color}" opacity=".65"/>')
    closes_full = [float(r["close"]) for r in rows]
    offset = len(rows) - len(view)
    for period, color in ((5, orange), (20, blue)):
        avg = moving_average(closes_full, period)[offset:]
        points = " ".join(f"{px(i):.2f},{py(value):.2f}" for i,value in enumerate(avg) if value is not None)
        if points:
            parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append(f'<line x1="{L}" x2="{R}" y1="{VB}" y2="{VB}" stroke="#c4d2cd"/>')
    parts.append(f'<text x="{L}" y="{VT-8}" font-size="11" fill="#647775" font-family="sans-serif">成交量（手）</text>')
    for k in range(6):
        idx = min(len(view)-1, round(k * (len(view)-1) / 5))
        parts.append(f'<text x="{px(idx):.2f}" y="557" text-anchor="middle" font-size="11" fill="#647775" font-family="sans-serif">{view[idx]["trade_date"][5:]}</text>')
    note = f'原始日线：{view[0]["trade_date"]} ～ {view[-1]["trade_date"]}（可下载完整快照）　数据：AKShare / {provider.split(".")[-1]}　不含分红和真实成交'
    parts.append(f'<text x="{L}" y="579" font-size="10" fill="#6c7c79" font-family="sans-serif">{html.escape(note)}</text></svg>')
    return "\n".join(parts) + "\n"


def csv_text(rows: list[dict]) -> str:
    buff = io.StringIO(newline="")
    writer = csv.DictWriter(buff, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buff.getvalue()


def write_snapshot(output: Path, assets: Path, results, version: str) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    captured = datetime.now(timezone.utc).isoformat()
    manifest = {
        "kind": "historical daily A-share teaching snapshot",
        "captured_utc": captured,
        "retriever": "AKShare",
        "akshare_version": version,
        "start_date_requested": START,
        "end_date_requested": END,
        "adjust": "none",
        "price_unit": "CNY/share (unadjusted OHLC)",
        "volume_unit": "lots (手), normalized; 1 lot=100 shares for these examples",
        "notes": [
            "Sampled named stocks; not an unbiased backtest universe",
            "No dividends, corporate-action adjustments, survivorship handling or live execution",
            "Historical source may revise values: exact CSV sha256 included",
        ],
        "items": [],
    }
    for symbol, name, provider, rows in results:
        text = csv_text(rows)
        csv_path = output / f"{symbol}.csv"
        svg_path = assets / f"{symbol}.svg"
        csv_path.write_text(text, encoding="utf-8")
        svg_path.write_text(render_svg(rows, symbol, name, provider), encoding="utf-8")
        manifest["items"].append({
            "symbol": symbol, "name": name,
            "source": provider,
            "records": len(rows),
            "first_date": rows[0]["trade_date"],
            "last_date": rows[-1]["trade_date"],
            "csv_path": csv_path.as_posix(),
            "chart_path": svg_path.as_posix(),
            "csv_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        })
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/real_a_share")
    parser.add_argument("--assets", type=Path, default=ROOT / "reader/assets/real-a-share")
    args = parser.parse_args()
    import akshare as ak
    results = []
    for symbol, name in STOCKS.items():
        rows, provider = collect_one(ak, symbol, name)
        results.append((symbol, name, provider, rows))
    manifest = write_snapshot(args.output, args.assets, results, getattr(ak, "__version__", "unknown"))
    print(json.dumps([{k: item[k] for k in ("symbol", "records", "source", "csv_sha256")}
                      for item in manifest["items"]], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
