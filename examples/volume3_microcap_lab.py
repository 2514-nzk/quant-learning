#!/usr/bin/env python3
"""Volume III microcap lesson lab. Synthetic-only; standard library."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/teaching/volume3_microcap_synthetic_v1.json"
def load(path=DATA):
 x=json.loads(path.read_text(encoding="utf-8"))
 if x.get("dataset_id")!="volume3-microcap-synthetic-v1" or x.get("evidence_grade")!="SYNTHETIC_ONLY": raise ValueError("Only the frozen synthetic fixture is accepted")
 if len(x.get("rebalance_dates",[]))!=3: raise ValueError("Expected three teaching rebalances")
 return x
def run(data):
 holdings={}; reports=[]
 for date in data["rebalance_dates"]:
  rows=[r for r in data["observations"] if r["date"]==date]; eligible=[]
  for r in rows:
   if r["size_rank"]>data["rules"]["max_size_rank"] or r["listing_days"]<data["rules"]["min_listing_days"] or r["avg_amount_20d"]<data["rules"]["min_avg_amount_20d"]: continue
   if not r["financial_available_at"]<date+"T18:00:00+08:00" or r["accrual"] is None: continue
   eligible.append(r)
  primary=sorted(eligible,key=lambda r:(r["accrual"],r["security_id"]))[:5]
  selected={r["security_id"]:r for r in primary}; backup=[]
  if len(selected)<5:
   candidates=[r for r in eligible if r["security_id"] not in selected and r["resi5"] is not None]
   backup=sorted(candidates,key=lambda r:(-r["resi5"],r["security_id"]))[:5-len(selected)]
   selected.update({r["security_id"]:r for r in backup})
  targets={k:1/len(selected) for k in selected} if selected else {}; actual={};blocked=[]
  for sid,r in selected.items():
   if r["suspended"] or r["limit_down"]:
    if sid in holdings: actual[sid]=holdings[sid]
    blocked.append({"security_id":sid,"reason":"SUSPENDED" if r["suspended"] else "LIMIT_DOWN"})
   else: actual[sid]=targets[sid]
  for sid,w in holdings.items():
   if sid not in selected and sid in data["blocked_exits"].get(date,[]):
    actual[sid]=w;blocked.append({"security_id":sid,"reason":"EXIT_NOT_FILLED"})
  invested=sum(actual.values())
  if invested>1+1e-12: raise ValueError("Holdings exceed NAV")
  reports.append({"date":date,"eligible":[r["security_id"] for r in eligible],"primary":[r["security_id"] for r in primary],"resi5_backup":[r["security_id"] for r in backup],"target_weights":targets,"actual_weights":actual,"blocked_orders":blocked,"cash_weight":1-invested,"source_kind":"SYNTHETIC_ONLY"})
  holdings=actual
 return {"dataset_id":data["dataset_id"],"evidence_grade":"SYNTHETIC_ONLY","market_pit_proven":False,"real_OOS_proven":False,"execution_proven":False,"reports":reports}
def main():
 p=argparse.ArgumentParser();p.add_argument("--json",action="store_true");a=p.parse_args();x=run(load())
 if a.json: print(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True))
 else:
  for r in x["reports"]: print(r["date"],"primary=",r["primary"],"backup=",r["resi5_backup"],"cash=",round(r["cash_weight"],4))
if __name__=="__main__":main()
