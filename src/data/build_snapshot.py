"""Join frozen Tushare records to an existing Research snapshot. Publish to a new directory."""
import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path

import duckdb
import pandas as pd
from factor_research.data import load_dataset


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_captures(folder, prefix, inventory, keep):
    data = defaultdict(list)
    for path in sorted(folder.glob("*.meta.json")):
        meta = json.loads(path.read_text("utf-8"))
        file = path.with_name(path.name.replace(".meta.json", ".json"))
        sha = digest(file)
        if sha != meta["sha256"] or meta["http_status"] != 200:
            raise ValueError(f"Unverified capture: {file.name}")
        response = json.loads(file.read_bytes())
        payload = response["data"]
        if response["code"] != 0 or payload.get("has_more") or len(payload["items"]) != meta["rows"]:
            raise ValueError(f"Partial or failed capture: {file.name}")
        if meta["endpoint"] != "https://api.tushare.pro":
            raise ValueError("Unexpected provider")
        inventory.append(dict(batch=prefix, file=file.name, api=meta["api"], params=meta["params"],
                              fields=meta["fields"], captured_at=meta["captured_at"], rows=meta["rows"],
                              sha256=sha, metadata_sha256=digest(path)))
        if meta["api"] in keep:
            for item in payload["items"]:
                row = dict(zip(payload["fields"], item, strict=True))
                symbol = meta["params"].get("ts_code")
                if symbol and row.get("ts_code") != symbol:
                    raise ValueError(f"Provider symbol mismatch: {file.name}")
                data[meta["api"]].append(dict(**row, source_sha256=sha))
    return {key: pd.DataFrame(rows) for key, rows in data.items()}


def day_keys(frame):
    return frame.rename(columns={"ts_code": "asset", "trade_date": "date"}).assign(
        date=lambda t: pd.to_datetime(t.date, format="%Y%m%d").dt.strftime("%Y-%m-%d"))


def join_daily(panel, rows, columns):
    subset = day_keys(rows)[["asset", "date", *columns]]
    return panel.merge(subset, how="left", on=["asset", "date"], validate="one_to_one")


