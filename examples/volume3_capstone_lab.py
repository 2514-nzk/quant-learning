"""Third-volume classroom allocation, paper-order recovery and evidence gates.

Standard-library-only. No broker API, credentials, network or live orders.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rev20_classroom_lab import (make_panel, observe_week, SIGNALS, TOP, SESSIONS,
                                  signal_snapshot, feature_snapshot, simulate_account,
                                  account_attribution, spearman)

SOURCE = "SYNTHETIC_ONLY"
INITIAL = 1_000_000
POLICY = dict(sleeves=["rev20","mom5"], base_exposure=.95, daily_vol_target=.009,
              name_cap=.15, industry_cap=.30, trailing_sessions=20,
              participation=.05, drawdown_stress=.08)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",",":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def sd(values):
    m = mean(values)
    return math.sqrt(mean((v-m)**2 for v in values))


def sleeve_scores(panel, t):
    f = feature_snapshot(panel,t)
    return {name: sorted(f,key=lambda k:(-f[k][j],k))[:TOP]
            for j,name in enumerate(POLICY["sleeves"])}


def allocation_at(panel, t):
    """Only data through t. Risk forecast uses current baskets' historical returns,
    not the realized return history of a dynamically traded sleeve."""
    names = sleeve_scores(panel,t)
    if any(not b for b in names.values()):
        raise ValueError("empty sleeve")
    series = {s:[mean(panel[k]["close"][d]/panel[k]["close"][d-1]-1 for k in ks)
                 for d in range(t-19,t+1)] for s,ks in names.items()}
    vol = {s:sd(v) for s,v in series.items()}
    a,b = [series[s] for s in POLICY["sleeves"]]
    cov = mean((x-mean(a))*(y-mean(b)) for x,y in zip(a,b))
    corr = cov/(sd(a)*sd(b)) if sd(a)*sd(b) else None
    inv = {s:1/max(v,.001) for s,v in vol.items()}
    budgets = {s:v/sum(inv.values()) for s,v in inv.items()}
    def combined(budget):
        out = {}
        for s,ks in names.items():
            for k in ks:
                out[k] = out.get(k,0.)+budget[s]/len(ks)
        return out
    fixed = combined({s:.475 for s in names})
    raw = {k:min(v,POLICY["name_cap"]) for k,v in
           combined({s:.95*v for s,v in budgets.items()}).items()}
    for g in range(5):
        keys = [k for k in raw if panel[k]["industry"]==g]
        total = sum(raw[k] for k in keys)
        if total>POLICY["industry_cap"]:
            for k in keys:
                raw[k] *= POLICY["industry_cap"]/total
    hist = [sum(w*(panel[k]["close"][d]/panel[k]["close"][d-1]-1)
                for k,w in raw.items()) for d in range(t-19,t+1)]
    predicted = sd(hist)
    scale = min(1., POLICY["daily_vol_target"]/predicted) if predicted else 1.
    risk = {k:w*scale for k,w in raw.items()}
    # Stress is a fixed simultaneous -8% stock shock, not a tail probability.
    stress_loss = -POLICY["drawdown_stress"]*sum(risk.values())
    return dict(signal=t, sleeves=names, sleeve_vol=vol, sleeve_corr=corr,
                budgets=budgets, overlap=len(set(names["rev20"])&set(names["mom5"])),
                fixed=fixed,risk=risk,estimated_vol=predicted*scale,
                target_cash=1-sum(risk.values()),stress_return=stress_loss)


def allocation_report(panel=None):
    panel = make_panel() if panel is None else panel
    decisions = [allocation_at(panel,t) for t in SIGNALS[18:]]
    accounts = {s:simulate_account(panel,{d["signal"]:d[s] for d in decisions})
                for s in ("fixed","risk")}
    accounts["cash"] = simulate_account(panel,{d["signal"]:{} for d in decisions})
    return dict(decisions=decisions, accounts=accounts,
                attribution={s:account_attribution(panel,a) for s,a in accounts.items()},
                source_kind=SOURCE, policy=POLICY)


class PaperLedger:
    """Integer-cent ledger. Snapshot is a classroom persistence contract.

    A live system would require transactional durable storage, broker identifiers,
    atomic event/outbox handling, authentication and broker-specific reconciliation.
    """
    def __init__(self, snapshot=None):
        self.s = copy.deepcopy(snapshot) if snapshot is not None else dict(
            cash=1_000_000, holdings={}, available={}, orders={}, events={},
            session=1, frozen=False, freeze_reason=None, audit=[])
        self.check()

    def snapshot(self):
        return json.loads(json.dumps(self.s, sort_keys=True))

    def check(self):
        s=self.s
        if s["cash"]<0 or any(v<0 for v in s["holdings"].values()):
            raise ValueError("negative balance")
        for k,v in s["available"].items():
            if not 0<=v<=s["holdings"].get(k,0):
                raise ValueError("invalid sellable balance")
        if self.reserved_cash()>s["cash"]:
            raise ValueError("cash reservation exceeds balance")
        for k in s["holdings"]:
            if self.reserved_qty(k)>s["available"].get(k,0):
                raise ValueError("sell reservation exceeds availability")

    def active(self):
        return [o for o in self.s["orders"].values()
                if o["state"] in ("OPEN","PARTIAL","UNKNOWN")]

    def reserved_cash(self):
        return sum((o["qty"]-o["filled"])*o["limit"] for o in self.active() if o["side"]=="BUY")

    def reserved_qty(self,k):
        return sum(o["qty"]-o["filled"] for o in self.active() if o["side"]=="SELL" and o["code"]==k)

    def freeze(self,reason):
        self.s["frozen"]=True
        self.s["freeze_reason"]=reason
        self.s["audit"].append(["FREEZE",reason])

    def submit(self, key, code, side, qty, limit, data_session, expected_session):
        # Retry of exact intent returns original order, even if currently frozen.
        identity=dict(code=code,side=side,qty=qty,limit=limit,session=expected_session)
        if key in self.s["orders"]:
            o=self.s["orders"][key]
            if any(o[k]!=v for k,v in identity.items()):
                self.freeze("ORDER_ID_CONFLICT")
                return "CONFLICT"
            return "DUPLICATE"
        if self.s["frozen"]:
            return "FROZEN"
        if data_session!=expected_session or expected_session!=self.s["session"]:
            self.freeze("STALE_DATA")
            return "STALE_DATA"
        if (not isinstance(qty,int) or not isinstance(limit,int) or
            qty<=0 or qty%100 or limit<=0 or side not in ("BUY","SELL")):
            return "INVALID"
        if side=="BUY" and qty*limit>self.s["cash"]-self.reserved_cash():
            return "CASH_LIMIT"
        if side=="SELL" and qty>self.s["available"].get(code,0)-self.reserved_qty(code):
            return "T_PLUS_ONE_OR_RESERVED"
        self.s["orders"][key]=dict(**identity,filled=0,state="OPEN")
        self.s["audit"].append(["SUBMIT",key])
        self.check()
        return "ACCEPTED"

    def fill(self,event,key,qty,price):
        payload=[key,qty,price]
        if event in self.s["events"]:
            if self.s["events"][event]!=payload:
                self.freeze("FILL_ID_CONFLICT")
                return "CONFLICT"
            return "DUPLICATE"
        o=self.s["orders"].get(key)
        if (o is None or o["state"] not in ("OPEN","PARTIAL","UNKNOWN")
            or not isinstance(qty,int) or not isinstance(price,int)
            or qty<=0 or price<=0 or qty>o["qty"]-o["filled"]
            or (o["side"]=="BUY" and price>o["limit"])
            or (o["side"]=="SELL" and price<o["limit"])):
            self.freeze("UNEXPECTED_FILL")
            return "RECONCILE_REQUIRED"
        k=o["code"]
        if o["side"]=="BUY":
            self.s["cash"]-=qty*price
            self.s["holdings"][k]=self.s["holdings"].get(k,0)+qty
        else:
            self.s["cash"]+=qty*price
            self.s["holdings"][k]-=qty
            self.s["available"][k]-=qty
        o["filled"]+=qty
        o["state"]="FILLED" if o["filled"]==o["qty"] else "PARTIAL"
        self.s["events"][event]=payload
        self.s["audit"].append(["FILL",event,key])
        self.check()
        return "APPLIED"

    def timeout(self,key):
        o=self.s["orders"][key]
        if o["state"] in ("OPEN","PARTIAL"):
            o["state"]="UNKNOWN"
            self.freeze("ORDER_TIMEOUT")

    def cancel_confirmed(self,key):
        # A confirmed final broker status, not merely a cancel request.
        o=self.s["orders"][key]
        if o["state"] in ("OPEN","PARTIAL","UNKNOWN"):
            o["state"]="CANCELLED"
            self.s["audit"].append(["CANCEL_CONFIRMED",key])
        self.check()

    def reconcile(self, broker_snapshot):
        # Compare full active order payloads, execution event IDs and balances;
        # cannot infer an unknown order's status from a missing response.
        local={k:self.s[k] for k in ("cash","holdings","available","orders","events","session")}
        if local!=broker_snapshot or any(o["state"]=="UNKNOWN" for o in self.active()):
            self.freeze("RECONCILIATION_MISMATCH")
            return False
        self.s["audit"].append(["RECONCILED"])
        return True

    def resume(self, broker_snapshot, operator_approved, fresh_session):
        if not operator_approved or fresh_session!=self.s["session"]:
            return False
        if not self.reconcile(broker_snapshot):
            return False
        self.s["frozen"]=False
        self.s["freeze_reason"]=None
        self.s["audit"].append(["RESUME"])
        return True

    def next_session(self):
        if self.active() or self.s["frozen"]:
            raise ValueError("resolve open/unknown orders and freezes first")
        self.s["session"]+=1
        self.s["available"]=dict(self.s["holdings"])
        self.check()


def broker_view(ledger):
    # Explicit artificial broker fixture. Not proof of independent real broker reconciliation.
    return {k:copy.deepcopy(ledger.s[k]) for k in
            ("cash","holdings","available","orders","events","session")}


def paper_report():
    l=PaperLedger()
    outcomes={}
    outcomes["first"]=l.submit("D1:S01:BUY:1","S01","BUY",200,1000,1,1)
    outcomes["duplicate_submit"]=l.submit("D1:S01:BUY:1","S01","BUY",200,1000,1,1)
    outcomes["partial_fill"]=l.fill("F1","D1:S01:BUY:1",100,990)
    l.timeout("D1:S01:BUY:1")
    # Persist then reconstruct; retry cannot create a second intent.
    l=PaperLedger(l.snapshot())
    outcomes["retry_after_restart"]=l.submit("D1:S01:BUY:1","S01","BUY",200,1000,1,1)
    outcomes["duplicate_fill"]=l.fill("F1","D1:S01:BUY:1",100,990)
    outcomes["blocked_while_unknown"]=l.submit("another","S02","BUY",100,1000,1,1)
    outcomes["premature_resume"]=l.resume(broker_view(l),True,1)
    # Artificial broker confirms remaining quantity cancelled.
    l.cancel_confirmed("D1:S01:BUY:1")
    mismatched=broker_view(l)
    mismatched["cash"]+=1
    outcomes["mismatch_resume"]=l.resume(mismatched,True,1)
    outcomes["no_approval"]=l.resume(broker_view(l),False,1)
    outcomes["confirmed_resume"]=l.resume(broker_view(l),True,1)
    outcomes["same_day_sell"]=l.submit("D1:SELL","S01","SELL",100,1000,1,1)
    l.next_session()
    outcomes["next_day_sell"]=l.submit("D2:SELL","S01","SELL",100,1000,2,2)
    outcomes["sell_fill"]=l.fill("F2","D2:SELL",100,1010)
    outcomes["stale_data"]=l.submit("D2:STALE","S02","BUY",100,1000,1,2)
    return dict(source_kind=SOURCE,outcomes=outcomes,snapshot=l.snapshot(),
                assumptions=["integer cents; no fees in fault drill; artificial limit orders",
                             "single process, one synthetic account; no network, broker or real trading",
                             "reconciliation fixture is constructed, not external broker evidence"])


def gate_decision(gates):
    if not gates["ledger_reconciled"] or not gates["fault_drill"]:
        return "STOP_AND_REPAIR"
    if not all(gates[k] for k in ("real_pit","independent_oos","real_execution","production_approval")):
        return "RESEARCH_ONLY"
    return "ELIGIBLE_FOR_HUMAN_REVIEW"


def report():
    panel=make_panel()
    allocation=allocation_report(panel)
    paper=paper_report()
    o=paper["outcomes"]
    gates=dict(ledger_reconciled=all(abs(d["residual"])<1e-6
                                    for a in allocation["attribution"].values()
                                    for d in a["daily"]),
               fault_drill=(o["retry_after_restart"]=="DUPLICATE" and
                            o["duplicate_fill"]=="DUPLICATE" and
                            not o["mismatch_resume"] and o["confirmed_resume"] and
                            o["same_day_sell"]=="T_PLUS_ONE_OR_RESERVED"),
               real_pit=False,independent_oos=False,real_execution=False,production_approval=False)
    result=dict(source_kind=SOURCE,study_id="volume3-classroom-capstone-v1",
                input_sha256=digest(panel),policy_sha256=digest(POLICY),
                allocation=allocation,paper=paper,gates=gates,decision=gate_decision(gates))
    result["report_sha256"]=digest(result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json",action="store_true")
    p.add_argument("--chapter",choices=("11","12","13"),default="13")
    args=p.parse_args()
    r=report()
    if args.json:
        print(json.dumps(r,ensure_ascii=False,allow_nan=False))
        return
    print(SOURCE, "— no live orders")
    if args.chapter in ("11","13"):
        for k,a in r["allocation"]["accounts"].items():
            print(k, "NAV",round(a["final_nav"],2),"return",round(a["total_return"]*100,3),
                  "% max drawdown",round(a["max_drawdown"]*100,3),"%")
        print("Risk decisions:",json.dumps([{k:d[k] for k in ("signal","target_cash","sleeve_corr","overlap")}
                                            for d in r["allocation"]["decisions"]],ensure_ascii=False))
    if args.chapter in ("12","13"):
        print("Fault drill:",json.dumps(r["paper"]["outcomes"],ensure_ascii=False))
    print("Evidence gates:",json.dumps(r["gates"],ensure_ascii=False))
    print("Decision:",r["decision"])


if __name__=="__main__":
    main()
