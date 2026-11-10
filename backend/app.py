"""
Quant Platform High-Fidelity FastAPI Gateway.
Provides REST and WebSocket endpoints for React/Electron UI and QuantBot IM integrations.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure platform root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.engine.nautilus_adapter import NautilusEngineAdapter
from src.core.invariant_core import AShareInvariantSafetyCore
from src.agents.meta_reflector import QuarterlyMacroMetaReflector
from src.agents.quantbot_gateway import QuantBotGateway

app = FastAPI(
    title="A-Share Institutional Quant Platform API (QuantMind + quant-agent Unified)",
    version="2.0.0",
    description="High-fidelity quantitative trading API backed by NautilusTrader and Tushare Parquet Lake."
)

# Enable CORS for React/Electron UI (:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def get_health() -> Dict[str, Any]:
    """Returns platform health, invariant safety core status, and lake configuration."""
    return {
        "status": "UP",
        "engine": "NautilusTrader 1.231.0 (Qlib replaced)",
        "invariants_enforced": [
            "INV-01 (T+1 Settlement)",
            "INV-02 (Limit-Up Buy Prohibition)",
            "INV-03 (Limit-Down Sell Prohibition)",
            "INV-04 (Suspension Lock & Deferred Delta)",
            "INV-05 (Statutory Stamp Duty Post-2023 Reduction)",
            "INV-06 (Broker Commission 5 CNY Floor)",
            "INV-07 (ChinaClear Transfer Fee)",
            "INV-08 (Execution Slippage Floor)",
            "INV-09 (ADV20 5% Liquidity Cap)",
            "INV-10 (Golden Ledger Decimal Identity)"
        ],
        "data_lake": {
            "source": "Tushare Pro Paid Lake",
            "path": "C:/Users/SKT80/Downloads/MyProj/my_upload/Tushare_DB/lake",
            "historical_range": "2005-2026 (16.2M bars)",
            "zero_synthetic_data": True
        }
    }


@app.get("/api/v1/backtest/summary")
def get_backtest_summary() -> Dict[str, Any]:
    """Returns 6-year long horizon battle test metrics and attribution."""
    summary = NautilusEngineAdapter.get_latest_backtest_summary()
    if summary.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=summary.get("message"))
    return summary


@app.get("/api/v1/backtest/nav-curve")
def get_nav_curve(limit: Optional[int] = Query(None, description="Limit recent days")) -> List[Dict[str, Any]]:
    """Returns daily mark-to-market NAV curve for chart rendering."""
    return NautilusEngineAdapter.get_nav_curve(limit=limit)


@app.get("/api/v1/backtest/yearly")
def get_yearly_breakdown() -> List[Dict[str, Any]]:
    """Returns annual returns, drawdowns, and excess return vs CSI 500."""
    return NautilusEngineAdapter.get_yearly_breakdown()


@app.get("/api/v1/factors/evaluate")
def evaluate_factor(factor_id: str = Query("composite_alpha_v1", description="Factor ID")) -> Dict[str, Any]:
    """Returns factor evaluation metrics with Newey-West HAC statistics."""
    report = NautilusEngineAdapter.get_factor_report(factor_id)
    if report.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=report.get("message"))
    return report


@app.get("/api/v1/agent/audit-trail")
def get_agent_audit_trail() -> Dict[str, Any]:
    """Returns the agent self-healing and microstructure reflection audit trail."""
    trail = NautilusEngineAdapter.get_audit_trail()
    if trail.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=trail.get("message"))
    return trail


# =====================================================================
# P-QM 4: Meta-Reflector & QuantBot Notification Endpoints
# =====================================================================
class QuantBotSendRequest(BaseModel):
    message_type: str = Field(default="GOLDEN_LEDGER_ALERT", description="Message type")
    trade_date: str = Field(default="2024-12-31", description="Trade date")
    portfolio_nav: float = Field(default=3889522.04, description="Portfolio NAV")
    daily_pnl: float = Field(default=0.0, description="Daily PnL")
    cash_diff: float = Field(default=0.00, description="Golden Ledger Cash Diff")
    total_friction: float = Field(default=2050275.26, description="Total Friction Paid")
    webhook_url: Optional[str] = Field(default=None, description="Optional Feishu/WeChat Webhook URL")


@app.post("/api/v1/meta-reflector/run")
def run_meta_reflector() -> Dict[str, Any]:
    """Triggers quarterly macro meta-reflection audit and adaptive parameter proposals."""
    import dataclasses
    reflector = QuarterlyMacroMetaReflector()
    proposal = reflector.run_quarterly_reflection()
    return dataclasses.asdict(proposal)


@app.get("/api/v1/meta-reflector/latest")
def get_latest_meta_reflection() -> Dict[str, Any]:
    """Retrieves the latest quarterly meta-reflection proposal."""
    report_file = root_dir / "outputs" / "quarterly_meta_reflection_report.json"
    if not report_file.exists():
        # Auto-run if not yet generated
        return run_meta_reflector()
    import json
    return json.loads(report_file.read_text(encoding="utf-8"))


@app.post("/api/v1/quantbot/send-alert")
def send_quantbot_alert(req: QuantBotSendRequest) -> Dict[str, Any]:
    """Formats and dispatches a structured QuantBot message card to mobile IM."""
    payload = QuantBotGateway.format_golden_ledger_card(
        trade_date=req.trade_date,
        portfolio_nav=req.portfolio_nav,
        daily_pnl=req.daily_pnl,
        total_friction=req.total_friction,
        cash_diff=req.cash_diff
    )
    return QuantBotGateway.dispatch_alert(
        message_type=req.message_type,
        payload=payload,
        webhook_url=req.webhook_url
    )


@app.get("/api/v1/quantbot/logs")
def get_quantbot_logs(limit: int = Query(50, description="Number of logs")) -> List[Dict[str, Any]]:
    """Returns outbound mobile IM dispatch audit logs."""
    return QuantBotGateway.get_recent_messages(limit=limit)

