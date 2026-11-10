"""Assess one weekly decision using an immutable Research value and an explicit account state."""
import argparse
import json
import sys
from pathlib import Path

from portfolio import Market, decide, sha, weekly_targets


def assess(request,registry,p1):
    required={"mode","state_id","asof","balance_basis","outstanding_orders","cash","positions",
              "signal_date","value_id","value_sha256","dataset_fingerprint"}
    if set(request)!=required or request["mode"] not in ("admitted","diagnostic"):
        raise ValueError("Invalid P3 request schema or mode")
    if not isinstance(request["state_id"],str) or not request["state_id"].strip():
        raise ValueError("State identifier required")
    if request["balance_basis"]!="CNY_CASH_ONLY_NO_RECEIVABLES" or type(request["outstanding_orders"])!=int or request["outstanding_orders"]!=0:
        raise ValueError("Outstanding orders, unpriced receivables and margin accounts need a different adapter")
    market=Market(p1/"market-v1")
    if market.fingerprint!=request["dataset_fingerprint"]:
        raise ValueError("Snapshot mismatch")
    diagnostic=request["mode"]=="diagnostic"
    targets=weekly_targets(registry,request["value_id"],request["value_sha256"],market.fingerprint,market.days,diagnostic)
    chosen=targets.loc[targets.signal_date.eq(request["signal_date"])]
    if len(chosen)!=10:
        raise ValueError("No ten-name weekly decision on requested date")
    day=chosen.assessment_date.iloc[0]
    if request["asof"]!=request["signal_date"]+"T18:00:00+08:00":
        raise ValueError("Account state must match the signal clock")
    pos=request["positions"]
    if not isinstance(pos,dict) or any(set(v)!={"shares","sellable"} for v in pos.values()):
        raise ValueError("Invalid position schema")
    account={a:(v["shares"],v["sellable"]) for a,v in pos.items()}
    policy_path=Path(__file__).with_name("policy.json")
    rows,report=decide(market,request["signal_date"],day,dict(zip(chosen.asset,chosen.target_weight)),
                         request["cash"],account,json.loads(policy_path.read_text("utf-8-sig")),planning=True)
    return dict(mode=request["mode"],state_id=request["state_id"],asof=request["asof"],value_id=request["value_id"],
                value_sha256=request["value_sha256"],dataset_fingerprint=market.fingerprint,policy_sha256=sha(policy_path),
                bind_to_execution=False,portfolio=report,decisions=json.loads(rows.to_json(orient="records")))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request",type=Path)
    parser.add_argument("registry",type=Path)
    parser.add_argument("p1",type=Path)
    args=parser.parse_args()
    try:
        result=assess(json.loads(args.request.read_text("utf-8-sig")),args.registry,args.p1)
        print(json.dumps(result,ensure_ascii=True,allow_nan=False))
    except (ValueError,KeyError,TypeError,PermissionError) as exc:
        print(json.dumps({"status":"BLOCKED","reason":str(exc)},ensure_ascii=True),file=sys.stderr)
        raise SystemExit(2)
