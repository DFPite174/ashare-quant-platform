"""Map provider announcement dates to the next SSE session, retaining every returned version."""
import argparse
import bisect
import json
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

from build_snapshot import digest, load_captures


def build(raw, calendar_raw, research, stage):
    inventory = []
    records = load_captures(raw, "statement-supplement", inventory, {"income","balancesheet"})
    source = json.loads((research/"manifest.json").read_text("utf-8"))
    assets = set(source["sources"][0]["security_master"])
    calmeta = list(calendar_raw.glob("trade_cal-*.meta.json"))
    if len(calmeta)!=1:
        raise ValueError("Ambiguous parent calendar")
    meta=json.loads(calmeta[0].read_text("utf-8"))
    calfile=calmeta[0].with_name(calmeta[0].name.replace(".meta.json",".json"))
    if digest(calfile)!=meta["sha256"] or meta["sha256"] not in {r["sha256"] for r in source["sources"][0]["responses"]}:
        raise ValueError("Untrusted parent calendar")
    payload=json.loads(calfile.read_bytes())["data"]
    cal=pd.DataFrame(payload["items"],columns=payload["fields"])
    sessions=sorted(cal.loc[cal.is_open.eq(1),"cal_date"])
    summary = {}
    con=duckdb.connect()
    for api, values in [("income",["revenue","total_revenue","n_income_attr_p"]),
                        ("balancesheet",["total_assets","total_liab","total_hldr_eqy_exc_min_int"])]:
        receipts=[r for r in inventory if r["api"]==api]
        if len(receipts)!=len(assets) or {r["params"]["ts_code"] for r in receipts}!=assets:
            raise ValueError("Incomplete statements requests")
        frame=records[api].copy()
        for field in ("ann_date","f_ann_date","end_date"):
            frame[field]=pd.to_datetime(frame[field],format="%Y%m%d",errors="raise")
        both=frame.ann_date.notna() & frame.f_ann_date.notna()
        latest=frame[["ann_date","f_ann_date"]].max(axis=1)
        latest=latest.where(both & latest.ge(frame.end_date) & latest.le(pd.Timestamp("2024-12-31")))
        def effective(day):
            if pd.isna(day):
                return None
            index=bisect.bisect_right(sessions,day.strftime("%Y%m%d"))
            if index>=len(sessions) or sessions[index]>"20241231":
                return None
            return pd.Timestamp(sessions[index]).strftime("%Y-%m-%dT18:00:00+08:00")
        frame["available_at_assumed"]=latest.map(effective)
        keys=["ts_code","end_date","report_type","comp_type","ann_date","f_ann_date"]
        # An update flag cannot establish which values investors actually saw on the date.
        versions=frame.drop_duplicates(keys+values).groupby(keys,dropna=False).size().rename("distinct_values")
        frame=frame.merge(versions.reset_index(),on=keys,how="left",validate="many_to_one")
        frame["diagnostic_usable"]=frame.available_at_assumed.notna() & frame.distinct_values.eq(1)
        con.register("versions",frame)
        con.table("versions").write_parquet(str(stage/(api+".parquet")),compression="zstd")
        con.unregister("versions")
        summary[api]={"requests":len(receipts),"rows":len(frame),"securities_with_rows":frame.ts_code.nunique(),
                      "empty_requests":sum(r["rows"]==0 for r in receipts),
                      "usable_diagnostic_rows":int(frame.diagnostic_usable.sum()),
                      "conflicting_rows":int(frame.distinct_values.gt(1).sum()),
                      "missing_or_out_of_window_available_at":int(frame.available_at_assumed.isna().sum())}
    con.close()
    (stage/"source_index.json").write_text(json.dumps(inventory,indent=1),"utf-8")
    (stage/"manifest.json").write_text(json.dumps({"end":"2024-12-31","strict_pit":False,
        "availability":"Later of both stated announcement dates; following session 18:00 Shanghai, assumed",
        "tables":summary,"sha256":{p.name:digest(p) for p in sorted(stage.iterdir())}},indent=2),"utf-8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ("raw","calendar_raw","research","output"):
        p.add_argument(arg,type=Path)
    args=p.parse_args()
    if args.output.exists():
        raise SystemExit("Choose a new directory")
    with tempfile.TemporaryDirectory(dir=args.output.parent) as temp:
        stage=Path(temp)/"tables"
        stage.mkdir()
        build(args.raw,args.calendar_raw,args.research,stage)
        stage.rename(args.output)
