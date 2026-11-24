#!/usr/bin/env python3
"""Date-balanced ridge and simple baselines on a user-supplied local panel.
No downloads or upload; descriptive research, not executable account returns.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean

if __package__:
    from .cross_section_daily_research import rows, day, positive, rank_ic, file_sha
else:
    from cross_section_daily_research import rows, day, positive, rank_ic, file_sha

FEATURES = ("REV5","REV20","MOM60","LOWVOL5","LOWREL_VOL")
MODELS = FEATURES + ("EQUAL5","RIDGE")
LAMBDAS = (.01,.1,1.,10.)
MONTHS = (2,4,6,8,10,11)
D = len(FEATURES)


def standardize(raw):
    if len(raw)<2:
        return None
    mu = [mean(r[1][j] for r in raw) for j in range(D)]
    sd = [math.sqrt(mean((r[1][j]-mu[j])**2 for r in raw)) for j in range(D)]
    if any(not math.isfinite(v) or v<=0 for v in sd):
        return None
    return [(code,[(v-m)/s for v,m,s in zip(x,mu,sd)],y) for code,x,y in raw]


def spec(days,t):
    i=days.index(t)
    if i<60 or i+6>=len(days):
        raise ValueError("Insufficient calendar around "+t)
    return [days[i-60],days[i-20],*days[i-5:i+1],days[i+1],days[i+6]]


def group(panel,t,ds):
    base60,base20,*recent,entry,exit_=ds
    raw=[]
    for code,r in panel[t].items():
        p60=panel[base60].get(code,(None,None,None))[1]
        p20=panel[base20].get(code,(None,None,None))[1]
        z=[panel[d].get(code,(None,None,None)) for d in recent]
        if p60 is None or p20 is None or any(v[1] is None or v[2] is None for v in z):
            continue
        ret=[math.log(b[1]/a[1]) for a,b in zip(z,z[1:])]
        mu=mean(ret)
        vol=math.sqrt(mean((v-mu)**2 for v in ret))
        c=r[1]
        x=[1-c/z[0][1],1-c/p20,c/p60-1,-vol,
           -math.log(r[2]/mean(v[2] for v in z[:-1]))]
        if not all(math.isfinite(v) for v in x):
            continue
        buy=panel[entry].get(code,(None,None,None))[0]
        sell=panel[exit_].get(code,(None,None,None))[0]
        y=sell/buy-1 if buy is not None and sell is not None else None
        if y is not None and not math.isfinite(y):
            y=None
        raw.append((code,x,y))
    z=standardize(raw)
    return {"signal":t,"entry":entry,"exit":exit_,"rows":z or [],
            "feature_valid_before_standardization":len(raw),
            "status":"OK" if z is not None else "NO_VALID_VARIATION"}


def split_groups(groups,validation_year,test_year):
    v=f"{validation_year:04d}-01-01"
    t=f"{test_year:04d}-01-01"
    if v>=t:
        raise ValueError("Validation must precede test")
    train,val,test,purged=[],[],[],[]
    for g in sorted(groups,key=lambda g:g["signal"]):
        if g["signal"]<v:
            (train if g["exit"]<v else purged).append(g)
        elif g["signal"]<t:
            (val if g["exit"]<t else purged).append(g)
        else:
            test.append(g)
    return train,val,test,purged


def fit(groups,lam):
    if not math.isfinite(lam) or lam<=0:
        raise ValueError("Positive regularization required")
    G=[[0.]*D for _ in range(D)]
    h=[0.]*D
    n=0
    for g in groups:
        pairs=[(x,y) for _,x,y in g["rows"] if y is not None]
        if len(pairs)<2:
            continue
        ybar=mean(y for x,y in pairs)
        n+=1
        for x,y in pairs:
            for i in range(D):
                h[i]+=x[i]*(y-ybar)/len(pairs)
                for j in range(D):
                    G[i][j]+=x[i]*x[j]/len(pairs)
    if not n:
        raise ValueError("No training groups with paired labels")
    a=[[G[i][j]/n+(lam if i==j else 0) for j in range(D)]+[h[i]/n]
       for i in range(D)]
    for i in range(D):
        pivot=max(range(i,D),key=lambda j:abs(a[j][i]))
        a[i],a[pivot]=a[pivot],a[i]
        den=a[i][i]
        if abs(den)<1e-14:
            raise ValueError("Singular ridge equations")
        a[i]=[v/den for v in a[i]]
        for j in range(D):
            if j!=i:
                w=a[j][i]
                a[j]=[x-w*y for x,y in zip(a[j],a[i])]
    return [r[-1] for r in a]


def avg(values):
    return mean(values) if values else None


def score(x,beta):
    return list(x)+[mean(x),sum(u*v for u,v in zip(x,beta))]


def compare(groups,beta,ks):
    rounds=[]
    for g in groups:
        scored=[(code,score(x,beta),y) for code,x,y in g["rows"]]
        paired=[r for r in scored if r[2] is not None]
        bench=avg([r[2] for r in paired])
        row={"signal":g["signal"],"exit":g["exit"],"status":g.get("status","OK"),
             "valid_scores":len(scored),"valid_labels":len(paired),
             "benchmark":bench,"models":{}}
        for j,name in enumerate(MODELS):
            order=sorted(scored,key=lambda r:(-r[1][j],r[0]))
            top=[]
            for k in ks:
                chosen=order[:k]
                labels=[r[2] for r in chosen if r[2] is not None]
                gross=avg(labels) if len(labels)==k else None
                top.append({"k":k,"selected":len(chosen),"valid_labels":len(labels),
                            "gross":gross,"excess":gross-bench if gross is not None else None})
            row["models"][name]={"rank_ic":rank_ic([r[1][j] for r in paired],[r[2] for r in paired]),
                                 "top":top}
        rounds.append(row)
    main=("REV20","EQUAL5","RIDGE")
    common=[r for r in rounds if all(p["gross"] is not None for f in main for p in r["models"][f]["top"])]
    def ic_for(name,rs):
        return avg([r["models"][name]["rank_ic"] for r in rs
                    if r["models"][name]["rank_ic"] is not None])
    return {"rounds":rounds,"mean_rank_ic":{f:ic_for(f,rounds) for f in MODELS},
            "positive_ic_count":{f:sum(r["models"][f]["rank_ic"] is not None and
                                      r["models"][f]["rank_ic"]>0 for r in rounds) for f in MODELS},
            "common_main_model_all_k_dates":[r["signal"] for r in common],
            "common_main_model_all_k":[{"k":k,"mean_excess":{
                f:avg([r["models"][f]["top"][j]["excess"] for r in common]) for f in main}}
                for j,k in enumerate(ks)],
            "by_year":[{"year":y,"signal_count":len(rs),
                        "mean_rank_ic":{f:ic_for(f,rs) for f in MODELS}}
                       for y in sorted({r["signal"][:4] for r in rounds})
                       for rs in [[r for r in rounds if r["signal"].startswith(y)]]]}


def run(groups,validation_year,test_year,ks):
    train,val,test,purged=split_groups(groups,validation_year,test_year)
    if not train or not val or not test:
        raise ValueError("Need train, validation and test date groups")
    candidates=[]
    for lam in LAMBDAS:
        beta=fit(train,lam)
        result=compare(val,beta,ks)
        ic=result["mean_rank_ic"]["RIDGE"]
        candidates.append({"lambda":lam,"beta":beta,"validation_mean_rank_ic":ic})
    usable=[c for c in candidates if c["validation_mean_rank_ic"] is not None]
    if not usable:
        raise ValueError("No valid validation IC")
    best=max(usable,key=lambda c:(c["validation_mean_rank_ic"],c["lambda"]))
    # No refit on validation or test labels after selecting the training model.
    return {"features":FEATURES,"candidates":candidates,"selected":best,
            "split":{name:{"dates":[g["signal"] for g in gs],
                           "valid_labels":sum(y is not None for g in gs for _,x,y in g["rows"])}
                     for name,gs in (("train",train),("validation",val),("test",test),("purged",purged))},
            "test":compare(test,best["beta"],ks),
            "evidence":"DESCRIPTIVE_LOCAL_TIME_HOLDOUT",
            "limitations":["input price and volume adjustment and membership not verified",
                           "calendar derived from observed dates, not independent exchange calendar",
                           "historical information availability beyond exit date not verified",
                           "no execution, costs, capacity or independent untouched OOS claim",
                           "low relative volume is not cross-sectional liquidity or capacity"]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--start-year",type=int,required=True)
    p.add_argument("--end-year",type=int,required=True)
    p.add_argument("--validation-year",type=int,required=True)
    p.add_argument("--test-year",type=int,required=True)
    p.add_argument("--date-column",default="trade_date")
    p.add_argument("--code-column",default="ts_code")
    p.add_argument("--k",nargs="+",type=int,default=[10,20,30,50])
    a=p.parse_args()
    if not a.start_year<a.validation_year<a.test_year<=a.end_year:
        p.error("Require chronological train, validation, test years")
    if min(a.k)<1 or len(a.k)!=len(set(a.k)):
        p.error("Require positive unique K")
    if a.input.resolve()==a.output.resolve() or a.output.exists():
        p.error("Choose a new output file")
    days=sorted({day(r[a.date_column]) for r in rows(a.input,[a.date_column])})
    signals=[]
    for year in range(a.start_year,a.end_year+1):
        for month in MONTHS:
            prefix=f"{year:04d}-{month:02d}"
            dates=[d for d in days if d.startswith(prefix)]
            if not dates:
                raise ValueError("Missing signal month "+prefix)
            signals.append(dates[-1])
    specs={t:spec(days,t) for t in signals}
    panel={d:{} for d in {d for ds in specs.values() for d in ds}}
    for r in rows(a.input,[a.date_column,a.code_column,"open","close","volume"]):
        d=day(r[a.date_column])
        if d not in panel:
            continue
        code=str(r[a.code_column]).strip() if r[a.code_column] is not None else ""
        if not code or code in panel[d]:
            raise ValueError("Missing or duplicate security/date key")
        panel[d][code]=tuple(positive(r[k]) for k in ("open","close","volume"))
    result=run([group(panel,t,ds) for t,ds in specs.items()],a.validation_year,a.test_year,a.k)
    result["input_sha256"]=file_sha(a.input)
    result["protocol"]={"months":MONTHS,"label":"next_open_5","ks":a.k}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("x",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print("Saved local descriptive ridge report:",a.output)


if __name__=="__main__":
    main()
