from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AgentContext:
    session_id: str
    user_description: str
    workspace: Path
    actor_id: str = "local"
    rag_chunks: list[dict[str, Any]] = field(default_factory=list)
    memory_summary: str = ""
    prior_messages: list[dict[str, Any]] = field(default_factory=list)
    prior_requirement_spec: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    tokens_used: int = 0
    error: str | None = None
    agent_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "tokens_used": self.tokens_used,
            "error": self.error,
            "agent_type": self.agent_type,
        }
