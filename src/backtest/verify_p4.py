"""Independent checks of the restricted P4 replay; no fabricated market or fill fixtures."""
import csv
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def verify(root):
    p4=root/'P4'; out=p4/'results'
    result=json.loads((out/'summary.json').read_text('utf8'))
    assert result['scope']=='RESTRICTED_NO_EXECUTION'
    assert result['bar_execution'] is False and result['trade_execution'] is False
    original=rows(root/'P0-P1/engine-inputs/bars_daily.csv')
    observed=rows(out/'observed-bars.csv')
    key=lambda r:(r['symbol'],r['trade_date'])
    expected={key(r):r for r in original}
    assert len(expected)==len(original)==len(observed)==85981
    assert {key(r) for r in observed}==set(expected)
    for r in observed:
        source=expected[key(r)]
        for field in ('open','high','low','close','volume'):assert D(r[field])==D(source[field])
    days=sorted({r['trade_date'] for r in original})
    daily=rows(out/'daily-reconciliation.csv')
    assert [r['date'] for r in daily]==days and len(days)==484
    for r in daily:
        assert D(r['native_cash'])==D(r['ledger_cash'])==D('1000000')
        assert D(r['ledger_nav'])==D(r['native_nav'])==D('1000000')
        for field in ('cash_difference','nav_difference','receivables','shares','sellable','price_pnl','dividend_pnl','fees','cash_pnl','unexplained'):
            assert D(r[field])==0,(r['date'],field)
    orders=json.loads((out/'orders.json').read_text('utf8'))
    assert len(orders)==1 and orders[0]['status']=='REJECTED' and D(orders[0]['filled_quantity'])==0
    assert orders[0]['purpose']=='NEGATIVE_EXECUTION_PROBE'
    assert json.loads((out/'fills.json').read_text('utf8'))==[]
    native_orders=rows(out/'native-orders.csv')
    assert len(native_orders)==1 and native_orders[0]['status']=='REJECTED' and D(native_orders[0]['filled_qty'])==0
    assert rows(out/'native-fills.csv')==[] and rows(out/'fees.csv')==[]
    native_account=rows(out/'native-account.csv')
    assert len(native_account)==1 and D(native_account[0]['total'])==D('1000000')
    assert D(native_account[0]['free'])==D('1000000') and D(native_account[0]['locked'])==0
    schedule=rows(out/'fee-schedule.csv')
    assert [r['date'] for r in schedule]==days
    for r in schedule:
        assert D(r['stamp_duty_rate'])==(D('.001') if r['date']<'2023-08-28' else D('.0005'))
        assert D(r['transfer_fee_rate'])==D('.00001')
    gates=rows(out/'strategy-gates.csv')
    drafts=rows(root/'P3/results/pretrade-drafts.csv')
    assert len(gates)==len(drafts)==991
    assert all(r['status']=='BLOCKED' and r['submitted']=='False' for r in gates)
    for r,draft in zip(gates,drafts):
        assert (r['symbol'],r['signal_date'],r['execution_date'],r['requested_delta'])==(draft['asset'],draft['signal_date'],draft['assessment_date'],draft['conditional_delta'])
        assert 'FACTOR_NOT_ADMITTED' in r['reasons'] and 'NO_AUTHORIZED_EXECUTION_MODEL' in r['reasons']
    assert result['bars']==85981 and result['assets']==197 and result['sessions']==484
    return dict(bars_reconciled=len(observed),sessions_reconciled=len(daily),strategy_requests_blocked=len(gates),
        negative_probe_rejections=1,fills=0,max_cash_difference='0.00',max_nav_difference='0.00',
        nonzero_accounting_validation='NOT_RUN',strategy_performance='NOT_AVAILABLE')

if __name__=='__main__':
    print(json.dumps(verify(Path(__file__).resolve().parents[1]),indent=2))
