"""
Unit Tests for Quarterly Macro Meta-Reflector & QuantBot Gateway (P-QM 4 Deliverables).
"""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.agents.meta_reflector import QuarterlyMacroMetaReflector, MetaReflectionProposal
from src.agents.quantbot_gateway import QuantBotGateway
from backend.app import app

client = TestClient(app)


def test_quarterly_macro_meta_reflector():
    reflector = QuarterlyMacroMetaReflector()
    proposal = reflector.run_quarterly_reflection()

    assert isinstance(proposal, MetaReflectionProposal)
    assert proposal.analyzed_quarters >= 24  # 6 years * 4 quarters
    assert "BEAR_DRAWDOWN" in proposal.dominant_regimes
    assert proposal.recommended_cash_floor >= 0.05
    assert proposal.recommended_turnover_penalty >= 0.003
    assert len(proposal.quarterly_breakdown) >= 24

    # Verify output JSON exists
    out_file = root_dir / "outputs" / "quarterly_meta_reflection_report.json"
    assert out_file.exists()


def test_quantbot_card_formatting_and_logging():
    # 1. Format GoldenLedger Card
    card_obj = QuantBotGateway.format_golden_ledger_card(
        trade_date="2024-12-31",
        portfolio_nav=3889522.04,
        daily_pnl=-5200.0,
        total_friction=2050275.26,
        cash_diff=0.00
    )
    assert card_obj["msg_type"] == "interactive"
    assert "黄金账本" in card_obj["card"]["header"]["title"]["content"]
    assert card_obj["card"]["header"]["template"] == "blue"  # 0 diff = blue template

    # 2. Format Risk Violation Card
    risk_card = QuantBotGateway.format_risk_violation_card(
        rule_id="INV-02",
        symbol="600519.SH",
        action="BUY",
        blocked_reason="Stock locked at limit-up, unexecutable.",
        trade_date="2024-05-10"
    )
    assert "INV-02" in risk_card["card"]["header"]["title"]["content"]
    assert risk_card["card"]["header"]["template"] == "red"

    # 3. Dispatch alert and verify local audit logging
    res = QuantBotGateway.dispatch_alert(
        message_type="TEST_GOLDEN_LEDGER",
        payload=card_obj
    )
    assert res["status"] == "SUCCESS"
    assert res["dispatch_status"] == "LOGGED_LOCAL_ONLY"

    # 4. Check that message appears in get_recent_messages
    recent = QuantBotGateway.get_recent_messages(limit=5)
    assert len(recent) > 0
    assert recent[-1]["message_type"] == "TEST_GOLDEN_LEDGER"


def test_api_meta_reflector_endpoints():
    response = client.post("/api/v1/meta-reflector/run")
    assert response.status_code == 200
    data = response.json()
    assert data["analyzed_quarters"] >= 24
    assert "recommended_cash_floor" in data

    resp_latest = client.get("/api/v1/meta-reflector/latest")
    assert resp_latest.status_code == 200
    assert resp_latest.json()["analyzed_quarters"] >= 24


def test_api_quantbot_endpoints():
    post_data = {
        "message_type": "DAILY_LEDGER_ALERT",
        "trade_date": "2024-12-31",
        "portfolio_nav": 3889522.04,
        "daily_pnl": 12000.0,
        "cash_diff": 0.00,
        "total_friction": 2050275.26
    }
    resp = client.post("/api/v1/quantbot/send-alert", json=post_data)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"

    logs_resp = client.get("/api/v1/quantbot/logs?limit=10")
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert len(logs) > 0
    assert logs[-1]["message_type"] == "DAILY_LEDGER_ALERT"
