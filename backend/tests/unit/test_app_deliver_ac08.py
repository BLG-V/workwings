"""D · App deliver（AC-08：Requirement + Frontend 扩展）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mawp.config.loader import load_config
from mawp.core.engine import WorkflowEngine
from mawp.core.loader import load_workflow
from mawp.core.validate import validate_workflow

APP_DELIVER = Path("apps/demo-code-agent/workflows/deliver.yaml")


@pytest.fixture
def engine(tmp_path: Path) -> WorkflowEngine:
    config = load_config().model_copy(update={"workspace": str(tmp_path)})
    config.llm = config.llm.model_copy(update={"provider": "mock"})
    return WorkflowEngine(config)


def test_app_deliver_validate_ok() -> None:
    assert validate_workflow(load_workflow(APP_DELIVER)) == []


def test_app_deliver_happy_path_has_frontend(engine: WorkflowEngine) -> None:
    run = engine.run(APP_DELIVER)
    assert run.status == "DONE"
    assert "requirement" in run.node_outputs
    assert "frontend" in run.node_outputs
    assert run.node_outputs["frontend"]["status"] == "ok"
    assert run.node_outputs["frontend"]["artifacts"]
    assert "tasks" in run.node_outputs["planner"]
    assert run.node_outputs["ship"]["auto_push"] is False


def test_app_deliver_retest_loop(engine: WorkflowEngine) -> None:
    run = engine.run(APP_DELIVER, params_override={"pass_on_attempt": 2})
    assert run.status == "DONE"
    assert run.node_outputs["testing"]["attempt"] == 2
    assert "debug" in run.node_outputs


def test_app_deliver_blocking_then_approve(engine: WorkflowEngine) -> None:
    run = engine.run(APP_DELIVER, params_override={"review_status": "blocking"})
    assert run.status == "WAITING_USER"
    assert run.current_node_id == "human_review"
    run = engine.resume(run.run_id, "approve")
    assert run.status == "DONE"
    assert "ship" in run.node_outputs
