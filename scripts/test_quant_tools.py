"""
Quick smoke test for quant tools in ashare-quant-platform.
"""
import sys
import json
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from src.agents.quant_tools import (
    tushare_snapshot_query, SnapshotQueryArgs,
    factor_evaluate, FactorEvaluateArgs,
    strategy_optimize, StrategyOptimizeArgs,
    risk_project, RiskProjectArgs,
    backtest_replay, BacktestReplayArgs
)

def test_all_tools():
    print("Testing tushare_snapshot_query...")
    res1 = json.loads(tushare_snapshot_query(SnapshotQueryArgs(dataset="market-v1")))
    assert res1["status"] == "OK" and res1["total_bars"] == 85981
    print("  * Data Tool PASS:", res1["fingerprint"][:16])

    print("Testing factor_evaluate...")
    res2 = json.loads(factor_evaluate(FactorEvaluateArgs(factor_id="momentum20")))
    assert res2["status"] == "OK" and res2["formal_gate"]["decision"] == "FACTOR_NOT_ADMITTED"
    print("  * Factor Tool PASS (Negative Gate Enforced):", res2["formal_gate"]["decision"])

    print("Testing strategy_optimize...")
    res3 = json.loads(strategy_optimize(StrategyOptimizeArgs()))
    assert res3["status"] == "OK" and res3["total_targets"] == 970
    print("  * Strategy Tool PASS:", res3["total_targets"], "targets across", res3["unique_weeks"], "weeks")

    print("Testing risk_project...")
    res4 = json.loads(risk_project(RiskProjectArgs()))
    assert res4["status"] == "OK" and res4["t_plus_1_violations"] == 0
    print("  * Risk Tool PASS: T+1 violations =", res4["t_plus_1_violations"])

    print("Testing backtest_replay...")
    res5 = json.loads(backtest_replay(BacktestReplayArgs()))
    assert res5["status"] == "OK" and res5["reconciliation"]["cash_difference"] == "0.00"
    print("  * Backtest Tool PASS: Cash diff =", res5["reconciliation"]["cash_difference"])

    print("\nALL 5 QUANT TOOLS SMOKE TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all_tools()
