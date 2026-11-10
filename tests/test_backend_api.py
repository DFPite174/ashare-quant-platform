"""
Tests for FastAPI Backend & Nautilus Adapter (P-QM 1 Deliverable).
"""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app import app

client = TestClient(app)

def test_api_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert "NautilusTrader" in data["engine"]
    assert len(data["invariants_enforced"]) == 10
    assert data["data_lake"]["zero_synthetic_data"] is True


def test_api_backtest_summary():
    response = client.get("/api/v1/backtest/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PASS"
    assert data["horizon"]["total_trading_days"] == 1456
    assert data["capital_and_friction"]["initial_cash"] == 10000000.0
    assert data["capital_and_friction"]["total_trading_friction"] > 2000000.0


def test_api_nav_curve():
    response = client.get("/api/v1/backtest/nav-curve?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10
    assert "date" in data[0]
    assert "strategy_nav" in data[0]
    assert "benchmark_500" in data[0]


def test_api_yearly_breakdown():
    response = client.get("/api/v1/backtest/yearly")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6  # 2019 to 2024
    years = [str(item["Year"]) for item in data]
    assert "2019" in years and "2024" in years


def test_api_factor_evaluation():
    # Evaluate composite_alpha_v1 (Admitted factor)
    response = client.get("/api/v1/factors/evaluate?factor_id=composite_alpha_v1")
    assert response.status_code == 200
    data = response.json()
    assert data["formal_gate"]["decision"] == "FACTOR_ADMITTED"
    assert data["metrics"]["5D"]["mean_ic"] > 0.05
    assert data["metrics"]["5D"]["hac_t_stat"] > 2.0


def test_api_agent_audit_trail():
    response = client.get("/api/v1/agent/audit-trail")
    assert response.status_code == 200
    data = response.json()
    assert "turn_1_initial_state_probe" in data
    assert "turn_2_microstructure_reflection" in data
    assert "turn_3_adaptive_hypothesis_formulation" in data
    assert data["turn_5_institutional_gate_verdict"]["gate_decision"] == "FACTOR_ADMITTED"
