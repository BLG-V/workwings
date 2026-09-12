from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentSpec:
    """工作流可引用的通用 Agent 定义（配置驱动）。"""

    name: str
    system_prompt: str
    model: str = "mock"
    tools: list[str] = field(default_factory=list)
    max_steps: int = 8
    output_schema: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "tools": list(self.tools),
            "max_steps": self.max_steps,
            "output_schema": self.output_schema,
        }
