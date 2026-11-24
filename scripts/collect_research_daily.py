#!/usr/bin/env python3
"""Optional, local-only AKShare daily snapshot; never claims historical PIT."""
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
    for r in rows:
        code = str(r["symbol"]).strip()
        if not re.fullmatch(r"[036]\d{5}", code):
            raise ValueError(f"Expected six-digit Shanghai/Shenzhen A-share code: {code}")
        if code in out:
            raise ValueError(f"Duplicate code: {code}")
        out[code] = str(r.get("name", ""))
    if not out:
        raise ValueError("Empty security list")
    return out


def validate(frame, start, end, source="akshare.stock_zh_a_hist"):
    fields = ("日期", "开盘", "最高", "最低", "收盘", "成交量") if source.endswith("hist") else ("date","open","high","low","close","volume")
    required = set(fields)
    if not required.issubset(frame.columns) or frame.empty:
        raise ValueError("Empty data or missing OHLCV columns")
    seen = set()
    for row in frame.to_dict("records"):
        day = str(row[fields[0]])[:10].replace("-", "")
        datetime.strptime(day,"%Y%m%d")
        if day in seen or not start <= day <= end:
            raise ValueError("Duplicate or out-of-range trade date")
        seen.add(day)
        o,h,l,c,v = [float(row[k]) for k in fields[1:]]
        if not all(math.isfinite(z) for z in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<0 or l>min(o,c) or h<max(o,c):
            raise ValueError("Invalid OHLCV")
    return min(seen),max(seen)


def collect(ak, universe, source, start, end, out, pause=.5, attempts=3):
    out = Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Use a new or empty output directory; no overwrite")
    out.mkdir(parents=True,exist_ok=True)
    for a in ("raw","hfq"):
        (out/a).mkdir()
    with (out/"universe.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(["symbol","name"]);w.writerows(universe.items())
    report={"sources":["akshare.stock_zh_a_hist","akshare.stock_zh_a_daily"],"akshare_version":getattr(ak,"__version__","unknown"),
            "started_at":stamp(),"start":start,"end":end,"universe_source":source,
            "historical_pit_proven":False,"historical_dynamic_membership_proven":False,
            "universe_sha256":digest(out/"universe.csv"),"items":[]}
    def save():
        tmp=out/"manifest.tmp"
        tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(out/"manifest.json")
    save()
    for code in universe:
        for kind,adjust in (("raw",""),("hfq","hfq")):
            errors=[]
            providers=[
                ("akshare.stock_zh_a_hist",lambda:ak.stock_zh_a_hist(symbol=code,period="daily",start_date=start,end_date=end,adjust=adjust,timeout=20)),
                ("akshare.stock_zh_a_daily",lambda:ak.stock_zh_a_daily(symbol=("sh" if code.startswith("6") else "sz")+code,start_date=start,end_date=end,adjust=adjust))
            ]
            success=False
            for provider,fetch in providers:
                for attempt in range(attempts):
                    try:
                        df=fetch()
                        first,last=validate(df,start,end,provider)
                        path=out/kind/(code+".csv")
                        temp=path.with_suffix(".tmp")
                        df.to_csv(temp,index=False,encoding="utf-8")
                        temp.replace(path)
                        report["items"].append(dict(symbol=code,adjust=kind,status="OK",rows=len(df),
                            source=provider, volume_unit="lots" if provider.endswith("hist") else "shares",
                            first=first,last=last,path=str(path.relative_to(out)),sha256=digest(path),
                            captured_at=stamp(),prior_errors=errors))
                        success=True
                        break
                    except Exception as e:
                        errors.append(provider+": "+type(e).__name__+": "+str(e)[:300])
                        if attempt+1<attempts: time.sleep(pause*(attempt+1))
                if success:break
            if not success:
                report["items"].append(dict(symbol=code,adjust=kind,status="FAILED",errors=errors))
            save()
            time.sleep(pause)
    by_code={}
    for item in report["items"]:
        if item["status"]=="OK":
            by_code.setdefault(item["symbol"],set()).add(item["source"])
    report["mixed_provider_pairs"]=[code for code,providers in by_code.items() if len(providers)>1]
    report["finished_at"]=stamp()
    report["expected_files"]=2*len(universe)
    report["successful_files"]=sum(r["status"]=="OK" for r in report["items"])
    report["all_requests_succeeded"]=report["successful_files"]==report["expected_files"]
    save()
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--symbols-file",type=Path)
    g.add_argument("--current-csi300",action="store_true")
    p.add_argument("--start",default="20160101")
    p.add_argument("--end",default="20251231")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    start,end=(datetime.strptime(x,"%Y%m%d") for x in (a.start,a.end))
    if start>end: p.error("start after end")
    import akshare as ak
    if a.current_csi300:
        df=ak.index_stock_cons_csindex(symbol="000300")
        universe=symbols([{"symbol":str(r["成分券代码"]).zfill(6),"name":r.get("成分券名称","")} for r in df.to_dict("records")])
        if len(universe)!=300: raise ValueError("Unexpected CSI300 member count; inspect source")
        source={"type":"CURRENT_CSI300_RETROSPECTIVE_FIXED_SAMPLE","captured_at":stamp(),
                "interface":"index_stock_cons_csindex","historical_membership":False}
    else:
        with a.symbols_file.open(encoding="utf-8-sig") as f: universe=symbols(csv.DictReader(f))
        source={"type":"USER_SUPPLIED_FIXED_LIST","sha256":digest(a.symbols_file),"historical_membership":False}
    report=collect(ak,universe,source,a.start,a.end,a.out)
    print(json.dumps({k:report[k] for k in ("expected_files","successful_files","all_requests_succeeded")}))
    return 0 if report["all_requests_succeeded"] else 1


if __name__=="__main__":
    raise SystemExit(main())
