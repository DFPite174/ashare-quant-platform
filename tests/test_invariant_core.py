"""
Unit Tests for A-Share Invariant Safety Core (10 Inviolable Rules).
"""
import pytest
from src.core.invariant_core import (
    AShareInvariantSafetyCore,
    InvariantViolationError,
    ExecutionFriction
)

def test_inv_01_t_plus_1_settlement():
    core = AShareInvariantSafetyCore()
    # Sellable 1000 shares, requesting 1000 -> PASS
    assert core.validate_t_plus_1_sell(1000, 1000, "600519.SH") == 1000
    # Sellable 1000 shares, requesting 1200 (attempting to sell T+0 locked 200 shares) -> REJECT
    with pytest.raises(InvariantViolationError) as exc_info:
        core.validate_t_plus_1_sell(1000, 1200, "600519.SH")
    assert "INV-01 Violation" in str(exc_info.value)


def test_inv_02_limit_up_buy_prohibition():
    core = AShareInvariantSafetyCore()
    # Upper limit 11.00, open=11.00, low=11.00 (一字涨停锁死) -> False (BLOCKED)
    assert not core.check_limit_up_buy_admissibility(11.00, 11.00, 11.00, "000001.SZ")
    # Upper limit 11.00, open=10.50, low=10.40 (正常交易开盘) -> True (ALLOWED)
    assert core.check_limit_up_buy_admissibility(10.50, 10.40, 11.00, "000001.SZ")


def test_inv_03_limit_down_sell_prohibition():
    core = AShareInvariantSafetyCore()
    # Down limit 9.00, open=9.00, high=9.00 (一字跌停锁死) -> False (CANNOT SELL)
    assert not core.check_limit_down_sell_admissibility(9.00, 9.00, 9.00, "000002.SZ")
    # Down limit 9.00, open=9.50, high=9.60 (正常交易开盘) -> True (ALLOWED)
    assert core.check_limit_down_sell_admissibility(9.50, 9.60, 9.00, "000002.SZ")


def test_inv_04_suspension_lock_and_deferred_delta():
    core = AShareInvariantSafetyCore()
    # Suspended stock: current 5000 shares, target 0 (liquidate) -> executable=0, deferred_delta=-5000
    executable, deferred = core.handle_suspension(is_suspended=True, current_position=5000, target_shares=0, symbol="600000.SH")
    assert executable == 0
    assert deferred == -5000

    # Normal stock: current 5000, target 0 -> executable=-5000, deferred=0
    executable, deferred = core.handle_suspension(is_suspended=False, current_position=5000, target_shares=0, symbol="600000.SH")
    assert executable == -5000
    assert deferred == 0


def test_inv_05_to_08_friction_and_stamp_reduction():
    core = AShareInvariantSafetyCore()
    # Scenario A: Sell 1000 shares @ 100.0 (gross 100,000) BEFORE 2023-08-28 (Stamp = 0.10%)
    f_pre = core.calculate_trade_friction("SELL", "2023-08-01", 100.0, 1000)
    assert f_pre.gross_value == 100000.0
    assert f_pre.stamp_duty == 100.0          # 0.10%
    assert f_pre.broker_commission == 25.0    # 100,000 * 0.00025 = 25.0 (exceeds 5.0)
    assert f_pre.transfer_fee == 2.0          # 100,000 * 0.00002 = 2.0
    assert f_pre.slippage_cost == 50.0        # 100,000 * 0.0005 = 50.0 (5 bps)
    assert f_pre.total_friction == 177.0

    # Scenario B: Sell 1000 shares @ 100.0 (gross 100,000) ON/AFTER 2023-08-28 (Stamp = 0.05% halved!)
    f_post = core.calculate_trade_friction("SELL", "2023-08-28", 100.0, 1000)
    assert f_post.stamp_duty == 50.0          # 0.05% HALVED!
    assert f_post.total_friction == 127.0

    # Scenario C: Buy small order 100 shares @ 10.0 (gross 1,000) -> Commission 5.0 CNY floor applied!
    f_small = core.calculate_trade_friction("BUY", "2024-01-02", 10.0, 100)
    assert f_small.gross_value == 1000.0
    assert f_small.stamp_duty == 0.0          # Buy has no stamp duty
    assert f_small.broker_commission == 5.0   # 1,000 * 0.00025 = 0.25 -> 5.0 FLOOR ENFORCED!


def test_inv_09_adv20_cap():
    core = AShareInvariantSafetyCore()
    # ADV20 = 20,000,000 CNY (2000万), 5% Cap = 1,000,000 CNY
    # Fill price = 50.0 -> max allowable shares = 1,000,000 / 50 = 20,000 shares
    # Requesting 50,000 shares -> Truncated to 20,000
    capped = core.apply_adv20_cap(requested_shares=50000, fill_price=50.0, adv20_amount=20000000.0, symbol="000858.SZ")
    assert capped == 20000

    # Requesting 10,000 shares -> Allowed 10,000
    capped2 = core.apply_adv20_cap(requested_shares=10000, fill_price=50.0, adv20_amount=20000000.0, symbol="000858.SZ")
    assert capped2 == 10000


def test_inv_10_golden_ledger_identity():
    core = AShareInvariantSafetyCore()
    # Exact match -> PASS
    core.audit_golden_ledger_identity(native_cash=1000000.0, reference_cash=1000000.0, native_nav=1000000.0, reference_nav=1000000.0, trade_date="2024-01-02")
    
    # Mismatch of 1.0 CNY -> Crash
    with pytest.raises(InvariantViolationError) as exc_info:
        core.audit_golden_ledger_identity(native_cash=1000000.0, reference_cash=999999.0, native_nav=1000000.0, reference_nav=1000000.0, trade_date="2024-01-02")
    assert "INV-10 Violation" in str(exc_info.value)
