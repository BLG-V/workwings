"""MAWP SDK: register_tool / register_agent public APIs (W4)."""

from mawp.runtime.spec import AgentSpec
from mawp.sdk.api import register_agent, register_tool
from mawp.tools.types import ToolDefinition

__all__ = ["register_tool", "register_agent", "AgentSpec", "ToolDefinition"]
