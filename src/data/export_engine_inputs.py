"""Adapt the published tables to the pinned engine's loaders. Does not run a matching engine."""
import argparse
import json
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from contracts import CorporateAction
from engine.data import load_bars_csv, load_rules_csv


def iso(value):
    return datetime.strptime(value, "%Y%m%d").date() if pd.notna(value) else None


def build(source, out):
    bars = pd.read_parquet(source/"bars_unadjusted.parquet")
    bars = bars.rename(columns={"asset":"symbol","date":"trade_date"})
    # The Research CSV round-trip has sub-microshare floating error; reject fractional shares.
    if (bars.volume-bars.volume.round()).abs().max()>1e-6:
        raise ValueError("Fractional share volume")
    bars.volume = bars.volume.round().astype("int64")
    cols = ["symbol","trade_date","open","high","low","close","volume"]
    bars[cols].to_csv(out/"bars_daily.csv",index=False)
    if len(load_bars_csv(out/"bars_daily.csv"))!=len(bars):
        raise ValueError("Engine Bar loader mismatch")
    panel = pd.read_parquet(source/"security_days.parquet")
    # Restrict the rule example to a documented regular ChiNext limit-order case.
    pilot = panel.loc[panel.asset.eq("300266.SZ") & panel.date.between("2023-01-18","2023-02-03")].copy()
    if len(pilot)!=8 or not pilot.eligible.eq(1).all() or pilot.st_listed.any() or (
            ~pilot.status.isin(["FULL_DAY_SUSPENSION","OBSERVED_BAR"])).any():
        raise ValueError("Unexpected pilot coverage")
    if (pilot.up_limit/pilot.down_limit).gt(2).any() or pilot.up_limit.isna().any():
        raise ValueError("Unverified pilot price bounds")
    pilot["trade_status"] = pilot.status.map({"FULL_DAY_SUSPENSION":"SUSPENDED","OBSERVED_BAR":"OPEN"})
    pilot = pilot.assign(limit_state="BOUNDED",buy_min=100,buy_step=100,sell_min=100,sell_step=100,
                         max_order=300000).rename(columns={"asset":"symbol","date":"trade_date"})
    rulecols = ["symbol","trade_date","trade_status","limit_state","up_limit","down_limit",
                "buy_min","buy_step","sell_min","sell_step","max_order"]
    pilot[rulecols].to_csv(out/"pilot_rules.csv",index=False)
    prules = load_rules_csv(out/"pilot_rules.csv")
    selected = bars.loc[bars.symbol.eq("300266.SZ") & bars.trade_date.isin(pilot.trade_date),cols]
    selected.to_csv(out/"pilot_bars.csv",index=False)
    pbars = load_bars_csv(out/"pilot_bars.csv")
    if len(prules)!=8 or len(pbars)!=3:
        raise ValueError("Pilot rules/Bar coverage mismatch")

    rows = pd.read_parquet(source/"corporate_actions.parquet")
    economic = ["imp_ann_date","record_date","pay_date","div_listdate","cash_div_tax",
                "stk_div","stk_bo_rate","stk_co_rate"]
    accepted,blocked = [],[]
    for (symbol,exdate),group in rows.groupby(["ts_code","ex_date"],sort=True):
        distinct = group.drop_duplicates(economic)
        reason = None
        row = distinct.iloc[0]
        stock = row.stk_div
        cash = row.cash_div_tax
        if len(distinct)>1:
            reason = "CONFLICTING_ECONOMIC_TERMS"
        elif not row.dates_complete or not row.chronology_ok:
            reason = "UNVERIFIED_DATES"
        elif pd.isna(cash) or pd.isna(stock):
            reason = "INCOMPLETE_AMOUNT"
        elif abs(stock - group.stk_bo_rate.fillna(0).iloc[0] - group.stk_co_rate.fillna(0).iloc[0])>1e-8:
            reason = "SHARE_COMPONENT_MISMATCH"
        if reason:
            blocked.append(dict(symbol=symbol,ex_date=exdate,reason=reason,source_rows=len(group)))
            continue
        data = CorporateAction(symbol=symbol,ex_date=iso(exdate),announcement_date=iso(row.imp_ann_date),
                 record_date=iso(row.record_date),pay_date=iso(row.pay_date),share_listing_date=iso(row.div_listdate),
                 fractional_policy="reject",cash_div=str(cash),bonus_ratio=str(group.stk_bo_rate.fillna(0).iloc[0]),
                 reserve_ratio=str(group.stk_co_rate.fillna(0).iloc[0]))
        accepted.append({"action":data.model_dump(mode="json"),"source_sha256":row.source_sha256,"source_rows":len(group)})
    for filename, data in [("corporate_actions.json",accepted),("blocked_actions.json",blocked)]:
        (out/filename).write_text(json.dumps(data,indent=1),"utf-8")
    summary = {"engine_bars_parsed":len(bars),"pilot_rules":len(prules),"pilot_bars":len(pbars),
               "action_security_dates":rows.groupby(["ts_code","ex_date"]).ngroups,
               "accepted_action_keys":len(accepted),"blocked_action_keys":len(blocked),
               "limit_order_pilot_only":True,"account_run":False}
    (out/"contract-check.json").write_text(json.dumps(summary,indent=2),"utf-8")


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    if args.output.exists():
        raise SystemExit("Choose a new directory")
    with tempfile.TemporaryDirectory(dir=args.output.parent) as temp:
        stage=Path(temp)/"contracts"
        stage.mkdir()
        build(args.source,stage)
        stage.rename(args.output)
