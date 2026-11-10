"""Restricted native NT observation and Decimal reconciliation; no execution model permitted."""
import argparse
import csv
import hashlib
import json
import sys
import tempfile
from collections import Counter,defaultdict
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parent/'upstream'))
from engine.golden_ledger import GoldenLedger
from engine.fee_model import get_ashare_rates_for_date
from nautilus_trader.backtest.engine import BacktestEngine,BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import CNY
from nautilus_trader.model.data import Bar,BarType
from nautilus_trader.model.enums import OmsType,AccountType,OrderSide
from nautilus_trader.model.identifiers import Venue,TraderId,InstrumentId,Symbol,ClientOrderId
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Money,Price,Quantity
from nautilus_trader.trading.strategy import Strategy
import nautilus_trader

TZ=ZoneInfo('Asia/Shanghai'); VENUE=Venue('ASHARE')
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf8')
def table(path,rows,fields=None):
    with path.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields or list(rows[0]));writer.writeheader();writer.writerows(rows)
def checked(root,relative):
    release=json.loads((root/'release.json').read_text('utf8'))
    path=root/relative
    if hashlib.sha256(path.read_bytes()).hexdigest()!=release['sha256'][relative]:raise ValueError('Input hash mismatch: '+relative)
    return path

def run(root,out):
    if nautilus_trader.__version__!='1.231.0':raise ValueError('Pinned NT runtime required')
    p1=root/'P0-P1';p3=root/'P3'
    bars=read(checked(p1,'engine-inputs/bars_daily.csv'))
    drafts=read(checked(p3,'results/pretrade-drafts.csv'))
    gate=json.loads(checked(p3,'results/formal-gate.json').read_text('utf8'))
    if gate['status']!='FACTOR_NOT_ADMITTED':raise ValueError('Reference admission state changed; re-review required')
    blocked=json.loads(checked(p1,'engine-inputs/blocked_actions.json').read_text('utf8'))
    actions=json.loads(checked(p1,'engine-inputs/corporate_actions.json').read_text('utf8'))
    save(out/'corporate-action-gate.json',dict(accepted_contracts=len(actions),blocked=blocked,
        applied_to_positions=0,reason='No held shares or fills; nonzero entitlements untested'))
    table(out/'strategy-gates.csv',[dict(case=r['case'],symbol=r['asset'],signal_date=r['signal_date'],
        execution_date=r['assessment_date'],requested_delta=r['conditional_delta'],status='BLOCKED',submitted=False,
        reasons='FACTOR_NOT_ADMITTED|DIAGNOSTIC_ACCOUNT_INPUT|NO_AUTHORIZED_EXECUTION_MODEL') for r in drafts])
    expected=Counter(r['trade_date'] for r in bars)
    instruments={};types={};groups=defaultdict(list)
    engine=BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId('P4-001'),logging=LoggingConfig(bypass_logging=True)))
    engine.add_venue(venue=VENUE,oms_type=OmsType.NETTING,account_type=AccountType.CASH,base_currency=CNY,
        starting_balances=[Money(1000000,CNY)],bar_execution=False,trade_execution=False)
    ledger=GoldenLedger(D('1000000'))
    class Observer(Strategy):
        def on_start(self):
            self.observed=[];self.daily=[];self.counts=Counter();self.prices={};self.current=None;self.probed=False;self.rejects=[]
            for bt in types.values():self.subscribe_bars(bt)
        def on_order_rejected(self,event):
            self.rejects.append(dict(client_order_id=str(event.client_order_id),reason=event.reason))
        def on_bar(self,bar):
            day=datetime.fromtimestamp(bar.ts_event/1e9,TZ).date().isoformat()
            asset=bar.bar_type.instrument_id.symbol.value
            if day!=self.current:
                ledger.on_trade_day_start(day);self.prices={};self.current=day
            row=dict(symbol=asset,trade_date=day,**{k:str(getattr(bar,k)) for k in ('open','high','low','close','volume')})
            self.observed.append(row);self.prices[asset]=bar.close.as_decimal();self.counts[day]+=1
            if asset=='300266.SZ' and not self.probed:
                self.probed=True
                self.submit_order(self.order_factory.market(instrument_id=instruments[asset].id,order_side=OrderSide.BUY,
                    quantity=Quantity.from_int(100),client_order_id=ClientOrderId('P4-NEGATIVE-001')))
            if self.counts[day]==expected[day]:
                nav=ledger.mark_to_market(day,self.prices)
                account=self.cache.account_for_venue(VENUE)
                cash=account.balance_total(CNY).as_decimal()
                if self.cache.positions_open() or ledger.fills:raise RuntimeError('Unexpected execution')
                self.daily.append(dict(date=day,native_cash=str(cash),ledger_cash=str(nav.cash),
                    native_nav=str(cash),ledger_nav=str(nav.total_equity),cash_difference=str(cash-nav.cash),
                    nav_difference=str(cash-nav.total_equity),receivables=str(nav.receivable_dividends),
                    shares='0',sellable='0',price_pnl='0',dividend_pnl='0',fees='0',cash_pnl='0',unexplained='0',
                    scope='EMPTY_ACCOUNT_NO_EXECUTION'))
    try:
        for asset in sorted({r['symbol'] for r in bars}):
            inst=Equity(instrument_id=InstrumentId(Symbol(asset),VENUE),raw_symbol=Symbol(asset[:6]),currency=CNY,
                price_precision=2,price_increment=Price.from_str('0.01'),lot_size=Quantity.from_int(100),ts_event=0,ts_init=0)
            instruments[asset]=inst;types[asset]=BarType.from_str(f'{inst.id}-1-DAY-LAST-EXTERNAL');engine.add_instrument(inst)
        for r in bars:
            values=[]
            for key in ('open','high','low','close'):
                value=D(r[key])
                if not value.is_finite() or value<=0 or value!=value.quantize(D('.01')):raise ValueError('Invalid observed price')
                values.append(Price.from_str(format(value,'.2f')))
            vol=D(r['volume'])
            if not vol.is_finite() or vol<0 or vol!=vol.to_integral_value():raise ValueError('Invalid share volume')
            stamp=int(datetime.fromisoformat(r['trade_date']+'T15:00:00').replace(tzinfo=TZ).timestamp()*1e9)
            groups[r['symbol']].append(Bar(types[r['symbol']],*values,Quantity.from_int(int(vol)),stamp,stamp))
        for asset,records in sorted(groups.items()):engine.add_data(records)
        observer=Observer();engine.add_strategy(observer);engine.run()
        orders=[dict(client_order_id=str(o.client_order_id),status=o.status.name,filled_quantity=str(o.filled_qty),
            purpose='NEGATIVE_EXECUTION_PROBE') for o in engine.cache.orders()]
        if len(orders)!=1 or orders[0]['status']!='REJECTED' or D(orders[0]['filled_quantity'])!=0:raise RuntimeError('Execution guard failed')
        if len(observer.observed)!=len(bars) or dict(observer.counts)!=dict(expected):raise RuntimeError('Incomplete market replay')
        table(out/'observed-bars.csv',sorted(observer.observed,key=lambda r:(r['trade_date'],r['symbol'])))
        table(out/'daily-reconciliation.csv',observer.daily)
        save(out/'orders.json',orders);save(out/'rejections.json',observer.rejects);save(out/'fills.json',[])
        # Raw NT reports are evidence of native cache state, not reconstructed orders or fills.
        engine.trader.generate_orders_report().to_csv(out/'native-orders.csv')
        engine.trader.generate_fills_report().to_csv(out/'native-fills.csv')
        engine.trader.generate_account_report(VENUE).to_csv(out/'native-account.csv')
        table(out/'fee-schedule.csv',[dict(date=day,**{k:str(v) for k,v in get_ashare_rates_for_date(day).items()},
            source='PINNED_ENGINE_DEFAULTS_NOT_BROKER_CONFIRMED') for day in sorted(expected)])
        table(out/'fees.csv',[],['fill_id','commission','transfer_fee','stamp_duty','total_fee','currency'])
        table(out/'industry-attribution.csv',[],['date','industry','price_pnl','dividend_pnl','fees','total_pnl'])
        result=dict(scope='RESTRICTED_NO_EXECUTION',runtime=nautilus_trader.__version__,bars=len(observer.observed),
            assets=len(instruments),sessions=len(observer.daily),bar_execution=False,trade_execution=False,
            market_inputs=dict(Bar=len(bars),TradeTick=0,QuoteTick=0,BookDelta=0),fills=0,
            strategy_orders_submitted=0,negative_probe_orders=1,full_account_acceptance='BLOCKED',
            attribution='EMPTY_ACCOUNT_ONLY',nonzero_fees='NOT_TESTED',nonzero_corporate_actions='NOT_TESTED')
        save(out/'summary.json',result)
        return result
    finally:engine.dispose()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
    if args.output.exists():raise SystemExit('Choose a new output directory')
    with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp:
        stage=Path(tmp)/'result';stage.mkdir()
        result=run(Path(__file__).resolve().parents[1],stage)
        stage.rename(args.output)
        print(json.dumps(result,ensure_ascii=False))
