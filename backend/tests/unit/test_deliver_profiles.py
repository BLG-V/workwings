"""增量短链 / 只验收工作流 / 不可修错误跳过 Debug。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mawp.config.loader import load_config
from mawp.core.engine import WorkflowEngine
from mawp.core.loader import load_workflow
from mawp.core.validate import validate_workflow
from mawp.runtime.agents import AgentRunContext
from mawp.runtime.deliver_profiles import select_deliver_workflow
from mawp.runtime.error_classifier import is_unfixable_debug_failure
from mawp.runtime.hybrid import HybridAgentRunner

INCREMENT = Path("apps/demo-code-agent/workflows/deliver-increment.yaml")
VERIFY = Path("apps/demo-code-agent/workflows/deliver-verify.yaml")


def test_p1_uses_full_deliver() -> None:
    path = select_deliver_workflow({"id": "p1", "depends_on": []})
    assert path.endswith("deliver.yaml")
    assert "increment" not in path
    assert "verify" not in path


def test_later_phase_uses_increment_chain() -> None:
    path = select_deliver_workflow(
        {"id": "p4", "depends_on": ["p2"], "title": "商城"}
    )
    assert path.endswith("deliver-increment.yaml")


def test_verify_only_uses_verify_chain() -> None:
    path = select_deliver_workflow({"id": "p1"}, verify_only=True)
    assert path.endswith("deliver-verify.yaml")


def test_increment_and_verify_yaml_validate() -> None:
    assert INCREMENT.is_file()
    assert VERIFY.is_file()
    assert validate_workflow(load_workflow(INCREMENT)) == []
    assert validate_workflow(load_workflow(VERIFY)) == []


@pytest.fixture
def engine(tmp_path: Path) -> WorkflowEngine:
    config = load_config().model_copy(update={"workspace": str(tmp_path)})
    config.llm = config.llm.model_copy(update={"provider": "mock"})
    return WorkflowEngine(config)


def test_increment_skips_planner_requirement_review(engine: WorkflowEngine) -> None:
    run = engine.run(INCREMENT)
    assert run.status == "DONE"
    assert "planner" not in run.node_outputs
    assert "requirement" not in run.node_outputs
    assert "review" not in run.node_outputs
    assert "coding" in run.node_outputs
    assert "frontend" in run.node_outputs
    assert "testing" in run.node_outputs


def test_verify_does_not_enter_debug_on_fail(engine: WorkflowEngine) -> None:
    run = engine.run(VERIFY, params_override={"force_test_status": "fail"})
    assert run.status == "DONE"
    assert "debug" not in run.node_outputs
    assert run.node_outputs["testing"]["passed"] is False


def test_402_is_unfixable() -> None:
    assert is_unfixable_debug_failure('OpenAI API 错误 (402): Insufficient Balance') is True
    assert is_unfixable_debug_failure("syntax error main.py") is False


def test_debug_skips_llm_on_unfixable_balance(monkeypatch, tmp_path: Path) -> None:
    for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    base = load_config()
    config = base.model_copy(
        update={
            "workspace": str(tmp_path),
            "llm": base.llm.model_copy(update={"provider": "mock", "api_key": None}),
        }
    )
    runner = HybridAgentRunner(config)
    ctx = AgentRunContext(
        run_id="r-unfix",
        params={"project_mode": True, "project_root": "workspaces/x"},
        nodes_outputs={
            "testing": {
                "passed": False,
                "failures": ['OpenAI API 错误 (402): Insufficient Balance'],
                "log_summary": "Insufficient Balance",
            }
        },
        node_id="debug",
    )
    result = runner.run("debug", {}, ctx)
    assert result.success is True
    assert result.output["fixed"] is False
    assert result.output["status"] == "unfixable"
