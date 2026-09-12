"""MAWP runtime: AgentSpec/AgentRuntime (B) + Hybrid DeepSeek 八 Agent + Testing/Ship (C)."""

from mawp.runtime.agent_runtime import AgentRunResult, AgentRuntime, RuntimeContext
from mawp.runtime.deliver_specs import DELIVER_AGENTS, build_deliver_specs
from mawp.runtime.hybrid import AgentRuntimeAsRunner, HybridAgentRunner
from mawp.runtime.spec import AgentSpec

__all__ = [
    "AgentRunResult",
    "AgentRuntime",
    "RuntimeContext",
    "AgentSpec",
    "HybridAgentRunner",
    "AgentRuntimeAsRunner",
    "DELIVER_AGENTS",
    "build_deliver_specs",
]
