"""
A-Share Invariant Safety Core (A 股 10 大不可逾越安全内核)
Inspired by yebof/quant-agent's Invariant Core architecture.

These rules are hardcoded in deterministic Python.
No LLM, Agent, Prompt, or Evolutionary Algorithm is permitted to bypass,
override, disable, or relax any invariant defined herein.
"""
from __future__ import annotations

import decimal
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple


class InvariantViolationError(Exception):
    """Raised when an action or state violates an inviolable safety invariant."""
    pass


@dataclass(frozen=True)
class ExecutionFriction:
    """Computed deterministic transaction friction breakdown."""
    gross_value: float
    stamp_duty: float
    broker_commission: float
    transfer_fee: float
    slippage_cost: float
    net_value: float  # For buy: gross + fees; For sell: gross - fees

    @property
    def total_friction(self) -> float:
        return self.stamp_duty + self.broker_commission + self.transfer_fee + self.slippage_cost


class AShareInvariantSafetyCore:
    """
    Deterministic A-Share Invariant Engine enforcing all 10 Microstructure Invariants.
    """

    # INV-05, INV-06, INV-07, INV-08 Constants
    COMMISSION_RATE = 0.00025          # 万 2.5
    MIN_COMMISSION_CNY = 5.0           # 单笔最低 5 元保底
    TRANSFER_FEE_RATE = 0.00002        # 十万分之 2 (双边)
    MIN_SLIPPAGE_BPS = 0.0005          # 开盘调仓单边冲击 5 bps
    STAMP_DUTY_SPLIT_DATE = "2023-08-28"
    STAMP_DUTY_PRE = 0.0010            # 2023-08-28 前千 1
    STAMP_DUTY_POST = 0.0005           # 2023-08-28 后减半为万 5
    MAX_ADV_PARTICIPATION = 0.05       # INV-09: 5% ADV20 单日容量硬约束

    # -------------------------------------------------------------
    # INV-01: T+1 Settlement Rule
    # -------------------------------------------------------------
    @staticmethod
    def validate_t_plus_1_sell(sellable_shares: int, requested_sell_qty: int, symbol: str) -> int:
        """
        Validates that requested sell order only consumes sellable shares from T-1 or earlier.
        Shares purchased on T day are locked and cannot be sold.
        """
        if requested_sell_qty <= 0:
            return 0
        if requested_sell_qty > sellable_shares:
            raise InvariantViolationError(
                f"[INV-01 Violation] {symbol}: Requested sell qty {requested_sell_qty} "
                f"exceeds sellable shares {sellable_shares} (T+1 locked shares cannot be sold)."
            )
        return requested_sell_qty

    # -------------------------------------------------------------
    # INV-02: Limit-Up Buy Prohibition
    # -------------------------------------------------------------
    @staticmethod
    def check_limit_up_buy_admissibility(
        open_price: float,
        low_price: float,
        up_limit: float,
        symbol: str
    ) -> bool:
        """
        Returns False if stock is locked at daily upper limit (一字涨停), preventing any buy fills.
        """
        is_limit_up_locked = (open_price >= up_limit - 0.01) and (low_price >= up_limit - 0.01)
        if is_limit_up_locked:
            return False
        return True

    # -------------------------------------------------------------
    # INV-03: Limit-Down Sell Prohibition
    # -------------------------------------------------------------
    @staticmethod
    def check_limit_down_sell_admissibility(
        open_price: float,
        high_price: float,
        down_limit: float,
        symbol: str
    ) -> bool:
        """
        Returns False if stock is locked at daily lower limit (一字跌停), preventing any exit/sell fills.
        """
        is_limit_down_locked = (open_price <= down_limit + 0.01) and (high_price <= down_limit + 0.01)
        if is_limit_down_locked:
            return False
        return True

    # -------------------------------------------------------------
    # INV-04: Suspension Lock & Deferred Delta
    # -------------------------------------------------------------
    @staticmethod
    def handle_suspension(
        is_suspended: bool,
        current_position: int,
        target_shares: int,
        symbol: str
    ) -> Tuple[int, int]:
        """
        If suspended, position is 100% frozen.
        Returns: (executable_delta=0, deferred_delta=target - current)
        """
        if is_suspended:
            deferred_delta = target_shares - current_position
            return (0, deferred_delta)
        return (target_shares - current_position, 0)

    # -------------------------------------------------------------
    # INV-05, INV-06, INV-07, INV-08: Complete Friction Calculation
    # -------------------------------------------------------------
    @classmethod
    def calculate_trade_friction(
        cls,
        action: str,  # "BUY" or "SELL"
        trade_date: str,
        fill_price: float,
        shares: int,
        apply_slippage: bool = True
    ) -> ExecutionFriction:
        """
        Enforces statutory stamp duty, broker commission with 5 RMB floor,
        transfer fees, and minimum mandatory 5 bps execution slippage.
        """
        if shares <= 0 or fill_price <= 0:
            return ExecutionFriction(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        # Base Gross Value
        gross_value = float(shares) * fill_price

        # INV-08: Slippage
        slippage_rate = cls.MIN_SLIPPAGE_BPS if apply_slippage else 0.0
        slippage_cost = gross_value * slippage_rate

        # INV-05: Statutory Stamp Duty (Sell-only)
        if action.upper() == "SELL":
            stamp_rate = cls.STAMP_DUTY_POST if trade_date >= cls.STAMP_DUTY_SPLIT_DATE else cls.STAMP_DUTY_PRE
            stamp_duty = gross_value * stamp_rate
        else:
            stamp_duty = 0.0

        # INV-06: Broker Commission (max of 5.0 CNY or 0.025%)
        broker_commission = max(cls.MIN_COMMISSION_CNY, gross_value * cls.COMMISSION_RATE)

        # INV-07: Transfer Fee (Dual-side 0.002%)
        transfer_fee = gross_value * cls.TRANSFER_FEE_RATE

        if action.upper() == "BUY":
            # Net cash consumed = gross + slippage_cost + commission + transfer
            net_value = gross_value + slippage_cost + broker_commission + transfer_fee
        else:
            # Net cash received = gross - slippage_cost - stamp_duty - commission - transfer
            net_value = gross_value - slippage_cost - stamp_duty - broker_commission - transfer_fee

        return ExecutionFriction(
            gross_value=gross_value,
            stamp_duty=stamp_duty,
            broker_commission=broker_commission,
            transfer_fee=transfer_fee,
            slippage_cost=slippage_cost,
            net_value=net_value
        )

    # -------------------------------------------------------------
    # INV-09: ADV20 Liquidity Participation Cap
    # -------------------------------------------------------------
    @classmethod
    def apply_adv20_cap(cls, requested_shares: int, fill_price: float, adv20_amount: float, symbol: str) -> int:
        """
        Caps order value to <= 5% of trailing 20-day ADV.
        Truncates order to maximum allowable board lots (100 shares).
        """
        if adv20_amount <= 0 or fill_price <= 0:
            return 0
        max_allowable_value = adv20_amount * cls.MAX_ADV_PARTICIPATION
        max_allowable_shares = int(max_allowable_value / fill_price) // 100 * 100
        if requested_shares > max_allowable_shares:
            return max_allowable_shares
        return requested_shares

    # -------------------------------------------------------------
    # INV-10: Golden Ledger Decimal Identity
    # -------------------------------------------------------------
    @staticmethod
    def audit_golden_ledger_identity(
        native_cash: float,
        reference_cash: float,
        native_nav: float,
        reference_nav: float,
        trade_date: str,
        tolerance: float = 1e-4
    ) -> None:
        """
        Enforces decimal equality between native broker ledger and reference ledger.
        If diff exceeds tolerance, triggers immediate InvariantViolationError crash stop.
        """
        cash_diff = abs(native_cash - reference_cash)
        nav_diff = abs(native_nav - reference_nav)
        if cash_diff > tolerance or nav_diff > tolerance:
            raise InvariantViolationError(
                f"[INV-10 Violation] Golden Ledger mismatch on {trade_date}: "
                f"cash_diff={cash_diff:.6f}, nav_diff={nav_diff:.6f}. Halting execution."
            )
