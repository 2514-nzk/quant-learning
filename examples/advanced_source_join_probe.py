#!/usr/bin/env python3
"""Read-only root-cause probe for 2024 A-share universe-to-daily joins.

Public mode uses frozen aggregate evidence only. Private mode requires TWO
explicit local paths (--source-db and --parquet), verifies the 2024 snapshot
SHA-256, and opens the source DuckDB read-only. No source rows are uploaded,
no database or Parquet is modified, and no candidate alias is silently patched.

A match through comp_code is a CANDIDATE, not validated historical PIT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "advanced" / "volume-2" / "local_all_a_2024_aggregate.json"

# The evidence is explicitly for ONE frozen 2024 data partition. Other years
# need separate signed manifests and date-scoped tests.
YEAR_START, YEAR_END = "20240101", "20241231"

SOURCE_GROUPS_SQL = """
SELECT
  CASE WHEN ends_with(ts_code,'.BJ') THEN 'BJ'
       WHEN ends_with(ts_code,'.SH') THEN 'SH'
       WHEN ends_with(ts_code,'.SZ') THEN 'SZ'
       ELSE 'OTHER' END AS source_code_suffix,
  COUNT(*) AS observed_daily_rows,
  COUNT(DISTINCT ts_code) AS distinct_source_codes
FROM daily
WHERE trade_date BETWEEN ? AND ?
GROUP BY 1 ORDER BY 1
"""

DIAGNOSE_SQL = """
WITH missing AS (
    SELECT trade_date AS dt, code, comp_code, exchange,
           (trade_date=delist_date) AS on_delist_date,
           COALESCE(has_suspend_record, FALSE) AS source_suspend_flag
    FROM read_parquet(?)
    WHERE has_daily_quote=FALSE
),
source_daily AS (
    SELECT DISTINCT ts_code, trade_date
    FROM daily
    WHERE trade_date BETWEEN ? AND ?
),
direct_hit AS (
    SELECT m.code, m.dt, COUNT(d.ts_code) AS direct_n
    FROM missing m
    LEFT JOIN source_daily d ON d.ts_code=m.code
       AND d.trade_date=strftime(m.dt,'%Y%m%d')
    GROUP BY 1,2
),
known_aliases AS (
    SELECT DISTINCT comp_code, ts_code AS alias_code
    FROM stock_basic
    WHERE exchange='BSE' AND comp_code IS NOT NULL
      AND trim(comp_code)<>'' AND ends_with(ts_code,'.BJ')
),
alias_hit AS (
    SELECT m.code, m.dt, COUNT(DISTINCT d.ts_code) AS source_alias_n
    FROM missing m
    JOIN known_aliases a ON a.comp_code=m.comp_code
       AND a.alias_code<>m.code
    JOIN source_daily d ON d.ts_code=a.alias_code
       AND d.trade_date=strftime(m.dt,'%Y%m%d')
    WHERE m.exchange='BJ'
    GROUP BY 1,2
),
status AS (
    SELECT m.exchange,m.dt,m.code,m.on_delist_date,m.source_suspend_flag,
           COALESCE(d.direct_n,0) AS direct_n,
           COALESCE(a.source_alias_n,0) AS source_alias_n
    FROM missing m
    LEFT JOIN direct_hit d ON d.code=m.code AND d.dt=m.dt
    LEFT JOIN alias_hit a ON a.code=m.code AND a.dt=m.dt
),
classified AS (
    SELECT exchange,dt,code,source_suspend_flag,
       CASE
         WHEN direct_n>0 THEN 'SOURCE_DIRECT_PRESENT_SNAPSHOT_JOIN_MISSED'
         WHEN source_alias_n>1 THEN 'AMBIGUOUS_COMP_CODE_ALIASES'
         WHEN source_alias_n=1 THEN 'COMP_CODE_ALIAS_CANDIDATE'
         WHEN exchange IN ('SH','SZ') AND on_delist_date
             THEN 'DELIST_DATE_MEMBER_ENDPOINT'
         WHEN source_suspend_flag
             THEN 'SUSPEND_SOURCE_FLAG_NEEDS_VENUE_CHECK'
         ELSE 'NO_MATCH_IN_CURRENT_SOURCE_DAILY'
       END AS status
    FROM status
)
SELECT exchange,status,COUNT(*) AS security_days,
       SUM(CASE WHEN source_suspend_flag THEN 1 ELSE 0 END)
           AS source_suspend_flag_rows
FROM classified GROUP BY 1,2 ORDER BY 1,2
"""

# Direct and candidate alias source keys for three already public examples.
# Never emit raw private membership/company details outside these public cases.
PUBLIC_CASE_KEYS_SQL = """
WITH example AS (
  SELECT trade_date AS dt, code, comp_code
  FROM read_parquet(?)
  WHERE trade_date='2024-06-21'
    AND code IN ('920002.BJ','920806.BJ','920001.BJ')
),
aliases AS (
  SELECT e.code AS member_code, e.dt, b.ts_code AS source_code
  FROM example e
  JOIN stock_basic b ON b.comp_code=e.comp_code
  WHERE b.exchange='BSE' AND ends_with(b.ts_code,'.BJ')
)
SELECT a.member_code, a.source_code,
       COUNT(d.ts_code) AS source_daily_rows
FROM aliases a
LEFT JOIN daily d
  ON d.ts_code=a.source_code
 AND d.trade_date=strftime(a.dt,'%Y%m%d')
