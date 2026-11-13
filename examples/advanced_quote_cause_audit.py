#!/usr/bin/env python3
"""Distinguish stock-universe join misses from real zero trading.

No network by default. --akshare runs a few PUBLIC historical quote checks;
it does not read/send the private PTradePolicy database, query entire markets,
or infer a delisting-day trade from an empty remote response.

For an audited *private* source, verify the original daily table and
historical code mapping locally; this script alone cannot prove their contents.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "advanced" / "volume-2" / "local_all_a_2024_aggregate.json"
PUBLIC_REPORT = (
    "https://www.stcn.com/article/detail/1237416.html"
)
CASES = (
    {"date": "2024-06-21", "canonical_code": "920806",
     "historical_code": "873806", "name": "云星宇", "public_close": 9.44},
    {"date": "2024-06-21", "canonical_code": "920001",
     "historical_code": "873001", "name": "纬达光电", "public_close": 8.18},
    {"date": "2024-06-21", "canonical_code": "920002",
     "historical_code": "920002", "name": "万达轴承", "public_close": 52.01},
)


def extract_exact_date(response: Any, day: str) -> dict:
    """Return price only when returned data explicitly contains the target date."""
    if hasattr(response, "to_dict"):
        rows = response.to_dict(orient="records")
    elif isinstance(response, list):
        rows = response
    else:
        raise TypeError("AKShare response must be DataFrame or list-of-dicts")
    matching = [row for row in rows if str(row.get("日期", ""))[:10] == day]
    if len(matching) > 1:
        raise ValueError("duplicated date in external quote response")
    if not matching:
        return {"status": "NOT_RETURNED_CANNOT_INFER_HALTED_OR_DELISTED"}
    raw = matching[0].get("收盘")
    if raw is None:
        return {"status": "RETURNED_BUT_CLOSE_MISSING"}
    close = float(raw)
    if not 0 < close < 1_000_000:
        raise ValueError("invalid external closing price")
    return {"status": "PRICE_OBSERVED", "close": close}


def query_akshare(module: Any, symbol: str, day: str) -> dict:
    digits = day.replace("-", "")
    try:
        frame = module.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=digits, end_date=digits, adjust=""
        )
        return extract_exact_date(frame, day)
    except Exception as exc:
        return {"status": "API_ERROR_NOT_EVIDENCE_OF_NO_TRADE",
                "error_type": type(exc).__name__}


def fetch_case(module: Any, case: dict) -> dict:
    # Test both historical code and canonical code. An empty 920 response
    # cannot disprove a 2024 trade under 873/832/837 or other old symbols.
    symbols = list(dict.fromkeys([case["historical_code"], case["canonical_code"]]))
    outcomes = {symbol: query_akshare(module, symbol, case["date"])
                for symbol in symbols}
    confirmed = [dict(symbol=sym, close=out["close"])
                 for sym, out in outcomes.items() if out["status"] == "PRICE_OBSERVED"]
    matches_public = any(abs(out["close"]-case["public_close"]) < .011 for out in confirmed)
    return {
        **case, "attempted_symbols": symbols, "results": outcomes,
        "api_price_observed": bool(confirmed), "api_matches_2024_public_report":
            matches_public if confirmed else None,
        "interpretation": ("INDEPENDENT_QUOTE_PRESENT" if confirmed else
            "NOT_CONFIRMED_BY_API_QUERY_NO_ABSENCE_INFERENCE"),
    }


def offline_summary(evidence: dict) -> dict:
    row = evidence["followup_cause_audit"]
    if row["sh_sz_unjoined_count"] != 52 or row["sh_sz_all_equal_delist_date"] is not True:
        raise ValueError("SH/SZ delist-day evidence has changed")
    if row["sh_sz_suspend_record_true"] != 0:
        raise ValueError("SH/SZ suspension count disagrees with frozen evidence")
    if row["bj_unjoined_count"] != 60463:
        raise ValueError("BJ frozen join count changed")
    if row["public_quote_2024_06_21_source"] != PUBLIC_REPORT:
        raise ValueError("dated public quote reference changed")
    return {
        "evidence_grade": "JOIN_CAUSE_TRIAGE_NOT_PIT_AND_NOT_ALL_A_QUOTE_PROOF",
        "sh_sz_unjoined_and_equal_delist_day": row["sh_sz_unjoined_count"],
        "bj_unjoined": row["bj_unjoined_count"],
        "historical_code_switch_is_a_plausible_join_cause": True,
        "new_920_code_also_unjoined": True,
        "akshare_queried": False,
        "independent_daily_relation_key_audit_completed": False,
        "historical_pit_proven": False,
        "public_historical_sample_checks": list(CASES),
        "limitations": [
            "SH/SZ missing observations all coincide with snapshot's delist_date, "
            "but exact final executable trading dates still require exchange notices.",
            "Some BJ names switched their codes only in 2025, while 920002 "
            "already traded under 920 in June 2024. Mapping alone is insufficient.",
            "2024 public newspaper quotation is independent of local snapshot.",
            "AKShare live requests are optional and not run in CI; nonresponse "
            "is not proof that a security did not trade.",
            "Private source daily coverage and complete code history remain unverified.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--akshare", action="store_true",
                    help="perform optional public remote API calls; requires pip install akshare")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    payload = json.loads(EVIDENCE.read_text("utf-8"))
    report = offline_summary(payload)
    if args.akshare:
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError("Install AKShare locally: pip install akshare") from exc
        report["akshare_queried"] = True
        report["akshare_results"] = [fetch_case(ak, case) for case in CASES]
        report["independent_daily_relation_key_audit_completed"] = False
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print("SH/SZ unjoined on delist dates:",
              report["sh_sz_unjoined_and_equal_delist_day"])
        print("BJ unjoined in snapshot:", report["bj_unjoined"])
        print("AKShare queried:", report["akshare_queried"])
        print("Do not conflate failed daily join with true market non-trading.")


if __name__ == "__main__":
    main()
