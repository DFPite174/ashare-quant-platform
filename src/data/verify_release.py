"""Read-only checks against released tables, native-contract exports and frozen-source receipts."""
import hashlib
import json
from pathlib import Path

import duckdb


def verify(root):
    sql=duckdb.connect()
    market=root/"market-v1"
    financial=root/"statements-v1"
    for directory in (market,financial,root/"research"):
        manifest=json.loads((directory/"manifest.json").read_text("utf-8"))
        for file,digest in manifest["sha256"].items():
            if hashlib.sha256((directory/file).read_bytes()).hexdigest()!=digest:
                raise ValueError(f"Content hash mismatch: {file}")
    for path in sorted([*market.glob("*.parquet"),*financial.glob("*.parquet")]):
        sql.register(path.stem,sql.read_parquet(str(path)))
    checks={}
    def count(name,query,expected):
        actual=sql.sql(query).fetchall()[0][0]
        if actual!=expected:
            raise ValueError(f"{name}: expected {expected}, observed {actual}")
        checks[name]=int(actual)
    count("security_day_unique","select count(distinct (asset,date)) from security_days",96800)
    count("security_day_total","select count(*) from security_days",96800)
    count("bar_unique","select count(distinct (asset,date)) from bars_unadjusted",85981)
    count("bar_total","select count(*) from bars_unadjusted",85981)
    count("suspensions_confirmed_by_provider","""select count(*) from security_days d
          where d.eligible=1 and d.close is null and exists (
            select 1 from suspension_events s where s.ts_code=d.asset
            and s.trade_date=replace(d.date,'-','') and s.suspend_type='S'
            and trim(coalesce(s.suspend_timing,''))='')""",755)
    count("unclassified_eligible_missing_bars","select count(*) from security_days where eligible=1 and close is null and status!='FULL_DAY_SUSPENSION'",0)
    count("prices_outside_observed_limits","""select count(*) from bars_unadjusted b join security_days d using(asset,date)
        where b.high>d.up_limit+0.000001 or b.low<d.down_limit-0.000001""",0)
    count("unresolved_full_S_bar_conflicts","select count(*) from security_days where status='CONFLICT_BAR_AND_FULL_S'",0)
    count("benchmark_dates","select count(distinct date) from benchmark_price",484)
    count("benchmark_months","select count(distinct substr(trade_date,1,6)) from benchmark_weights_monthly",25)
    count("benchmark_membership_exceptions","""select count(*) from (
         select trade_date from benchmark_weights_monthly group by trade_date
         having count(distinct con_code)<>300 or abs(sum(weight)-100)>0.02)""",0)
    for table in ("income","balancesheet"):
        count(table+"_future_or_ambiguous_usable",f"""select count(*) from {table} where diagnostic_usable and
          (distinct_values<>1 or available_at_assumed is null or
          cast(substr(available_at_assumed,1,10) as date)<=greatest(ann_date,f_ann_date)
          or substr(available_at_assumed,1,10)>'2024-12-31')""",0)
    accepted=json.loads((root/"engine-inputs/corporate_actions.json").read_text("utf-8"))
    blocked=json.loads((root/"engine-inputs/blocked_actions.json").read_text("utf-8"))
    a={(r["action"]["symbol"],r["action"]["ex_date"].replace("-","")) for r in accepted}
    b={(r["symbol"],r["ex_date"]) for r in blocked}
    keys=set(sql.sql("select distinct ts_code,ex_date from corporate_actions").fetchall())
    if a&b or a|b!=keys or len(a)!=len(accepted) or any(r["action"]["fractional_policy"]!="reject" for r in accepted):
        raise ValueError("Corporate action coverage mismatch")
    checks["admitted_action_keys"]=len(a)
    checks["quarantined_action_keys"]=len(b)
    sql.close()
    return checks


if __name__=="__main__":
    print(json.dumps(verify(Path(__file__).resolve().parent),indent=2))
