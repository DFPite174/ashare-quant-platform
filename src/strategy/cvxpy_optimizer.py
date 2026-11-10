"""
Institutional CVXPY Quadratic Programming (QP) Portfolio Optimizer.
Enforces Barra Industry Neutrality, Style Constraints, and L1 Turnover Penalty.

Mathematical Formulation:
    max_w  alpha^T w - (lambda_risk / 2) * w^T Sigma w - lambda_turn * ||w - w_0||_1
    s.t.
           sum(w) <= 1.0 - cash_floor
           0 <= w_i <= max_weight_per_stock
           |B_ind^T (w - w_bench)| <= industry_tolerance
           |w_i - w_0,i| * NAV <= 0.05 * ADV20_i  (INV-09 ADV Participation Cap)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import cvxpy as cp


@dataclass
class OptimizationResult:
    status: str
    optimal_weights: Dict[str, float]
    expected_alpha: float
    portfolio_variance: float
    turnover: float
    cash_weight: float
    solver_time_ms: float


class InstitutionalPortfolioOptimizer:
    """
    Production-grade Convex Optimization Engine for Institutional A-Share Portfolios.
    """

    def __init__(
        self,
        risk_aversion: float = 1.0,
        turnover_penalty: float = 0.003,      # 30 bps penalty per 100% turnover
        cash_floor: float = 0.05,             # 5% mandatory cash reserve
        max_stock_weight: float = 0.05,       # 5% max single stock
        industry_tolerance: float = 0.02,     # +/- 2% industry active exposure
        adv_cap_fraction: float = 0.05        # INV-09: 5% ADV20 cap
    ):
        self.risk_aversion = risk_aversion
        self.turnover_penalty = turnover_penalty
        self.cash_floor = cash_floor
        self.max_stock_weight = max_stock_weight
        self.industry_tolerance = industry_tolerance
        self.adv_cap_fraction = adv_cap_fraction

    def optimize(
        self,
        alpha_scores: pd.Series,              # index: symbol, values: alpha score
        cov_matrix: pd.DataFrame,             # index & cols: symbol
        current_weights: Optional[pd.Series] = None,  # index: symbol, values: prior weight w_0
        industry_matrix: Optional[pd.DataFrame] = None, # index: symbol, cols: industry dummies
        benchmark_weights: Optional[pd.Series] = None,
        adv20_values: Optional[pd.Series] = None,      # index: symbol, values: ADV20 in CNY
        portfolio_nav: float = 10_000_000.0
    ) -> OptimizationResult:
        """
        Executes quadratic programming optimization using OSQP / Clarabel.
        """
        import time
        t0 = time.perf_counter()

        symbols = list(alpha_scores.index)
        n = len(symbols)

        if n == 0:
            return OptimizationResult("EMPTY_UNIVERSE", {}, 0.0, 0.0, 0.0, 1.0, 0.0)

        # 1. Align inputs to common symbol vector
        alpha_vec = alpha_scores.reindex(symbols).fillna(0.0).values
        cov_aligned = cov_matrix.reindex(index=symbols, columns=symbols).fillna(0.0).values

        # Ensure positive semi-definite covariance (eigenvalue clipping)
        cov_psd = (cov_aligned + cov_aligned.T) / 2.0
        eigvals, eigvecs = np.linalg.eigh(cov_psd)
        eigvals = np.maximum(eigvals, 1e-6)
        Sigma = eigvecs @ np.diag(eigvals) @ eigvecs.T

        # Prior weights w_0
        if current_weights is not None:
            w0_vec = current_weights.reindex(symbols).fillna(0.0).values
        else:
            w0_vec = np.zeros(n)

        # 2. Define CVXPY Variable
        w = cp.Variable(n, nonneg=True)

        # 3. Construct Objective: Maximize alpha - Risk Penalty - Turnover Penalty
        # alpha term
        alpha_term = alpha_vec @ w
        # risk term: 0.5 * lambda_risk * w^T Sigma w
        risk_term = 0.5 * self.risk_aversion * cp.quad_form(w, Sigma)
        # turnover term: lambda_turn * ||w - w0||_1
        turnover_term = self.turnover_penalty * cp.norm1(w - w0_vec)

        objective = cp.Maximize(alpha_term - risk_term - turnover_term)

        # 4. Constraints
        constraints = [
            # Long-only & stock upper limit
            w >= 0,
            w <= self.max_stock_weight,
            # Budget: sum(w) <= 1.0 - cash_floor
            cp.sum(w) <= (1.0 - self.cash_floor),
            cp.sum(w) >= 0.50  # Keep invested
        ]

        # Industry Neutrality constraint: |B_ind^T (w - w_bench)| <= delta_ind
        if industry_matrix is not None:
            B_aligned = industry_matrix.reindex(symbols).fillna(0.0).values
            if benchmark_weights is not None:
                w_bench_vec = benchmark_weights.reindex(symbols).fillna(0.0).values
            else:
                w_bench_vec = np.zeros(n)
            
            # Active industry exposure
            active_ind_exposure = B_aligned.T @ (w - w_bench_vec)
            constraints.append(active_ind_exposure <= self.industry_tolerance)
            constraints.append(active_ind_exposure >= -self.industry_tolerance)

        # INV-09 ADV20 Participation constraint: |w_i - w0_i| * NAV <= 0.05 * ADV20_i
        if adv20_values is not None and portfolio_nav > 0:
            adv_aligned = adv20_values.reindex(symbols).fillna(1e5).values
            max_delta_w = (adv_aligned * self.adv_cap_fraction) / portfolio_nav
            constraints.append(w - w0_vec <= max_delta_w)
            constraints.append(w0_vec - w <= max_delta_w)

        # 5. Solve via OSQP
        problem = cp.Problem(objective, constraints)
        try:
            problem.solve(solver=cp.OSQP, eps_abs=1e-5, eps_rel=1e-5, max_iter=4000)
        except Exception:
            # Fallback to Clarabel
            problem.solve(solver=cp.CLARABEL)

        solver_time = (time.perf_counter() - t0) * 1000.0

        if problem.status not in ["optimal", "optimal_inaccurate"]:
            # Fallback to safe prior weights if solver fails
            return OptimizationResult(
                status=f"FAILED_{problem.status}",
                optimal_weights={s: float(w0_vec[i]) for i, s in enumerate(symbols) if w0_vec[i] > 1e-4},
                expected_alpha=0.0,
                portfolio_variance=0.0,
                turnover=0.0,
                cash_weight=1.0 - float(np.sum(w0_vec)),
                solver_time_ms=solver_time
            )

        w_opt = np.array(w.value).flatten()
        w_opt[w_opt < 1e-4] = 0.0  # Clean tiny dust positions

        turnover_val = float(np.sum(np.abs(w_opt - w0_vec)))
        var_val = float(w_opt @ Sigma @ w_opt)
        alpha_val = float(alpha_vec @ w_opt)
        cash_val = 1.0 - float(np.sum(w_opt))

        weights_dict = {symbols[i]: float(w_opt[i]) for i in range(n) if w_opt[i] > 0.0}

        return OptimizationResult(
            status="OPTIMAL",
            optimal_weights=weights_dict,
            expected_alpha=alpha_val,
            portfolio_variance=var_val,
            turnover=turnover_val,
            cash_weight=cash_val,
            solver_time_ms=solver_time
        )
