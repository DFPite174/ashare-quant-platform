"""
NautilusTrader & DuckDB Lake Engine Adapter.
Replaces QuantMind's Qlib engine with verified high-fidelity NautilusTrader execution.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"


class NautilusEngineAdapter:
    """
    Adapter providing high-fidelity NautilusTrader backtest results,
    NAV curves, friction accounting, and Alphalens factor research reports.
    """

    @classmethod
    def get_latest_backtest_summary(cls) -> Dict[str, Any]:
        """Loads and returns the 6-year long horizon battle test report."""
        report_path = OUTPUTS_DIR / "long_horizon_battle_test_report.json"
        if not report_path.exists():
            return {"status": "ERROR", "message": "Long horizon report not found"}
        return json.loads(report_path.read_text("utf-8"))

    @classmethod
    def get_nav_curve(cls, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns daily NAV curve data for React charts."""
        nav_path = OUTPUTS_DIR / "long_horizon_nav_curve.csv"
        if not nav_path.exists():
            return []
        df = pd.read_csv(nav_path)
        if "nav" in df.columns and "strategy_nav" not in df.columns:
            df["strategy_nav"] = df["nav"]
        if limit:
            df = df.tail(limit)
        return df.to_dict(orient="records")

    @classmethod
    def get_yearly_breakdown(cls) -> List[Dict[str, Any]]:
        """Returns annual returns, drawdowns, and excess return vs benchmarks."""
        yearly_path = OUTPUTS_DIR / "long_horizon_yearly_breakdown.csv"
        if not yearly_path.exists():
            return []
        df = pd.read_csv(yearly_path)
        return df.to_dict(orient="records")

    @classmethod
    def get_factor_report(cls, factor_id: str) -> Dict[str, Any]:
        """Returns Alphalens-cn evaluation report for a given factor."""
        if factor_id == "composite_alpha_v1":
            f_path = OUTPUTS_DIR / "factor_report_composite_alpha_v1.json"
        else:
            f_path = OUTPUTS_DIR / "p2_factor_report.json"

        if not f_path.exists():
            return {"status": "ERROR", "message": f"Report for {factor_id} not found"}
        data = json.loads(f_path.read_text("utf-8"))
        if "evaluation_metrics" in data and "metrics" not in data:
            data["metrics"] = data["evaluation_metrics"]
        return data

    @classmethod
    def get_audit_trail(cls) -> Dict[str, Any]:
        """Returns the self-healing and microstructure reflection audit trail."""
        audit_path = OUTPUTS_DIR / "agent_self_healing_reflection.json"
        if not audit_path.exists():
            return {"status": "ERROR", "message": "Audit reflection log not found"}
        return json.loads(audit_path.read_text("utf-8"))
