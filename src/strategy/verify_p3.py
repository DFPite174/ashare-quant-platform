"""Independent read-only reconciliation of all published P3 targets and decisions."""
import json
import math
from pathlib import Path

import duckdb
import pandas as pd


def verify(root):
    p3=root/"P3"
    cfg=json.loads((p3/"policy.json").read_text("utf-8-sig"))
    sql=duckdb.connect()
    base=root/"P0-P1/market-v1"
    sql.register("days",sql.read_parquet(str(base/"security_days.parquet")))
    sql.register("bars",sql.read_parquet(str(base/"bars_unadjusted.parquet")))
    sql.register("master",sql.read_parquet(str(base/"security_master.parquet")))
    market=sql.sql("""
        SELECT d.date,d.asset,d.close,d.status,d.up_limit,d.down_limit,d.st_listed,
               d.industry_l1,m.market,b.high,b.low,
               avg(CASE WHEN d.status='FULL_DAY_SUSPENSION' THEN 0 ELSE b.amount END)
                 OVER w AS trailing_avg,
               count(CASE WHEN d.status='FULL_DAY_SUSPENSION' THEN 0 ELSE b.amount END)
                 OVER w AS trailing_count
        FROM days d LEFT JOIN bars b USING(asset,date) JOIN master m ON d.asset=m.ts_code
        WINDOW w AS (PARTITION BY d.asset ORDER BY d.date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)
        """).df().set_index(["date","asset"])
    sql.close()
    targets=pd.read_csv(p3/"results/weekly-targets.csv")
    scores=pd.read_csv(root/"P2/research-run/factor_input.csv")
    calendar=pd.read_csv(root/"P0-P1/research/calendar.csv").date.tolist()
    dates={day:nxt for day,nxt in zip(calendar,calendar[1:]) if
           pd.Timestamp(day).isocalendar()[:2]!=pd.Timestamp(nxt).isocalendar()[:2]}
    expected=[]
    for day,nxt in dates.items():
        ranked=scores.loc[scores.date.eq(day)].sort_values(["factor","asset"],ascending=[False,True]).head(10)
        if len(ranked)==10:
            expected.extend((day,nxt,a) for a in ranked.asset)
    assert list(targets[["signal_date","assessment_date","asset"]].itertuples(index=False,name=None))==expected
    assert targets.target_weight.eq(.1).all()
    checks=pd.read_csv(p3/"results/risk-decisions.csv")
    drafts=pd.read_csv(p3/"results/pretrade-drafts.csv").set_index(["case","asset"],verify_integrity=True)
    assert drafts["asof"].eq(drafts.signal_date).all() and checks["asof"].eq(checks.assessment_date).all()
    assert len(drafts)==len(checks)
    reports=json.loads((p3/"results/portfolios.json").read_text("utf8"))
    assert len({r["case"] for r in reports})==len(reports)
    assert not checks.duplicated(["case","asset"]).any()
    for report in reports:
        book=checks.loc[checks["case"].eq(report["case"])]
        states=report["input_positions"]
        cash=report["cash"]
        day=report["assessment_date"]
        equity=cash+sum(states.get(r.asset,[0,0])[0]*r.mark for r in book.itertuples())
        assert abs(report["equity"]-equity)<1e-5
        buy_cost=0
        for r in book.itertuples():
            m=market.loc[(day,r.asset)]
            plan=drafts.loc[(report["case"],r.asset)]
            assert min(0,plan.conditional_delta)<=r.conditional_delta<=max(0,plan.conditional_delta)
            assert plan.mark_date<=plan.signal_date
            if m.trailing_count==20:
                assert abs(plan.adv20_cny-m.trailing_avg)<=max(.01,abs(m.trailing_avg)*1e-12)
            assert plan.requested_delta==plan.precheck_requested_delta
            assert plan.deferred_delta+plan.conditional_delta==plan.requested_delta
            assert r.actual_shares==r.actual_shares_after_check==states.get(r.asset,[0,0])[0]
            assert r.sellable_shares==states.get(r.asset,[0,0])[1]
            assert r.locked_shares==r.actual_shares-r.sellable_shares
            assert r.requested_delta==math.floor(equity*r.raw_weight/r.mark)-r.actual_shares
            assert r.conditional_shares==r.actual_shares+r.conditional_delta
            assert r.requested_delta==r.conditional_delta+r.deferred_delta
            assert min(0,r.requested_delta)<=r.conditional_delta<=max(0,r.requested_delta)
            if m.trailing_count==20:
                assert abs(r.adv20_cny-m.trailing_avg)<max(.01,abs(m.trailing_avg)*1e-12)
            else:
                assert pd.isna(r.adv20_cny)
            if not r.conditional_delta:continue
            assert m.status=="OBSERVED_BAR" and r.mark==m.close and r.mark_date==day
            assert m.trailing_count==20 and abs(r.conditional_delta)*r.mark<=cfg["adv_fraction"]*m.trailing_avg+1e-5
            assert m.down_limit>0 and m.up_limit/m.down_limit<=2 and m.down_limit<=r.mark<=m.up_limit
            minimum,step,max_qty={"主板":(100,100,1000000),"创业板":(100,100,300000),"科创板":(200,1,100000)}[m.market]
            q=abs(r.conditional_delta)
            assert q<=max_qty
            if r.conditional_delta>0:
                assert not m.st_listed and r.mark<m.up_limit and pd.notna(m.industry_l1)
                assert r.conditional_shares*r.mark<=cfg["name_cap"]*equity+1e-7
                assert q>=minimum and q%step==0
                buy_cost+=q*r.mark*(1+cfg["fee_buffer"])+cfg["min_fee"]
            else:
                assert r.mark>m.down_limit and q<=r.sellable_shares
                assert q==r.actual_shares or (q>=minimum and q%step==0)
        assert abs(cash-buy_cost-report["unreserved_cash_after_requests"])<=1e-5
        if buy_cost:
            assert cash-buy_cost>=equity*cfg["cash_floor"]-1e-6
        for group,frame in book.groupby("industry"):
            worst=(frame.actual_shares+frame.conditional_delta.clip(lower=0))*frame.mark
            if frame.conditional_delta.gt(0).any():
                assert worst.sum()<=cfg["industry_cap"]*equity+1e-5
        assert not report["account_mutated"]
    cases=checks.set_index(["case","asset"])
    def delta(case,a):return int(cases.loc[(case,a),"conditional_delta"])
    assert [delta("suspension-reopen-2023-05-"+str(d),"600446.SH") for d in (23,24,25,26)]==[0,0,0,-1000]
    assert delta("zero-sellable","600446.SH")==0 and delta("partial-sellable","600446.SH")==-100
    assert delta("odd-lot-exit","600446.SH")==-55
    assert delta("limit-up-buy","000936.SZ")==0 and delta("limit-up-sell","000936.SZ")<0
    assert delta("limit-down-buy","600446.SH")>0
    assert delta("no-sell-proceeds","000936.SZ")==0 and delta("no-sell-proceeds","600446.SH")<0
    cap=drafts.loc[("adv-cap","301309.SZ")]
    assert "ADV20_CAP" in cap.reasons and 0<cap.conditional_delta<cap.requested_delta
    assert cap.conditional_delta*cap.mark<=cfg["adv_fraction"]*cap.adv20_cny<(cap.conditional_delta+100)*cap.mark
    locked=next(r for r in reports if r["case"]=="locked-industry")
    assert locked["unresolved"] and locked["residual"]["industry_over"] and locked["residual"]["name_over"]
    for day,a,side in [("2023-06-14","000936.SZ","up"),("2023-05-24","600446.SH","down")]:
        row=market.loc[(day,a)]
        assert row.low==row.high==(row.up_limit if side=="up" else row.down_limit)
    weekly=checks.loc[checks["case"].str.startswith("weekly-")]
    return dict(weeks=targets.signal_date.nunique(),targets=len(targets),decision_rows=len(checks),
        weekly_nonzero=int(weekly.conditional_delta.ne(0).sum()),weekly_zero=int(weekly.conditional_delta.eq(0).sum()),
        weekly_with_deferred=int(weekly.deferred_delta.ne(0).sum()),diagnostic_extra_cases=len(reports)-targets.signal_date.nunique(),
        illegal_requests_passing=0,mutated_positions=0,fills=0)


if __name__=="__main__":
    print(json.dumps(verify(Path(__file__).resolve().parents[1]),indent=2))
