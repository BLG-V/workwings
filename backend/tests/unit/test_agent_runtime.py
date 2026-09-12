from __future__ import annotations

from pathlib import Path

import pytest

from mawp.config.loader import AgentConfig
from mawp.llm.mock import MockLLMAdapter
from mawp.llm.types import LLMResponse, TokenUsage
from mawp.runtime.agent_runtime import AgentRuntime, RuntimeContext
from mawp.runtime.spec import AgentSpec
from mawp.tools.registry import ToolRegistry


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> AgentConfig:
    return AgentConfig(workspace=str(workspace), llm={"provider": "mock"})


def test_agent_runtime_text_only_with_mock(config: AgentConfig) -> None:
    llm = MockLLMAdapter(
        [
            LLMResponse(
                content="hello-from-agent",
                usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            )
        ]
    )
    runtime = AgentRuntime(config, llm=llm, registry=ToolRegistry(config))
    runtime.register(
        AgentSpec(
            name="requirement",
            system_prompt="You are a helper.",
            model="mock",
            tools=[],
            max_steps=3,
        )
    )

    result = runtime.run(
        "requirement",
        {"text": "say hi"},
        RuntimeContext(session_id="s1"),
    )

    assert result.success
    assert result.output.get("text") == "hello-from-agent"
    assert result.error is None
    assert result.tool_calls == []
    assert result.usage.get("total_tokens") == 2
    assert result.usage.get("prompt_tokens") == 1
    assert result.usage.get("completion_tokens") == 1


def test_agent_runtime_tool_calling_until_done(config: AgentConfig) -> None:
    llm = MockLLMAdapter(
        [
            MockLLMAdapter.tool_call_response(
                "call_1", "echo", {"text": "ping"}
            ),
            LLMResponse(
                content="done-after-echo",
                usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            ),
        ]
    )
    runtime = AgentRuntime(config, llm=llm, registry=ToolRegistry(config))
    runtime.register(
        AgentSpec(
            name="requirement",
            system_prompt="Use echo when needed.",
            model="mock",
            tools=["echo"],
            max_steps=5,
        )
    )

    result = runtime.run(
        "requirement",
        {"text": "ping please"},
        RuntimeContext(session_id="s2"),
    )

    assert result.success
    assert result.output.get("text") == "done-after-echo"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "echo"
    assert result.tool_calls[0]["success"] is True


def test_agent_runtime_respects_max_steps(config: AgentConfig) -> None:
    llm = MockLLMAdapter(
        [
            MockLLMAdapter.tool_call_response("c1", "echo", {"text": "a"}),
            MockLLMAdapter.tool_call_response("c2", "echo", {"text": "b"}),
            MockLLMAdapter.tool_call_response("c3", "echo", {"text": "c"}),
        ]
    )
    runtime = AgentRuntime(config, llm=llm, registry=ToolRegistry(config))
    runtime.register(
        AgentSpec(
            name="requirement",
            system_prompt="Keep calling tools.",
            model="mock",
            tools=["echo"],
            max_steps=2,
        )
    )

    result = runtime.run(
        "requirement",
        {"text": "loop"},
        RuntimeContext(session_id="s3"),
    )

    assert not result.success
    assert "max_steps" in (result.error or "")
    assert len(result.tool_calls) == 2


def test_agent_runtime_finalize_round_emits_json(config: AgentConfig) -> None:
    llm = MockLLMAdapter(
        [
            MockLLMAdapter.tool_call_response("c1", "echo", {"text": "a"}),
            MockLLMAdapter.tool_call_response("c2", "echo", {"text": "b"}),
            MockLLMAdapter.json_response({"status": "ok", "from": "finalize"}),
        ]
    )
    runtime = AgentRuntime(config, llm=llm, registry=ToolRegistry(config))
    runtime.register(
        AgentSpec(
            name="review",
            system_prompt="Keep calling tools.",
            model="mock",
            tools=["echo"],
            max_steps=2,
        )
    )
    result = runtime.run(
        "review",
        {"text": "loop"},
        RuntimeContext(session_id="s4"),
    )
    assert result.success
    assert result.output.get("from") == "finalize"
    assert len(result.tool_calls) == 2
    assert llm.calls[-1]["tools"] in (None, [])


def test_agent_runtime_maps_llm_error(config: AgentConfig) -> None:
    from mawp.llm.exceptions import LLMRequestError

    class Boom(MockLLMAdapter):
        max_retries = 1
        retry_base_delay = 0.0

        def chat(self, *a, **k):  # type: ignore[no-untyped-def]
            raise LLMRequestError(
                "OpenAI 请求失败: Server disconnected without sending a response."
            )

    runtime = AgentRuntime(config, llm=Boom([]), registry=ToolRegistry(config))
    runtime.register(
        AgentSpec(
            name="coding",
            system_prompt="x",
            model="mock",
            tools=[],
            max_steps=2,
        )
    )
    result = runtime.run(
        "coding",
        {"text": "go"},
        RuntimeContext(session_id="s5"),
    )
    assert not result.success
    assert "disconnected" in (result.error or "").lower()


def test_agent_runtime_honors_model_override(config: AgentConfig) -> None:
    llm = MockLLMAdapter(
        [
            MockLLMAdapter.json_response({"status": "ok"}),
        ]
    )
    runtime = AgentRuntime(config, llm=llm, registry=ToolRegistry(config))
    runtime.register(
        AgentSpec(
            name="coding",
            system_prompt="x",
            model="deepseek-v4-pro",
            tools=[],
            max_steps=2,
        )
    )
    result = runtime.run(
        "coding",
        {"text": "go"},
        RuntimeContext(session_id="s6"),
        model_override="deepseek-v4-flash",
    )
    assert result.success
    assert llm.calls[-1]["model"] == "deepseek-v4-flash"


def test_engine_can_run_agent_node_with_mock(config: AgentConfig, workspace: Path) -> None:
    from mawp.core.engine import WorkflowEngine
    from mawp.core.models import Workflow, WorkflowEdge, WorkflowNode

    llm = MockLLMAdapter(
        [
            LLMResponse(
                content="classified:ok",
                usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            )
        ]
    )
    runtime = AgentRuntime(config, llm=llm, registry=ToolRegistry(config))
    runtime.register(
        AgentSpec(
            name="requirement",
            system_prompt="Classify briefly.",
            model="mock",
            tools=[],
        )
    )
    engine = WorkflowEngine(config, agent_runtime=runtime)
    workflow = Workflow(
        id="agent-hello",
        name="agent hello",
        version="0.1.0",
        entry="start",
        params={},
        nodes=[
            WorkflowNode(id="start", type="start"),
            WorkflowNode(
                id="a1",
                type="agent",
                agent="requirement",
                input={"text": "hello"},
            ),
            WorkflowNode(id="end", type="end"),
        ],
        edges=[
            WorkflowEdge(from_id="start", to_id="a1"),
            WorkflowEdge(from_id="a1", to_id="end"),
        ],
        source_path=str(workspace / "wf.yaml"),
    )

    run = engine.run(workflow)
    assert run.status == "DONE"
    assert run.node_outputs["a1"]["text"] == "classified:ok"
    usage = run.node_outputs["a1"].get("_usage") or {}
    assert usage.get("total_tokens") == 2
    events = engine.store.read_events(run.run_id)
    assert any(e.get("type") == "agent_usage" and e.get("usage", {}).get("total_tokens") == 2 for e in events)
