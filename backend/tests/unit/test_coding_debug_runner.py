# -*- coding: utf-8 -*-
"""B · Coding / Debug runner + 八 Agent 工具白名单。"""
from __future__ import annotations

from pathlib import Path

import pytest

from mawp.config.loader import AgentConfig, load_config
from mawp.core.engine import WorkflowEngine
from mawp.core.loader import load_workflow
from mawp.runtime.agents import AgentRunContext, MockAgentRunner
from mawp.runtime.hybrid import HybridAgentRunner
from mawp.security.policy import PolicyDenied, PolicyEngine
from mawp.tools.registry import AGENT_TOOL_WHITELIST, ToolRegistry
from mawp.tools.types import ToolCallContext


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> AgentConfig:
    cfg = load_config().model_copy(update={"workspace": str(workspace)})
    # 单测离线：强制 mock，避免本机 DEEPSEEK_API_KEY 触发真 LLM
    cfg.llm = cfg.llm.model_copy(update={"provider": "mock"})
    return cfg


def test_whitelist_includes_eight_agents() -> None:
    for name in (
        "planner",
        "requirement",
        "coding",
        "frontend",
        "testing",
        "debug",
        "review",
        "ship",
    ):
        assert name in AGENT_TOOL_WHITELIST


def test_debug_and_frontend_can_write_allowed_paths(config: AgentConfig) -> None:
    registry = ToolRegistry(config)
    # debug 可写 src
    r1 = registry.execute(
        "write_file",
        {"path": "src/fix_note.py", "content": "# fixed\n"},
        ToolCallContext(agent_name="debug", session_id="s1"),
    )
    assert r1.success, r1.error
    assert (Path(config.workspace) / "src" / "fix_note.py").exists()

    # frontend 可写 frontend/
    r2 = registry.execute(
        "write_file",
        {"path": "frontend/index.html", "content": "<html></html>\n"},
        ToolCallContext(agent_name="frontend", session_id="s1"),
    )
    assert r2.success, r2.error

    # review 不可写
    r3 = registry.execute(
        "write_file",
        {"path": "src/hack.py", "content": "nope\n"},
        ToolCallContext(agent_name="review", session_id="s1"),
    )
    assert not r3.success


def test_frontend_write_outside_frontend_denied(config: AgentConfig) -> None:
    policy = PolicyEngine(config)
    with pytest.raises(PolicyDenied) as exc:
        policy.check_write("src/secret.py", "frontend")
    assert exc.value.code in {"AGENT_NO_WRITE", "PATH_OUT_OF_SCOPE", "FRONTEND_PATH_DENIED"}


def test_hybrid_coding_writes_and_stable_outputs(config: AgentConfig) -> None:
    runner = HybridAgentRunner(config)
    ctx = AgentRunContext(
        run_id="r1",
        params={"goal": "add hello"},
        nodes_outputs={
            "planner": {
                "tasks": [{"id": "T1", "title": "hello", "depends_on": []}],
                "status": "ok",
                "count": 1,
            }
        },
        node_id="coding",
    )
    result = runner.run("coding", {}, ctx)
    assert result.success
    out = result.output
    assert out["status"] == "ok"
    assert "changed_files" in out
    assert "tasks_done" in out
    assert "T1" in out["tasks_done"]
    # 应经 ToolRegistry 落盘
    assert any(
        (Path(config.workspace) / p).exists()
        for p in out["changed_files"]
    )


def test_hybrid_debug_uses_testing_failures_and_tools(config: AgentConfig) -> None:
    runner = HybridAgentRunner(config)
    ctx = AgentRunContext(
        run_id="r2",
        params={},
        nodes_outputs={
            "testing": {
                "passed": False,
                "status": "fail",
                "failures": ["assert False"],
                "log_summary": "failed",
                "attempt": 1,
            }
        },
        node_id="debug",
    )
    result = runner.run("debug", {"note": "fix assert"}, ctx)
    assert result.success
    out = result.output
    assert out["status"] == "ok"
    assert out["fixed"] is True
    assert out["based_on_failures"] == ["assert False"]
    assert (Path(config.workspace) / "src" / ".mawp_debug_fix").exists() or any(
        Path(config.workspace).joinpath("src").glob("*debug*")
    )


def test_hybrid_delegates_other_agents_to_mock(config: AgentConfig) -> None:
    runner = HybridAgentRunner(config, fallback=MockAgentRunner())
    ctx = AgentRunContext(run_id="r3", params={"goal": "g"}, nodes_outputs={}, node_id="planner")
    result = runner.run("planner", {}, ctx)
    assert result.success
    assert "tasks" in result.output


def test_engine_default_uses_hybrid_coding_debug(config: AgentConfig) -> None:
    """引擎默认 Hybrid：Coding/Debug 走 B 实现，deliver 契约仍绿。"""
    engine = WorkflowEngine(config)
    assert isinstance(engine.agent_runner, HybridAgentRunner)

    deliver = Path("examples/deliver/workflow.yaml")
    if not deliver.exists():
        pytest.skip("examples/deliver missing")
    run = engine.run(deliver)
    assert run.status == "DONE"
    assert "changed_files" in run.node_outputs["coding"]
    assert run.node_outputs["ship"]["auto_push"] is False


def test_coding_debug_retest_loop_with_hybrid(config: AgentConfig) -> None:
    engine = WorkflowEngine(config)
    deliver = Path("examples/deliver/workflow.yaml")
    if not deliver.exists():
        pytest.skip("examples/deliver missing")
    run = engine.run(deliver, params_override={"pass_on_attempt": 2})
    assert run.status == "DONE"
    assert run.node_outputs["testing"]["attempt"] == 2
    assert "debug" in run.node_outputs
    assert run.node_outputs["debug"]["fixed"] is True
