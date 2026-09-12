from __future__ import annotations

from mawp.config.loader import load_config
from mawp.runtime.agent_runtime import AgentRuntime
from mawp.runtime.spec import AgentSpec
from mawp.sdk import register_agent, register_tool
from mawp.tools.registry import ToolRegistry
from mawp.tools.types import ToolDefinition


def test_register_tool_and_agent(tmp_path) -> None:
    config = load_config("mawp.config.yaml.example")
    config.workspace = str(tmp_path)
    registry = ToolRegistry(config)
    runtime = AgentRuntime(config, registry=registry)

    def _ping(policy, *, msg: str = "pong") -> dict:  # noqa: ANN001
        _ = policy
        return {"msg": msg}

    register_tool(
        ToolDefinition(
            name="ping",
            description="ping",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
            },
            handler=_ping,
            allowed_agents={"workflow"},
        ),
        registry=registry,
    )
    register_agent(
        AgentSpec(name="pinger", system_prompt="ping", tools=["ping"]),
        runtime=runtime,
    )

    assert registry.get("ping") is not None
    assert runtime.get("pinger") is not None
