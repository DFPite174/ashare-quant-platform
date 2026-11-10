"""P3 historical decision adapter. No order transmission or fill simulation."""
import hashlib
import json
import math
import sys
from io import BytesIO
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent/"upstream"))
from engine.market_rules import block_reason, round_order
from risk.tradability.adv_capacity_guard import ADVCapacityGuard
from strategy.optimizers.equal_weight import EqualWeightOptimizer
from factor_research.admission import candidate_list
from factor_research.registry import factor_snapshot


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weekly_targets(registry, value_id, expected_digest, fingerprint, calendar, diagnostic=False):
    matches=[r for r in candidate_list(registry) if r["id"]==value_id]
    if len(matches)!=1 or matches[0]["value_sha256"]!=expected_digest:
        raise ValueError("Factor identity mismatch")
    row=matches[0]
    if not diagnostic and (row["status"]!="published" or row["membership"]!="library"):
        raise PermissionError("FACTOR_NOT_ADMITTED")
    meta,body=factor_snapshot(registry,value_id,fingerprint)
    if meta["sha256"]!=expected_digest:
        raise ValueError("Unexpected registered content")
    values=pd.read_csv(BytesIO(body))
    if values.duplicated(["date","asset"]).any() or not np.isfinite(values.factor).all():
        raise ValueError("Invalid registered values")
    optimizer=EqualWeightOptimizer()
    records=[]
    for day,nxt in zip(calendar,calendar[1:]):
        if pd.Timestamp(day).to_period("W-FRI")==pd.Timestamp(nxt).to_period("W-FRI"):
            continue
        frame=values.loc[values.date.eq(day)].copy()
        ready=pd.to_datetime(frame.available_at,utc=True)
        frame=frame.loc[ready.le(pd.Timestamp(day,tz="Asia/Shanghai")+pd.Timedelta(hours=18))]
        top=frame.sort_values(["factor","asset"],ascending=[False,True]).head(10)
        if len(top)!=10:
            continue
        weights=optimizer.optimize(top.factor.to_numpy(),None)
        for rank,((_,item),weight) in enumerate(zip(top.iterrows(),weights),1):
            records.append(dict(signal_date=day,assessment_date=nxt,asset=item.asset,rank=rank,
                score=item.factor,target_weight=weight,value_id=value_id,value_sha256=expected_digest,
                mode="DEVELOPMENT_DIAGNOSTIC" if diagnostic else "ADMITTED_RESEARCH"))
    return pd.DataFrame(records)


class Market:
    def __init__(self,root):
        root=Path(root)
        manifest=json.loads((root/"manifest.json").read_text("utf8"))
        self.fingerprint=manifest["research_fingerprint"]
        def table(name):
            path=root/(name+".parquet")
            if sha(path)!=manifest["sha256"][path.name]:
                raise ValueError("P1 content hash mismatch")
            return duckdb.read_parquet(str(path)).df()
        panel=table("security_days")
        bars=table("bars_unadjusted")
        df=panel.merge(bars[["date","asset","open","high","low","amount","volume"]],
                       on=["date","asset"],how="left",validate="one_to_one")
        df=df.merge(table("security_master")[["ts_code","market"]].rename(columns={"ts_code":"asset"}),
                    on="asset",validate="many_to_one").sort_values(["asset","date"])
        confirmed=df.status.eq("FULL_DAY_SUSPENSION")
        amount=df.amount.mask(confirmed,0)
        df["adv20"]=amount.groupby(df.asset).transform(lambda s:s.shift(1).rolling(20,min_periods=20).mean())
        df["next_adv20"]=amount.groupby(df.asset).transform(lambda s:s.rolling(20,min_periods=20).mean())
        # A carried mark values a locked holding; it is never fed to the trade-price filter.
        df["mark"]=df.close.groupby(df.asset).ffill()
        df["mark_date"]=df.date.where(df.close.notna()).groupby(df.asset).ffill()
        self.days=sorted(df.date.unique())
        self.panel=df.set_index(["date","asset"],verify_integrity=True).sort_index()
        actions=table("corporate_actions")
        self.actions=set(zip(actions.ts_code,pd.to_datetime(actions.ex_date).dt.strftime("%Y-%m-%d")))


