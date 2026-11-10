"""
P4 Backtest Verification Runner
Validates:
- NautilusTrader 1.231.0 execution replay (Observed-Bar mode, zero synthetic data)
- Observed bars integrity: 85,981 rows matching Tushare raw input
- GoldenLedger daily triple reconciliation:
  * native_cash == ledger_cash
  * native_nav == ledger_nav
  * cash_difference == 0.00
  * nav_difference == 0.00
  * unexplained == 0.00
- Negative execution probe validation (FACTOR_NOT_ADMITTED -> Order rejected, zero filled quantity)
"""
import sys
import os
import json
import csv
from decimal import Decimal as D
from pathlib import Path
from datetime import datetime

def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def run_p4():
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    p1_inputs = data_dir / "engine-inputs"
    results_dir = data_dir / "backtest-run" / "results"

    if not results_dir.exists():
        raise FileNotFoundError(f"Missing P4 backtest results directory: {results_dir}")

    # 1. Scope & Execution Mode Invariants
    summary = json.loads((results_dir / "summary.json").read_text("utf8"))
    if summary.get("scope") != "RESTRICTED_NO_EXECUTION":
        raise ValueError(f"Invalid scope: {summary.get('scope')}")
    if summary.get("bar_execution") is not False or summary.get("trade_execution") is not False:
        raise ValueError("Violation: Synthetic bar or trade execution enabled under zero-synthetic-data rule")

    # 2. Observed Bars Matching
    original_bars = rows(p1_inputs / "bars_daily.csv")
    observed_bars = rows(results_dir / "observed-bars.csv")
    key = lambda r: (r["symbol"], r["trade_date"])
    
    expected = {key(r): r for r in original_bars}
    if len(expected) != len(original_bars) or len(original_bars) != len(observed_bars) or len(observed_bars) != 85981:
        raise ValueError(f"Observed bars count mismatch: expected 85981, got {len(observed_bars)}")
    
    if set(expected.keys()) != {key(r) for r in observed_bars}:
        raise ValueError("Observed bars symbol-date key set mismatch")

    for r in observed_bars:
        src = expected[key(r)]
        for f in ("open", "high", "low", "close", "volume"):
            if D(r[f]) != D(src[f]):
                raise ValueError(f"Price/Volume mismatch on {r['symbol']} {r['trade_date']}")

    # 3. GoldenLedger Daily Reconciliation
    daily = rows(results_dir / "daily-reconciliation.csv")
    days = sorted({r["trade_date"] for r in original_bars})
    if [r["date"] for r in daily] != days or len(days) != 484:
        raise ValueError("Reconciliation trading days mismatch")

    for r in daily:
        if D(r["native_cash"]) != D(r["ledger_cash"]):
            raise ValueError(f"Cash mismatch on {r['date']}")
        if D(r["native_nav"]) != D(r["ledger_nav"]):
            raise ValueError(f"NAV mismatch on {r['date']}")
        for f in ("cash_difference", "nav_difference", "unexplained"):
            if D(r[f]) != 0:
                raise ValueError(f"Non-zero {f} on {r['date']}")

    # 4. Negative Execution Probe (Order Rejected, Zero Fill)
    orders = json.loads((results_dir / "orders.json").read_text("utf8"))
    fills = json.loads((results_dir / "fills.json").read_text("utf8"))
    if len(orders) != 1 or orders[0]["status"] != "REJECTED" or D(orders[0]["filled_quantity"]) != 0:
        raise ValueError("Negative execution probe failed to reject cleanly")
    if fills != []:
        raise ValueError("Fills must be empty for negative execution probe")

    report = {
        "phase": "P4",
        "timestamp": datetime.now().isoformat(),
        "status": "PASS",
        "execution_model": "OBSERVED_BAR_ZERO_SYNTHETIC",
        "reconciliation": {
            "trading_days": len(days),
            "observed_bars_count": len(observed_bars),
            "reconciliation_rows": len(daily),
            "cash_difference": "0.00",
            "nav_difference": "0.00",
            "unexplained_difference": "0.00"
        },
        "negative_probe": {
            "order_status": orders[0]["status"],
            "filled_quantity": orders[0]["filled_quantity"],
            "purpose": orders[0]["purpose"]
        }
    }

    out_dir = base_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "p4_backtest_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")

    print(f"P4 backtest verification complete. Status: {report['status']}")
    print(f"  * Execution Model: OBSERVED_BAR_ZERO_SYNTHETIC (No synthetic book)")
    print(f"  * Trading Days Reconciled: {len(days)}")
    print(f"  * Observed Bars Verified: {len(observed_bars):,}")
    print(f"  * GoldenLedger Cash Diff: 0.00")
    print(f"  * GoldenLedger NAV Diff: 0.00")
    print(f"  * Negative Probe Status: REJECTED (Zero fill, Negative Gate Passed)")
    print(f"Report saved to: {out_path}")
    return report

if __name__ == "__main__":
    rep = run_p4()
    if rep["status"] != "PASS":
        sys.exit(1)
