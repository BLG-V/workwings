"""MAWP SDK：register_tool / register_agent（W4 最小可用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mawp.runtime.spec import AgentSpec
from mawp.tools.types import ToolDefinition

if TYPE_CHECKING:
    from mawp.runtime.agent_runtime import AgentRuntime
    from mawp.tools.registry import ToolRegistry

__all__ = ["register_tool", "register_agent", "AgentSpec", "ToolDefinition"]


def register_tool(
    tool: ToolDefinition,
    *,
    registry: ToolRegistry,
) -> None:
    """向 ToolRegistry 注册自定义 Tool。"""
    registry.register(tool)


def register_agent(
    spec: AgentSpec,
    *,
    runtime: AgentRuntime,
) -> None:
    """向 AgentRuntime 注册自定义 AgentSpec。"""
    runtime.register(spec)
