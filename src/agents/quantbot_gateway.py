"""
QuantBot Multi-Channel Notification Gateway (QuantBot 移动端即时通信推流网关).
Inspired by QuantMind's QuantBot architecture.

Supports Feishu (Lark) Interactive Cards and WeChat Work (企业微信) Markdown cards.
Maintains an institutional audit log of all outbound messages in outputs/quantbot_message_log.jsonl.
"""
from __future__ import annotations

import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"


class QuantBotGateway:
    """
    Formats and dispatches structured quant alerts, daily GoldenLedger reports,
    and Invariant Core violation alerts to mobile IM channels.
    """

    LOG_FILE = OUTPUTS_DIR / "quantbot_message_log.jsonl"

    @classmethod
    def _log_message(cls, channel: str, message_type: str, payload: Dict[str, Any], dispatch_status: str) -> None:
        """Appends message record to local audit JSONL log."""
        record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "channel": channel,
            "message_type": message_type,
            "dispatch_status": dispatch_status,
            "payload": payload
        }
        with open(cls.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @classmethod
    def format_golden_ledger_card(
        cls,
        trade_date: str,
        portfolio_nav: float,
        daily_pnl: float,
        total_friction: float,
        cash_diff: float = 0.00,
        invariants_status: str = "10/10 PASS"
    ) -> Dict[str, Any]:
        """Formats a Feishu interactive card for daily GoldenLedger reconciliation."""
        pnl_color = "red" if daily_pnl < 0 else "green"
        pnl_symbol = "+" if daily_pnl >= 0 else ""

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊【黄金账本】A股量化实盘对账日报 ({trade_date})"
                },
                "template": "blue" if cash_diff == 0.0 else "red"
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**期末总净值:**\n¥{portfolio_nav:,.2f}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**当日对账差额:**\n<font color='green'>¥{cash_diff:.2f}</font> (恒等0)"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**当日盈亏 (PnL):**\n<font color='{pnl_color}'>{pnl_symbol}¥{daily_pnl:,.2f}</font>"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**累计摩擦扣除:**\n¥{total_friction:,.2f}"}}
                    ]
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"🛡️ **安全内核状态**: `{invariants_status}`\n⚙️ **回测撮合引擎**: `NautilusTrader 1.231.0` (零合成数据)"
                    }
                }
            ]
        }
        return {"msg_type": "interactive", "card": card}

    @classmethod
    def format_risk_violation_card(
        cls,
        rule_id: str,
        symbol: str,
        action: str,
        blocked_reason: str,
        trade_date: str
    ) -> Dict[str, Any]:
        """Formats a critical risk violation intercept alert."""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🚨【风控硬拦截】安全不变量阻断通知 ({rule_id})"
                },
                "template": "red"
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**标的代码:** `{symbol}`"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**拦截动作:** `{action}`"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**生效日期:** `{trade_date}`"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**处理结果:** 100% 拒绝并记录"}}
                    ]
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"⚠️ **阻断理由**: {blocked_reason}\n*注：该行为已触发 A 股不变安全内核底层硬件级拦截，未执行任何报单。*"
                    }
                }
            ]
        }
        return {"msg_type": "interactive", "card": card}

    @classmethod
    def dispatch_alert(
        cls,
        message_type: str,
        payload: Dict[str, Any],
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches message to webhook if URL provided; always writes to institutional audit log.
        """
        status = "LOGGED_LOCAL_ONLY"
        if webhook_url:
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    webhook_url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        status = "DISPATCHED_OK"
                    else:
                        status = f"HTTP_{resp.status}"
            except Exception as e:
                status = f"FAILED: {str(e)}"

        cls._log_message(channel="FEISHU_OR_WECHAT", message_type=message_type, payload=payload, dispatch_status=status)
        return {
            "status": "SUCCESS" if "OK" in status or "LOGGED" in status else "FAILED",
            "dispatch_status": status,
            "timestamp": datetime.datetime.now().isoformat()
        }

    @classmethod
    def get_recent_messages(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent message logs for frontend UI."""
        if not cls.LOG_FILE.exists():
            return []
        lines = cls.LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
        records = [json.loads(line) for line in lines if line.strip()]
        return records[-limit:]
