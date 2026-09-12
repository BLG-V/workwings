"""Demo App 插件：展示 SDK register_tool / register_agent。

App 装卸落地后由装载器 import 本模块；当前可被 examples/sdk-min 直接调用。
"""

from __future__ import annotations

from mawp.runtime.spec import AgentSpec
from mawp.sdk import register_agent, register_tool
from mawp.tools.types import ToolDefinition


def _echo_version(policy, *, prefix: str = "mawp") -> dict:  # noqa: ANN001
    _ = policy
    from mawp import __version__

    return {"text": f"{prefix} {__version__}"}


def register(registry, runtime) -> None:  # noqa: ANN001
    """插件入口：把自定义 Tool + Agent 挂到当前进程。"""
    register_tool(
        ToolDefinition(
            name="demo_version",
            description="打印 demo App 侧的版本回显（无副作用）",
            parameters={
                "type": "object",
                "properties": {"prefix": {"type": "string"}},
            },
            handler=_echo_version,
            allowed_agents={"workflow", "requirement", "planner", "coding"},
        ),
        registry=registry,
    )
    register_agent(
        AgentSpec(
            name="demo_greeter",
            system_prompt='只输出 JSON：{"hello":"demo-code-agent"}',
            model="mock",
            tools=["echo", "demo_version"],
            max_steps=2,
            output_schema={
                "type": "object",
                "required": ["hello"],
                "properties": {"hello": {"type": "string"}},
            },
        ),
        runtime=runtime,
    )