def lots(board):
    profiles={"主板":(100,100,1000000),"创业板":(100,100,300000),"科创板":(200,1,100000)}
    if board not in profiles:
        return None
    minimum,step,maximum=profiles[board]
    return dict(buy_min=minimum,buy_step=step,sell_min=minimum,sell_step=step,max_order=maximum)


def historical_gate(row,side,has_action):
    if row.status=="FULL_DAY_SUSPENSION":
        return "SUSPENDED"
    if not row.eligible or row.status!="OBSERVED_BAR":
        return "DAY_STATUS_BLOCKED"
    if has_action:
        return "CORPORATE_ACTION_REVIEW"
    if row.limit_evidence!="PROVIDER_PRICE_BOUNDS" or row.up_limit/row.down_limit>2:
        return "PRICE_RULE_REVIEW"
    if side=="buy" and row.st_listed:
        return "ST_BUY_BLOCKED"
    return block_reason({"trade_status":"OPEN","limit_state":"BOUNDED","up_limit":row.up_limit,
              "down_limit":row.down_limit},{"close":row.close,"volume":row.volume},side)


def decide(market,signal_day,day,weights,cash,positions,policy,*,planning=False,previous_plan=None):
    """Independent frozen account request. Cash is net of reservations; sellable is net of sell reservations."""
    if day not in market.days or market.days.index(day)==0 or market.days[market.days.index(day)-1]!=signal_day:
        raise ValueError("Require consecutive signal and assessment sessions")
    if not weights and not positions:
        raise ValueError("Empty portfolio request")
    for k in ("adv_fraction","name_cap","industry_cap","cash_floor","fee_buffer"):
        if not math.isfinite(policy[k]) or not 0<=policy[k]<=1:
            raise ValueError("Invalid risk policy: "+k)
    if not math.isfinite(policy["min_fee"]) or policy["min_fee"]<0:
        raise ValueError("Invalid fee reserve")
    if not math.isfinite(cash) or cash<0 or any(not math.isfinite(w) or not 0<=w<=1 for w in weights.values()) or sum(weights.values())>1+1e-12:
        raise ValueError("Invalid cash or target")
    for held,sellable in positions.values():
        if type(held)!=int or type(sellable)!=int or not 0<=sellable<=held:
            raise ValueError("Invalid holdings or sellability")
    assets=sorted(set(weights)|set(positions))
    prior=market.panel.loc[signal_day].loc[assets]
    asof=signal_day if planning else day
    now=market.panel.loc[asof].loc[assets].copy()
    if planning:
        now["adv20"]=now.next_adv20
    for a,(held,_) in positions.items():
        if held and any(not math.isfinite(v) or v<=0 for v in (now.at[a,"mark"],prior.at[a,"mark"])):
            raise ValueError("UNVALUED_POSITION")
        if held and (not now.at[a,"eligible"] or not prior.at[a,"eligible"]):
            raise ValueError("POSITION_LIFECYCLE_UNVERIFIED")
        if held and any(symbol==a and prior.at[a,"mark_date"]<exday<=asof for symbol,exday in market.actions):
            raise ValueError("POSITION_REQUIRES_CORPORATE_ACTION_RECONCILIATION")
    equity=cash+sum(held*now.at[a,"mark"] for a,(held,_) in positions.items() if held)
    prev_equity=cash+sum(held*prior.at[a,"mark"] for a,(held,_) in positions.items() if held)
    if equity<=0:raise ValueError("Nonpositive portfolio equity")
    holdings={a:positions.get(a,(0,0))[0] for a in assets}
    exposure={}
    for a,held in holdings.items():
        if held:
            key=now.at[a,"industry_l1"] if pd.notna(now.at[a,"industry_l1"]) else "UNKNOWN"
            exposure[key]=exposure.get(key,0)+held*now.at[a,"mark"]
    actual_group_weights={k:value/equity for k,value in exposure.items()}
    withheld=cash
    result=[]
    capacity=ADVCapacityGuard(max_adv_participation=policy["adv_fraction"])
    for a in sorted(assets,key=lambda a:(-weights.get(a,0),a)):
        row=now.loc[a]
        held,sellable=positions.get(a,(0,0))
        mark=row.mark
        weight=weights.get(a,0)
        before=prior.at[a,"mark"]
        if not math.isfinite(mark) or mark<=0 or not math.isfinite(before) or before<=0:
            raise ValueError("UNVALUED_TARGET")
        prev_desired=math.floor(prev_equity*weight/before)-held
        requested=math.floor(equity*weight/mark)-held
        count=abs(requested)
        reasons=[]
        def limit(maximum,label):
            nonlocal count
            new=min(count,max(0,math.floor(maximum+1e-10)))
            if new<count:reasons.append(label)
            count=new
        side="buy" if requested>0 else "sell"
        reason=None
        if requested and not planning:
            reason=historical_gate(row,side,(a,day) in market.actions)
        if planning and requested and (not row.eligible or (requested>0 and row.st_listed)):
            reason="SIGNAL_DATE_POLICY"
        if previous_plan is not None and requested:
            planned=previous_plan[a]
            limit(abs(planned) if planned*requested>0 else 0,"SIGNAL_PLAN_CAP")
        profile=lots(row.market)
        industry=row.industry_l1 if pd.notna(row.industry_l1) else "UNKNOWN"
        if reason or profile is None:
            limit(0,reason or "UNKNOWN_BOARD")
        if requested<0:
            limit(sellable,"T1_OR_RESERVED")
        if requested>0:
            if industry=="UNKNOWN" or "UNKNOWN" in exposure:
                limit(0,"UNKNOWN_INDUSTRY")
            limit((equity*policy["name_cap"]-held*mark)/mark,"NAME_CAP")
            limit((equity*policy["industry_cap"]-exposure.get(industry,0))/mark,"INDUSTRY_CAP")
            spend=withheld-equity*policy["cash_floor"]
            limit((spend-policy["min_fee"])/(mark*(1+policy["fee_buffer"])),"CASH_RESERVE")
        if not math.isfinite(row.adv20) or row.adv20<=0:
            limit(0,"MISSING_ADV20")
        else:
            limit(row.adv20*capacity.max_adv_participation/mark,"ADV20_CAP")
        sign=1 if requested>0 else -1
        qty=round_order(sign*count,held,profile) if count else 0
        if abs(qty)!=count:reasons.append("LOT_OR_MAX_ORDER")
        fee=0.0
        if qty>0:
            fee=policy["min_fee"]+qty*mark*policy["fee_buffer"]
            withheld-=qty*mark+fee
            exposure[industry]=exposure.get(industry,0)+qty*mark
        impact=capacity.estimate_market_impact_bps(abs(qty)*mark,row.adv20) if qty else 0
        result.append(dict(asset=a,signal_date=signal_day,assessment_date=day,asof=asof,
            stage="PRETRADE_DRAFT" if planning else "HISTORICAL_CLOSE_REVIEW",raw_weight=weight,
            actual_shares=held,sellable_shares=sellable,locked_shares=held-sellable,
            previous_mark=before,mark=mark,mark_date=row.mark_date,previous_equity=prev_equity,equity=equity,
            precheck_requested_delta=prev_desired,requested_delta=requested,conditional_delta=qty,
            deferred_delta=requested-qty,actual_shares_after_check=held,conditional_shares=held+qty,
            raw_actual_weight=held*mark/equity,industry=industry,status=row.status,adv20_cny=row.adv20,
            fee_reserved=fee,impact_model_bps=impact,reasons="|".join(reasons) or "NONE"))
    frame=pd.DataFrame(result)
    risk=frame.assign(exposure=frame.conditional_shares*frame.mark/equity)
    breaches=risk.loc[risk.exposure.gt(policy["name_cap"]+1e-12),"asset"].tolist()
    groups=risk.groupby("industry").exposure.sum()
    residual=dict(name_over=breaches,industry_over=groups[groups>policy["industry_cap"]+1e-12].index.tolist(),
        unclassified_held=bool("UNKNOWN" in exposure),cash_floor_shortfall=max(0.0,equity*policy["cash_floor"]-withheld))
    return frame,dict(previous_equity=prev_equity,equity=equity,cash=cash,unreserved_cash_after_requests=withheld,
        actual_name_over=frame.loc[frame.raw_actual_weight.gt(policy["name_cap"]+1e-12),"asset"].tolist(),
        actual_industry_over=[k for k,w in actual_group_weights.items() if w>policy["industry_cap"]+1e-12],
        any_deferred=bool(frame.deferred_delta.ne(0).any()),residual=residual,
        unresolved=any(bool(v) for v in residual.values()),account_mutated=False)
