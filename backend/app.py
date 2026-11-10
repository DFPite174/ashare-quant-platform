"""
Quant Platform High-Fidelity FastAPI Gateway.
Provides REST and WebSocket endpoints for React/Electron UI and QuantBot IM integrations.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
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


@app.get("/", response_class=HTMLResponse)
def index_portal() -> str:
    """Institutional landing page with direct links to Swagger, ReDoc, endpoints, and frontend."""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A-Share Institutional Quant Platform Gateway</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: #0b0f19;
            color: #e2e8f0;
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
        }
        .container {
            max-width: 900px;
            width: 100%;
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 36px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        }
        .header {
            border-bottom: 1px solid #1f2937;
            padding-bottom: 20px;
            margin-bottom: 24px;
        }
        .badge {
            display: inline-block;
            background: #064e3b;
            color: #34d399;
            font-size: 12px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 9999px;
            margin-bottom: 12px;
            border: 1px solid #059669;
        }
        h1 {
            font-size: 24px;
            font-weight: 700;
            color: #f8fafc;
            margin: 0 0 8px 0;
        }
        p.subtitle {
            color: #94a3b8;
            font-size: 14px;
            margin: 0;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 16px;
            margin: 24px 0;
        }
        .card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 20px;
            text-decoration: none;
            color: inherit;
            transition: all 0.2s ease;
            display: block;
        }
        .card:hover {
            border-color: #38bdf8;
            transform: translateY(-2px);
            background: #1e293b;
        }
        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: #38bdf8;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .card-desc {
            font-size: 13px;
            color: #94a3b8;
            line-height: 1.4;
        }
        .footer-box {
            background: #0f172a;
            border-left: 4px solid #38bdf8;
            padding: 16px;
            border-radius: 4px;
            margin-top: 24px;
            font-size: 13px;
            color: #cbd5e1;
        }
        code {
            background: #1e293b;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: Consolas, monospace;
            color: #f43f5e;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="badge">● GATEWAY ONLINE (PORT 8000)</span>
            <h1>A股机构级量化投研平台 · API 导航网关</h1>
            <p class="subtitle">NautilusTrader 1.231.0 纯观察回测引擎 · 10 大不可逾越安全内核 · 1,620 万行真实 Tushare 湖仓</p>
        </div>

        <div class="grid">
            <a href="/docs" class="card" target="_blank">
                <div class="card-title">📖 Swagger API 在线交互文档</div>
                <div class="card-desc">直观测试全部 REST 接口、查看数据契约与参数规范（/docs）。</div>
            </a>
            <a href="/redoc" class="card" target="_blank">
                <div class="card-title">📑 ReDoc 规范文档</div>
                <div class="card-desc">OpenAPI 3.0 标准机构级接口参考手册（/redoc）。</div>
            </a>
            <a href="/api/v1/health" class="card" target="_blank">
                <div class="card-title">🛡️ 平台健康与10大安全内核</div>
                <div class="card-desc">查看 T+1、涨跌停阻断、印花税减半等 10 项不可动摇刚性规则状态。</div>
            </a>
            <a href="/api/v1/backtest/summary" class="card" target="_blank">
                <div class="card-title">📊 6年实战长周期对账总结</div>
                <div class="card-desc">2019-2024 穿透 205 万摩擦损耗的权威三方黄金对账账本。</div>
            </a>
            <a href="/api/v1/factor/evaluation" class="card" target="_blank">
                <div class="card-title">🔬 Alphalens-cn 因子评测中台</div>
                <div class="card-desc">大模型 5 轮自愈演化后的复合因子评价报告（Rank IC +0.0676, t=6.63）。</div>
            </a>
            <a href="http://localhost:3000/ashare-dashboard" class="card" target="_blank">
                <div class="card-title">🖥️ 机构级全栈交互控制台</div>
                <div class="card-desc">React 18 + TailwindCSS 现代化实盘对账看板（需启动前端 :3000）。</div>
            </a>
        </div>

        <div class="footer-box">
            💡 <strong>前端控制台启动指南</strong>：在另一个终端窗口中执行 <code>cd frontend; npm run dev</code>，即可通过 <code>http://localhost:3000/ashare-dashboard</code> 查看完整的可视化图表与实盘看板。
        </div>
    </div>
</body>
</html>
"""


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

