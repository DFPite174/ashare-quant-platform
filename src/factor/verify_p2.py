"""Independent P2 release checks on daily quantiles, turnover, HAC, and truncated histories."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
from factor_research.data import load_dataset
from factor_research.generation import evaluate_definition
from verify_development import verify

root=Path(__file__).resolve().parent
dev=root.parent/'P0-P1/research'
run=root/'research-run'
evidence=verify(dev,run,ic_output=root/'independent_ic.csv')
manifest=json.loads((run/'manifest.json').read_text('utf8'))
for key,sha in manifest['artifact_sha256'].items():
    if hashlib.sha256((run/key).read_bytes()).hexdigest()!=sha:raise ValueError(key)

def check(a,b,title):
    a,b=a.sort_index(),b.sort_index()
    if not a.index.equals(b.index) or not a.columns.equals(b.columns):
        raise ValueError(title+' keys differ')
    x,y=a.to_numpy(float),b.to_numpy(float)
    if not np.array_equal(np.isnan(x),np.isnan(y)):
        raise ValueError(title+' missingness differs')
    diff=float(np.nanmax(np.abs(x-y)))
    if not np.isfinite(diff) or diff>1e-8: raise ValueError(title+' exceeds tolerance')
    evidence[title]=diff
clean=pd.read_csv(run/'clean_factor.csv')
horizons=['1D','5D','20D']
group=clean.groupby(['factor_quantile','date'])[horizons].mean()
stored=pd.read_csv(run/'quantile_returns.csv').set_index(['factor_quantile','date'])[horizons]
check(group,stored,'quantile_returns_max_error')
dates=pd.Index(pd.read_csv(run/'rank_ic.csv').date,name='date')
calendar=pd.read_csv(dev/'calendar.csv').date
previous=dict(zip(calendar.iloc[1:],calendar.iloc[:-1]))
sets=clean.groupby(['date','factor_quantile']).asset.agg(set).to_dict()
turn=pd.DataFrame(index=dates)
for q in range(1,6):
    turn['Q'+str(q)]=[len(sets[d,q]-sets[previous[d],q])/len(sets[d,q]) if (previous[d],q) in sets else np.nan for d in dates]
check(turn,pd.read_csv(run/'turnover.csv').set_index('date'),'turnover_max_error')
summary=json.loads((run/'summary.json').read_text('utf8'))
stats=summary['segments']['all']['rank_ic']
hac={}
for h in horizons:
    x=pd.read_csv(root/'independent_ic.csv')[h].to_numpy()
    centered=x-x.mean()
    lag=int(h[:-1])
    var=np.dot(centered,centered)+2*sum((1-j/(lag+1))*np.dot(centered[j:],centered[:-j]) for j in range(1,lag+1))
    se=np.sqrt(var)/len(x)
    hac[h]={'se_diff':float(abs(se-stats[h]['hac_se'])),'t_diff':float(abs(x.mean()/se-stats[h]['t_stat']))}
if max(v for s in hac.values() for v in s.values())>1e-8:raise ValueError('HAC mismatch')
evidence['hac_difference']=hac
ds=load_dataset(dev)
definition=json.loads((run/'factor_metadata.json').read_text('utf8'))['provenance']['definition']
original=pd.read_csv(run/'factor_input.csv',parse_dates=['date']).set_index(['date','asset'],verify_integrity=True)
cutoff=original.index.get_level_values('date').tz_localize('Asia/Shanghai')+pd.Timedelta(hours=18)
if not (pd.to_datetime(original.available_at,utc=True).array==cutoff).all():raise ValueError('Signal clock mismatch')
prefixes={}
for day in ['2023-02-07','2023-12-29','2024-12-02']:
    date=pd.Timestamp(day)
    prefix=replace(ds,calendar=ds.calendar[ds.calendar<=date],market=ds.market.loc[:date],universe=ds.universe.loc[:date],
                   feature_events=ds.feature_events.loc[ds.feature_events.available_at<=date.tz_localize('Asia/Shanghai')+pd.Timedelta(hours=18)])
    short=evaluate_definition(prefix,definition).dropna().sort_index()
    prior=original.loc[:date].factor.sort_index()
    if not short.index.equals(prior.index) or len(short)==0:raise ValueError('Prefix membership')
    error=float((short-prior).abs().max())
    if error>1e-8:raise ValueError('Prefix values')
    prefixes[day]={'observations':len(short),'max_abs_diff':error}
evidence['prefix']=prefixes
# Quantiles available at decision time include names with unknown future returns.
values=pd.read_csv(run/'factor_values.csv').dropna(subset=['factor']).set_index(['date','asset'])
decision_input=pd.read_csv(run/'factor_input.csv').set_index(['date','asset']).factor
decision=decision_input.groupby(level='date').transform(lambda s:pd.qcut(s,5,labels=False)+1)
check(decision.to_frame('q'),values.factor_quantile.to_frame('q'),'decision_quantiles_error')
ex=pd.read_csv(run/'exclusions.csv')
counts={'missing_factor':int(ex.factor_missing.sum()),'valid_factor_missing_label':int((~ex.factor_missing & ex.label_missing).sum()),
        'complete_input_but_not_retained':int((~ex.factor_missing & ~ex.label_missing & ~ex.retained).sum()),'retained':int(ex.retained.sum())}
if sum(counts.values())!=len(ex):raise ValueError('Exclusion accounting')
evidence['exclusive_counts']=counts
# Explicitly export horizon-specific path coverage, separately from common-sample analysis.
prices=ds.prices
eligible=ds.universe.eligible.eq(1)
hrows=[]
for n in [1,5,20]:
    path=prices.notna().rolling(n+1).sum().shift(-1-n).eq(n+1).stack(future_stack=True)
    good=path.reindex(eligible.index,fill_value=False) & eligible
    present=original.factor.reindex(eligible.index).notna()
    for d,block in good.groupby(level='date'):
        hrows.append([str(d.date()),n,int(eligible.loc[d].sum()),int(block.sum()),int((block & present.reindex(block.index)).sum())])
pd.DataFrame(hrows,columns=['date','horizon','eligible','complete_label','valid_factor_and_label']).to_csv(root/'horizon_coverage.csv',index=False)
(root/'independent-checks.json').write_text(json.dumps(evidence,indent=2,allow_nan=False),'utf8')
print(evidence)
