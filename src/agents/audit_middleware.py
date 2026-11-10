"""自定义中间件示例：工具调用审计（AuditLogMiddleware）。

演示 DeerFlow 2.0 生产级扩展点之二 —— AgentMiddleware 切面：
通过 awrap_tool_call 包裹每一次工具执行，记录：

- 工具名、参数摘要（密钥类字段自动脱敏）
- 耗时（毫秒）、成功/失败与异常类型
- JSONL 追加写入 audit/tool-audit.jsonl（生产合规审计的最小实现）

异常处理契约：本中间件只记录、不改写、不吞异常 —— 原样抛出后由
DeerFlow 的 ToolErrorHandlingMiddleware 转成 error ToolMessage 回环自愈。
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.types import Command

if TYPE_CHECKING:
    from langgraph.prebuilt.tool_node import ToolCallRequest

# 参数脱敏：命中这些键的值一律替换为 ***（含嵌套 dict）
_SECRET_KEY_RE = re.compile(
    r"(?:api[_-]?key|token|secret|password|authorization|credential)",
    re.IGNORECASE,
)

_MAX_ARGS_CHARS = 800  # 参数摘要上限，防止审计日志本身膨胀
_RESULT_SIZES = {"task"}  # 子代理委派结果较长，只记长度不记内容


def _redact(value: object) -> object:
    """递归脱敏 dict / list 中命中密钥模式的字段值。"""
    if isinstance(value, dict):
        return {
            k: ("***" if _SECRET_KEY_RE.search(str(k)) else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str) and _SECRET_KEY_RE.search(value):
        return "***"
    return value


def _summarize_args(args: object) -> object:
    text = json.dumps(_redact(args), ensure_ascii=False, default=str)
    if len(text) > _MAX_ARGS_CHARS:
        return {"_truncated": text[:_MAX_ARGS_CHARS]}
    return json.loads(text)


class AuditLogMiddleware(AgentMiddleware[AgentState]):
    """把每次工具调用以 JSONL 记录到磁盘；控制台同步打印一行摘要。"""

    def __init__(self, log_dir: str | Path = "audit") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "tool-audit.jsonl"

    # ---------------- 异步路径（生产运行走这里） ---------------- #

    async def awrap_tool_call(
        self,
        request: "ToolCallRequest",
        handler: Callable[["ToolCallRequest"], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        tool_call = request.tool_call
        name = tool_call.get("name", "<unknown>")
        args = tool_call.get("args", {}) or {}
        started = time.perf_counter()
        record: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tool": name,
            "args": _summarize_args(args),
        }
        try:
            result = await handler(request)
        except Exception as exc:
            record.update(
                status="failed",
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            self._emit(record)
            raise  # 只记录不吞异常：交给 ToolErrorHandlingMiddleware 兜底回环
        record.update(
            status="ok",
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        if isinstance(result, ToolMessage):
            record["result_chars"] = len(str(result.content))
        else:
            record["result_type"] = type(result).__name__
        self._emit(record)
        return result

    # ---------------- 同步路径（保持对齐，防止降级运行丢审计） ---------------- #

    def wrap_tool_call(
        self,
        request: "ToolCallRequest",
        handler: Callable[["ToolCallRequest"], ToolMessage | Command],
    ) -> ToolMessage | Command:
        tool_call = request.tool_call
        name = tool_call.get("name", "<unknown>")
        args = tool_call.get("args", {}) or {}
        started = time.perf_counter()
        record: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tool": name,
            "args": _summarize_args(args),
        }
        try:
            result = handler(request)
        except Exception as exc:
            record.update(
                status="failed",
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            self._emit(record)
            raise
        record.update(
            status="ok",
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        if isinstance(result, ToolMessage):
            record["result_chars"] = len(str(result.content))
        else:
            record["result_type"] = type(result).__name__
        self._emit(record)
        return result

    # ---------------- 落盘 ---------------- #

    def _emit(self, record: dict[str, object]) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        status = record.get("status", "?")
        duration = record.get("duration_ms", 0)
        print(f"  [audit] {record.get('tool')} -> {status} ({duration} ms)", flush=True)