GROUP BY 1,2 ORDER BY 1,2
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_one(*, exchange: str, direct_source: bool, alias_count: int,
                 on_delist_date: bool, suspend_flag: bool) -> str:
    """Pure contract for status priorities, independently tested."""
    if direct_source:
        return "SOURCE_DIRECT_PRESENT_SNAPSHOT_JOIN_MISSED"
    if alias_count > 1:
        return "AMBIGUOUS_COMP_CODE_ALIASES"
    if alias_count == 1:
        return "COMP_CODE_ALIAS_CANDIDATE"
    if exchange in ("SH", "SZ") and on_delist_date:
        return "DELIST_DATE_MEMBER_ENDPOINT"
    if suspend_flag:
        return "SUSPEND_SOURCE_FLAG_NEEDS_VENUE_CHECK"
    return "NO_MATCH_IN_CURRENT_SOURCE_DAILY"


def offline_report(evidence: dict[str, Any]) -> dict:
    a = evidence["year_2024"]["exchange_quote_rows"]
    f = evidence["followup_cause_audit"]
    total = sum(v["quote_missing"] for v in a.values())
    if total != 60515 or f["sh_sz_unjoined_count"] != 52:
        raise ValueError("Frozen evidence mismatched; abort")
    if f.get("bj_2024_suspend_record_rows") != 19:
        raise ValueError("2024 BJ suspension marker audit missing")
    if f.get("bj_2024_unknown_trading_rows") != 60444:
        raise ValueError("2024 BJ unknown trading marker audit missing")
    return {
        "mode": "PUBLIC_FROZEN_COUNTS_ONLY",
        "total_snapshot_unjoined": total,
        "sh_sz_on_delist_date": f["sh_sz_unjoined_count"],
        "bj_with_suspend_source_flag": f["bj_2024_suspend_record_rows"],
        "bj_trading_status_unknown": f["bj_2024_unknown_trading_rows"],
        "bj_total_unjoined": f["bj_unjoined_count"],
        "source_daily_table_directly_inspected": False,
        "source_join_root_cause_confirmed": False,
        "real_market_no_trade_inferred": False,
        "historical_pit_verified": False,
    }


def probe_private_db(db: Path, parquet: Path, evidence: dict[str, Any],
                     *, enforce_hash: bool = True) -> dict:
    """Every query is SELECT, using DuckDB's read-only connection."""
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Optional private-source audit needs: pip install duckdb") from exc
    if not db.is_file() or not parquet.is_file():
        raise FileNotFoundError("Both local source DuckDB and frozen Parquet must exist")
    if enforce_hash:
        actual = sha256_file(parquet)
        if actual != evidence["year_2024"]["sha256"]:
            raise ValueError("Frozen 2024 Parquet SHA-256 does not match source manifest")
    con = duckdb.connect(str(db), read_only=True)
    try:
        source = con.execute(SOURCE_GROUPS_SQL, [YEAR_START, YEAR_END]).fetchall()
        rows = con.execute(DIAGNOSE_SQL, [str(parquet), YEAR_START, YEAR_END]).fetchall()
        public = con.execute(PUBLIC_CASE_KEYS_SQL, [str(parquet)]).fetchall()
    finally:
        con.close()
    out = {
        "mode": "PRIVATE_READ_ONLY_SOURCE_JOIN_DIAGNOSIS",
        "source_daily_code_suffix_counts": [
            {"suffix": suffix, "daily_rows": n, "distinct_codes": ncode}
            for suffix, n, ncode in source
        ],
        "snapshot_unjoined_by_cause": [
            {"exchange": exchange, "classification": status,
             "security_days": n, "source_suspend_flag_rows": suspend}
            for exchange, status, n, suspend in rows
        ],
        "public_case_source_keys": [
            {"member_code": member, "source_code": alias,
             "source_daily_rows": n}
            for member, alias, n in public
        ],
        "source_daily_table_directly_inspected": True,
        "source_db_opened_read_only": True,
        "frozen_parquet_sha_matched": bool(enforce_hash),
        "source_join_root_cause_confirmed": False,
        "historical_pit_verified": False,
        "source_2024_publication_timestamps_verified": False,
        "raw_private_rows_exported": False,
        "note": "Aliases are unverified identity candidates; source DB may itself "
                "lack complete historical daily records. Rebuild only after evidence review.",
    }
    total = sum(x["security_days"] for x in out["snapshot_unjoined_by_cause"])
    expected = sum(x["quote_missing"]
                   for x in evidence["year_2024"]["exchange_quote_rows"].values())
    if total != expected:
        raise ValueError(f"Unjoined rows changed: source probe {total}, frozen {expected}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-db", type=Path, help="private LOCAL xc_tushare DuckDB")
    ap.add_argument("--parquet", type=Path, help="matching frozen 2024 member Parquet")
    ap.add_argument("--output", type=Path, help="optional new report; refuses overwrite")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if bool(args.source_db) != bool(args.parquet):
        ap.error("--source-db and --parquet must be supplied together")
    report = (probe_private_db(args.source_db, args.parquet, evidence)
              if args.source_db else offline_report(evidence))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as sink:
            json.dump(report, sink, ensure_ascii=False, indent=2)
            sink.write("\n")
        print(f"Report written: {args.output}")
    elif args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Mode:", report["mode"])
        print("Source daily directly inspected:",
              report["source_daily_table_directly_inspected"])
        print("Do not edit/patch source data based on unverified aliases.")


if __name__ == "__main__":
    main()
