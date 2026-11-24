#!/usr/bin/env python3
"""Optional local AKShare daily snapshot; not a historical PIT universe."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbols(rows):
    out = {}
    for row in rows:
        code = str(row["symbol"]).strip()
        if not re.fullmatch(r"[03468]\d{5}", code):
            raise ValueError(f"Expected six-digit Shanghai/Shenzhen/Beijing A-share code: {code}")
        if code in out:
            raise ValueError(f"Duplicate code: {code}")
        out[code] = str(row.get("name", ""))
    if not out:
        raise ValueError("Empty security list")
    return out


def validate(frame, start, end, provider, adjust):
    if provider.endswith("_em"):
        fields = ("日期", "开盘", "最高", "最低", "收盘", "成交量")
    elif provider.endswith("_sina"):
        fields = ("date", "open", "high", "low", "close", "volume")
    else:
        raise ValueError(f"Unknown provider schema: {provider}")
    if not set(fields).issubset(frame.columns) or frame.empty:
        raise ValueError(f"Empty data or missing OHLCV columns from {provider}")
    seen = set()
    nonpositive = False
    for row in frame.to_dict("records"):
        day = str(row[fields[0]])[:10].replace("-", "")
        datetime.strptime(day, "%Y%m%d")
        if day in seen or not start <= day <= end:
            raise ValueError("Duplicate or out-of-range trade date")
        seen.add(day)
        o, h, low, c, volume = [float(row[key]) for key in fields[1:]]
        if not all(math.isfinite(v) for v in (o, h, low, c, volume)) or volume < 0:
            raise ValueError("Non-finite OHLCV or negative volume")
        if low > min(o, c) or h < max(o, c) or h < low:
            raise ValueError("Invalid OHLC ordering")
        if min(o, h, low, c) <= 0:
            nonpositive = True
            if adjust == "raw":
                raise ValueError("Nonpositive raw execution price")
    return min(seen), max(seen), nonpositive


def collect(ak, universe, universe_source, start, end, out, pause=0.5, attempts=3):
    out = Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Use a new or empty output directory; no overwrite")
    out.mkdir(parents=True, exist_ok=True)
    for folder in ("raw", "qfq"):
        (out / folder).mkdir()
    with (out / "universe.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["symbol", "name"])
        writer.writerows(universe.items())
    report = {
        "sources": ["akshare.stock_zh_a_hist_em", "akshare.stock_zh_a_hist_sina"],
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "started_at": stamp(),
        "start": start,
        "end": end,
        "universe_source": universe_source,
        "historical_pit_proven": False,
        "historical_dynamic_membership_proven": False,
        "adjustment_semantics": {
            "raw": "unadjusted quoted OHLC; use only with a separate corporate-action ledger for total-return research",
            "qfq": "current forward-adjusted snapshot; may be restated and is not a point-in-time price archive",
            "qfq_nonpositive_prices": "preserved and flagged; do not use nonpositive adjusted OHLC in price-ratio calculations",
        },
        "universe_sha256": digest(out / "universe.csv"),
        "items": [],
    }

    def save():
        temp = out / "manifest.tmp"
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(out / "manifest.json")

    save()
    for code in universe:
        for kind, adjust in (("raw", ""), ("qfq", "qfq")):
            errors = []
            providers = [
                (
                    "akshare.stock_zh_a_hist_em",
                    lambda: ak.stock_zh_a_hist_em(
                        symbol=code, period="daily", start_date=start, end_date=end, adjust=adjust
                    ),
                    "lots",
                    "percent",
                ),
            ]
            # Sina's historical endpoint is used only for Shanghai/Shenzhen;
            # Beijing A-share symbols stay on the Eastmoney provider.
            if code.startswith(("0", "3", "6")):
                providers.append((
                    "akshare.stock_zh_a_hist_sina",
                    lambda: ak.stock_zh_a_hist_sina(
                        symbol=("sh" if code.startswith("6") else "sz") + code,
                        period="daily", start_date=start, end_date=end, adjust=adjust,
                    ),
                    "shares",
                    "fraction",
                ))
            success = False
            for provider, fetch, volume_unit, turnover_unit in providers:
                for attempt in range(attempts):
                    try:
                        frame = fetch()
                        first, last, nonpositive = validate(frame, start, end, provider, kind)
                        path = out / kind / (code + ".csv")
                        temp = path.with_suffix(".tmp")
                        frame.to_csv(temp, index=False, encoding="utf-8")
                        temp.replace(path)
                        report["items"].append({
                            "symbol": code,
                            "adjust": kind,
                            "status": "OK",
                            "rows": len(frame),
                            "source": provider,
                            "volume_unit": volume_unit,
                            "turnover_unit": turnover_unit,
                            "contains_nonpositive_ohlc": nonpositive,
                            "first": first,
                            "last": last,
                            "path": str(path.relative_to(out)),
                            "sha256": digest(path),
                            "captured_at": stamp(),
                            "prior_errors": errors,
                        })
                        success = True
                        break
                    except Exception as exc:
                        errors.append(provider + ": " + type(exc).__name__ + ": " + str(exc)[:300])
                        if attempt + 1 < attempts:
                            time.sleep(pause * (attempt + 1))
                if success:
                    break
            if not success:
                report["items"].append({
                    "symbol": code, "adjust": kind, "status": "FAILED", "errors": errors
                })
            save()
            time.sleep(pause)
    by_code = {}
    for item in report["items"]:
        if item["status"] == "OK":
            by_code.setdefault(item["symbol"], set()).add(item["source"])
    report["mixed_provider_pairs"] = sorted(
        code for code, providers in by_code.items() if len(providers) > 1
    )
    report["finished_at"] = stamp()
    report["expected_files"] = 2 * len(universe)
    report["successful_files"] = sum(item["status"] == "OK" for item in report["items"])
    report["all_requests_succeeded"] = report["successful_files"] == report["expected_files"]
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbols-file", type=Path)
    group.add_argument("--current-csi300", action="store_true")
    parser.add_argument("--start", default="20160101")
    parser.add_argument("--end", default="20251231")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    start_date = datetime.strptime(args.start, "%Y%m%d")
    end_date = datetime.strptime(args.end, "%Y%m%d")
    if start_date > end_date:
        parser.error("start after end")
    import akshare as ak

    if args.current_csi300:
        getter = getattr(ak, "index_stock_cons_csindex", None)
        if not callable(getter):
            raise RuntimeError("AKShare lacks index_stock_cons_csindex; inspect ak.interface_info/search.")
        frame = getter(symbol="000300")
        universe = symbols([
            {"symbol": str(row["成分券代码"]).split(".")[0].zfill(6), "name": row.get("成分券名称", "")}
            for row in frame.to_dict("records")
        ])
        if len(universe) != 300:
            raise ValueError(f"Expected 300 current CSI300 constituents, got {len(universe)}")
        universe_source = {
            "type": "CURRENT_CSI300_RETROSPECTIVE_FIXED_SAMPLE",
            "captured_at": stamp(),
            "interface": "index_stock_cons_csindex",
            "historical_membership": False,
        }
    else:
        with args.symbols_file.open(encoding="utf-8-sig") as handle:
            universe = symbols(csv.DictReader(handle))
        universe_source = {
            "type": "USER_SUPPLIED_FIXED_LIST",
            "sha256": digest(args.symbols_file),
            "historical_membership": False,
        }
    report = collect(ak, universe, universe_source, args.start, args.end, args.out)
    print(json.dumps({
        key: report[key]
        for key in ("expected_files", "successful_files", "all_requests_succeeded")
    }))
    return 0 if report["all_requests_succeeded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