def build(research, base_raw, supplement, stage):
    ds = load_dataset(research)
    inventory = []
    base = load_captures(base_raw, "research-parent", inventory,
                         {"daily", "adj_factor", "stock_basic", "trade_cal", "daily_basic"})
    declared = {r["sha256"] for r in ds.manifest["sources"][0]["responses"]}
    if declared != {r["sha256"] for r in inventory}:
        raise ValueError("Parent raw response set differs from Research manifest")
    ext = load_captures(supplement, "p1", inventory, {"suspend_d", "stk_limit", "stock_st", "dividend",
                        "index_daily", "index_weight", "index_member_all", "trade_cal"})
    symbols = sorted(ds.universe.index.get_level_values("asset").unique())
    for api in ("suspend_d", "stk_limit", "stock_st", "dividend", "index_member_all"):
        reqs = [r for r in inventory if r["batch"] == "p1" and r["api"] == api]
        actual = {(r["params"]["ts_code"], r["params"].get("is_new")) for r in reqs}
        expected = {(s, mode) for s in symbols for mode in (("N","Y") if api=="index_member_all" else (None,))}
        if actual != expected or len(reqs) != len(expected):
            raise ValueError(f"Incomplete security coverage: {api}")
        if api in ("suspend_d", "stk_limit", "stock_st") and any(
                (r["params"].get("start_date"), r["params"].get("end_date")) != ("20230101","20241231") for r in reqs):
            raise ValueError(f"Unexpected request window: {api}")
    dates = ds.calendar.strftime("%Y-%m-%d")
    for cal in [base["trade_cal"], ext["trade_cal"]]:
        observed = pd.to_datetime(cal.loc[cal.is_open.eq(1), "cal_date"], format="%Y%m%d")
        observed = observed.loc[observed.between(ds.calendar[0], ds.calendar[-1])]
        if sorted(observed.dt.strftime("%Y-%m-%d")) != list(dates):
            raise ValueError("Exchange calendar differs from research calendar")

    market = pd.read_csv(research/"market.csv")
    panel = pd.read_csv(research/"universe.csv").drop(columns=["industry","exclusion_reason"])
    if len(panel) != len(symbols)*len(dates):
        raise ValueError("Incomplete security-day grid")
    master = pd.DataFrame(ds.manifest["sources"][0]["security_master"].values())
    raw_master = base["stock_basic"].set_index("ts_code", verify_integrity=True)
    for field in ("list_date","delist_date","exchange"):
        a = master.set_index("ts_code")[field].sort_index().fillna("")
        if not a.equals(raw_master[field].reindex(a.index).fillna("")):
            raise ValueError("Master mismatch: "+field)
    panel = panel.merge(master[["ts_code","list_date","delist_date"]].rename(columns={"ts_code":"asset"}),
                        on="asset", validate="many_to_one")
    stamp = panel.date.str.replace("-","",regex=False)
    before = stamp.lt(panel.list_date)
    after = panel.delist_date.notna() & stamp.ge(panel.delist_date.fillna("99999999"))
    if not panel.eligible.eq((~(before | after)).astype(int)).all():
        raise ValueError("Historical eligibility differs from listing contract")
    raw = day_keys(base["daily"])
    sample = raw.loc[raw.date.isin(dates)]
    compare = market.merge(sample, on=["asset","date"], suffixes=("_research","_raw"),
                           how="outer", validate="one_to_one", indicator=True)
    if not compare["_merge"].eq("both").all():
        raise ValueError("Raw and normalized Bar keys differ")
    tolerances = {"open":1e-8,"high":1e-8,"low":1e-8,"close":1e-8,"volume":1e-6,"amount":1e-4}
    deltas = {}
    for field in tolerances:
        value = compare[field+"_research"] if field in ("open","high","low","close") else compare[
                "amount_research" if field=="amount" else field]
        reference = (compare.vol*100 if field=="volume" else compare.amount_raw*1000 if field=="amount"
                     else compare[field+"_raw"])
        delta = (value-reference).abs()
        if delta.isna().any() or delta.max()>tolerances[field]:
            raise ValueError("Unit/value mismatch: "+field)
        deltas[field] = float(delta.max())
    for api, column, target, multiplier in (("adj_factor","adj_factor","adj_factor",1),
                                            ("daily_basic","total_mv","total_mv",10000)):
        values = day_keys(base[api]).set_index(["asset","date"],verify_integrity=True)[column]
        local = market.set_index(["asset","date"])[target]
        delta = (local - values.reindex(local.index)*multiplier).abs()
        if delta.isna().any() or delta.max()>0.01:
            raise ValueError("Value mismatch: "+target)
        deltas[target] = float(delta.max())
    bars = market.merge(sample[["asset","date","source_sha256"]], on=["asset","date"],validate="one_to_one")
    panel = panel.merge(bars[["asset","date","close"]],on=["asset","date"],how="left",validate="one_to_one")
    susp = ext["suspend_d"].copy()
    # Preserve multiple intraday events rather than allowing a row-order-dependent join.
    susp["full_S"] = susp.suspend_type.eq("S") & susp.suspend_timing.fillna("").str.strip().eq("")
    susp["intraday_S"] = susp.suspend_type.eq("S") & ~susp.full_S
    susp["resume_R"] = susp.suspend_type.eq("R")
    flags = susp.groupby(["ts_code","trade_date"],as_index=False)[["full_S","intraday_S","resume_R"]].any()
    panel = join_daily(panel,flags,["full_S","intraday_S","resume_R"])
    for col in ("full_S","intraday_S","resume_R"):
        panel[col] = panel[col].eq(True)
    panel = join_daily(panel,ext["stk_limit"],["up_limit","down_limit"])
    st = ext["stock_st"].groupby(["ts_code","trade_date"],as_index=False).size()
    panel = join_daily(panel,st,["size"]).rename(columns={"size":"st_record_count"})
    panel["st_record_count"] = panel.st_record_count.fillna(0).astype(int)
    panel["status"] = "UNKNOWN_MISSING_BAR"
    panel.loc[panel.close.notna(),"status"] = "OBSERVED_BAR"
    panel.loc[panel.close.notna() & panel.intraday_S,"status"] = "OBSERVED_INTRADAY_HALT"
    panel.loc[panel.close.isna() & panel.full_S & ~panel.resume_R,"status"] = "FULL_DAY_SUSPENSION"
    panel.loc[panel.close.notna() & panel.full_S & ~panel.resume_R,"status"] = "CONFLICT_BAR_AND_FULL_S"
    panel.loc[before,"status"] = "PRE_LISTING"
    panel.loc[after,"status"] = "DELISTED"
    panel["limit_evidence"] = "UNKNOWN"
    bounds = panel.up_limit.gt(0) & panel.down_limit.gt(0) & panel.up_limit.ge(panel.down_limit)
    panel.loc[bounds,"limit_evidence"] = "PROVIDER_PRICE_BOUNDS"
    panel["st_listed"] = panel.st_record_count.gt(0)
    gaps = panel.loc[panel.eligible.eq(1) & panel.close.isna()].copy()

    industry = ext["index_member_all"].drop_duplicates()
    actions = ext["dividend"].copy()
    actions = actions.loc[actions.ex_date.fillna("").between("20230101","20241231") & actions.div_proc.eq("实施")].copy()
    actions["dates_complete"] = (actions.record_date.notna() & actions.imp_ann_date.notna()
            & (actions.cash_div_tax.fillna(0).eq(0) | actions.pay_date.notna())
            & (actions.stk_div.fillna(0).eq(0) | actions.div_listdate.notna()))
    actions["ambiguous_security_exdate"] = actions.duplicated(["ts_code","ex_date"],keep=False)
    actions["chronology_ok"] = (actions.imp_ann_date.le(actions.record_date.fillna("")) &
            actions.record_date.fillna("").le(actions.ex_date) &
            (actions.pay_date.isna() | actions.pay_date.fillna("").ge(actions.ex_date)) &
            (actions.div_listdate.isna() | actions.div_listdate.fillna("").ge(actions.ex_date)))
    actions["account_review_required"] = (~actions.dates_complete | actions.ambiguous_security_exdate |
                                          ~actions.chronology_ok)
    index = day_keys(ext["index_daily"])
    if sorted(index.date)!=list(dates):
        raise ValueError("Incomplete benchmark price-index history")
    weights = ext["index_weight"]
    if weights.duplicated(["index_code","trade_date","con_code"]).any():
        raise ValueError("Duplicate benchmark membership")
    wdates = pd.to_datetime(weights.trade_date,format="%Y%m%d")
    if wdates.dt.to_period("M").nunique() != 25:
        raise ValueError("Missing benchmark months")
    financial = pd.read_csv(research/"feature_events.csv")
    source_hashes = {r["sha256"] for r in inventory if r["api"]=="fina_indicator"}
    if not set(financial.source_id.str.replace("tushare:","",regex=False)) <= source_hashes:
        raise ValueError("Financial event references an unknown source")

    db = duckdb.connect()
    db.register("panel",panel)
    db.register("industry",industry)
    # Date intervals with ambiguous memberships remain unassigned. Industry is provider-restated.
    industry_days = db.sql("""
        SELECT p.asset,p.date, count(distinct i.l1_code) AS industry_choices,
          CASE WHEN count(distinct i.l1_code)=1 THEN min(i.l1_code) END AS industry_l1
        FROM panel p LEFT JOIN industry i ON p.asset=i.ts_code
         AND i.in_date <= replace(p.date,'-','')
         AND (i.out_date IS NULL OR i.out_date > replace(p.date,'-',''))
        GROUP BY p.asset,p.date ORDER BY p.asset,p.date
    """).df()
    panel = panel.merge(industry_days,on=["asset","date"],validate="one_to_one")
    tables = {"security_days":panel,"bars_unadjusted":bars,"corporate_actions":actions,
              "suspension_events":susp,"industry_intervals":industry,"financial_events":financial,
              "benchmark_price":index,"benchmark_weights_monthly":weights,"security_master":master}
    counts = {}
    for name, frame in tables.items():
        db.register("source_table",frame)
        file = stage/(name+".parquet")
        db.table("source_table").write_parquet(str(file),compression="zstd")
        counts[name] = db.read_parquet(str(file)).aggregate("count(*)").fetchall()[0][0]
        if counts[name]!=len(frame):
            raise ValueError("Parquet readback mismatch")
        db.unregister("source_table")
    db.close()
    gaps.to_csv(stage/"missing_bars.csv",index=False)
    (stage/"source_index.json").write_text(json.dumps(inventory,indent=1,ensure_ascii=False),"utf-8")
    summary = dict(research_fingerprint=ds.fingerprint,strict_pit=False,raw_requests=len(inventory),
        securities=len(symbols),sessions=len(dates),first=dates[0],last=dates[-1],tables=counts,
        unit_check_max_error=deltas,status=panel.status.value_counts().to_dict(),
        missing_bar_reason=gaps.status.value_counts().to_dict(),
        eligible_unknown_limit=int((panel.eligible.eq(1) & ~bounds).sum()),
        eligible_ambiguous_or_missing_industry=int((panel.eligible.eq(1) & panel.industry_choices.ne(1)).sum()),
        actions_requiring_review=int(actions.account_review_required.sum()),
        quarantined_financial_fields=ds.manifest["sources"][0]["quarantined_financial_fields"],
        benchmark_months=wdates.dt.to_period("M").nunique(),benchmark_min_members=int(weights.groupby("trade_date").con_code.nunique().min()),
        sha256={p.name:digest(p) for p in sorted(stage.iterdir())})
    (stage/"manifest.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),"utf-8")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ("research","base_raw","supplement","output"):
        parser.add_argument(arg,type=Path)
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit("Choose a new output directory")
    with tempfile.TemporaryDirectory(dir=args.output.parent) as temp:
        stage=Path(temp)/"tables"
        stage.mkdir()
        build(args.research,args.base_raw,args.supplement,stage)
        stage.rename(args.output)
