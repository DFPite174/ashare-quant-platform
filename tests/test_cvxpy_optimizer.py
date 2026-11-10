"""
Unit Tests for Institutional CVXPY Portfolio Optimizer (P-QM 3 Deliverable).
"""
import numpy as np
import pandas as pd
import pytest
from src.strategy.cvxpy_optimizer import (
    InstitutionalPortfolioOptimizer,
    OptimizationResult
)


@pytest.fixture
def mock_quant_universe():
    symbols = [f"00000{i}.SZ" for i in range(1, 21)]  # 20 stocks
    np.random.seed(42)
    # Alpha scores
    alpha = pd.Series(np.random.normal(0.05, 0.02, 20), index=symbols)
    # Covariance matrix (diagonal + small positive correlation)
    diag = np.random.uniform(0.01, 0.04, 20)
    cov = pd.DataFrame(np.diag(diag) + 0.005, index=symbols, columns=symbols)
    # Industry matrix (2 industries: Tech and Consumer)
    ind = pd.DataFrame(0, index=symbols, columns=["Tech", "Consumer"])
    for i, s in enumerate(symbols):
        if i < 10:
            ind.loc[s, "Tech"] = 1
        else:
            ind.loc[s, "Consumer"] = 1
    # ADV20
    adv20 = pd.Series(np.random.uniform(1e7, 5e7, 20), index=symbols)
    return symbols, alpha, cov, ind, adv20


def test_optimizer_basic_constraints(mock_quant_universe):
    symbols, alpha, cov, ind, adv20 = mock_quant_universe
    optimizer = InstitutionalPortfolioOptimizer(
        max_stock_weight=0.08,
        cash_floor=0.05,
        turnover_penalty=0.001
    )
    res = optimizer.optimize(
        alpha_scores=alpha,
        cov_matrix=cov,
        adv20_values=adv20,
        portfolio_nav=10_000_000.0
    )
    assert res.status == "OPTIMAL"
    assert res.cash_weight >= 0.049  # Cash floor respected
    # Check max stock weight constraint
    for sym, w in res.optimal_weights.items():
        assert w <= 0.0801, f"{sym} weight {w} exceeded 8%"
        assert w >= 0.0


def test_optimizer_turnover_penalty_compression(mock_quant_universe):
    symbols, alpha, cov, ind, adv20 = mock_quant_universe
    # Current portfolio: 10 stocks equal weight (10% each)
    w0 = pd.Series(0.0, index=symbols)
    for s in symbols[:10]:
        w0[s] = 0.095

    # Run 1: Zero turnover penalty
    opt_zero_penalty = InstitutionalPortfolioOptimizer(turnover_penalty=0.0)
    res_zero = opt_zero_penalty.optimize(
        alpha_scores=alpha,
        cov_matrix=cov,
        current_weights=w0
    )

    # Run 2: High turnover penalty
    opt_high_penalty = InstitutionalPortfolioOptimizer(turnover_penalty=0.05)
    res_high = opt_high_penalty.optimize(
        alpha_scores=alpha,
        cov_matrix=cov,
        current_weights=w0
    )

    # High penalty must strictly compress turnover!
    assert res_high.turnover < res_zero.turnover
    print(f"\nTurnover compressed from {res_zero.turnover:.4f} down to {res_high.turnover:.4f}")


def test_optimizer_industry_neutrality(mock_quant_universe):
    symbols, alpha, cov, ind, adv20 = mock_quant_universe
    # Benchmark is 50% Tech, 50% Consumer
    w_bench = pd.Series(0.0475, index=symbols)  # sum = 0.95

    optimizer = InstitutionalPortfolioOptimizer(
        industry_tolerance=0.02,  # +/- 2% max deviation
        turnover_penalty=0.001
    )
    res = optimizer.optimize(
        alpha_scores=alpha,
        cov_matrix=cov,
        industry_matrix=ind,
        benchmark_weights=w_bench
    )
    assert res.status == "OPTIMAL"
    w_series = pd.Series(res.optimal_weights).reindex(symbols).fillna(0.0)

    # Verify active industry exposure
    tech_exp = (ind["Tech"] * w_series).sum() - (ind["Tech"] * w_bench).sum()
    consumer_exp = (ind["Consumer"] * w_series).sum() - (ind["Consumer"] * w_bench).sum()

    assert abs(tech_exp) <= 0.0201
    assert abs(consumer_exp) <= 0.0201
