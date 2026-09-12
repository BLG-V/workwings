# A · deliver / Planner / Review（UC-07 骨架）

from __future__ import annotations

from pathlib import Path

import pytest

from mawp.config.loader import load_config
from mawp.core.engine import WorkflowEngine
from mawp.core.loader import load_workflow, parse_workflow_dict
from mawp.core.validate import validate_workflow


DELIVER = Path("examples/deliver/workflow.yaml")


@pytest.fixture
def engine(tmp_path: Path) -> WorkflowEngine:
    config = load_config().model_copy(update={"workspace": str(tmp_path)})
    config.llm = config.llm.model_copy(update={"provider": "mock"})
    return WorkflowEngine(config)


def test_deliver_validate_ok() -> None:
    wf = load_workflow(DELIVER)
    assert validate_workflow(wf) == []


def test_deliver_happy_path_done(engine: WorkflowEngine) -> None:
    run = engine.run(DELIVER)
    assert run.status == "DONE"
    assert "tasks" in run.node_outputs["planner"]
    assert run.node_outputs["testing"]["passed"] is True
    assert run.node_outputs["review"]["status"] == "pass"
    assert "ship" in run.node_outputs
    assert run.node_outputs["ship"]["auto_push"] is False


def test_deliver_test_fail_then_debug_retest(engine: WorkflowEngine) -> None:
    run = engine.run(DELIVER, params_override={"pass_on_attempt": 2})
    assert run.status == "DONE"
    assert run.node_outputs["testing"]["attempt"] == 2
    assert run.node_outputs["testing"]["passed"] is True
    assert "debug" in run.node_outputs


def test_deliver_review_blocking_pauses_not_ship(engine: WorkflowEngine) -> None:
    run = engine.run(DELIVER, params_override={"review_status": "blocking"})
    assert run.status == "WAITING_USER"
    assert run.current_node_id == "human_review"
    assert "ship" not in run.node_outputs

    run = engine.resume(run.run_id, "approve")
    assert run.status == "DONE"
    assert "ship" in run.node_outputs


def test_unmarked_cycle_rejected() -> None:
    raw = {
        "id": "bad-cycle",
        "name": "bad",
        "version": "0.1.0",
        "entry": "start",
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "a", "type": "tool", "tool": "echo", "input": {"text": "a"}},
            {"id": "b", "type": "tool", "tool": "echo", "input": {"text": "b"}},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"from": "start", "to": "a"},
            {"from": "a", "to": "b"},
            {"from": "b", "to": "a"},  # 未标 loop
            {"from": "b", "to": "end"},
        ],
    }
    wf = parse_workflow_dict(raw)
    errs = validate_workflow(wf)
    assert any("检测到环" in e for e in errs)


def test_loop_edge_exceeds_max(engine: WorkflowEngine) -> None:
    """永远 fail 的 testing + 小 max_traversals → FAILED。"""
    raw = {
        "id": "loop-cap",
        "name": "loop-cap",
        "version": "0.1.0",
        "entry": "start",
        "default_loop_max": 1,
        "params": {"pass_on_attempt": 99, "force_test_status": "fail"},
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "testing", "type": "agent", "agent": "testing", "input": {}},
            {"id": "check_test", "type": "condition"},
            {"id": "debug", "type": "agent", "agent": "debug", "input": {}},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"from": "start", "to": "testing"},
            {"from": "testing", "to": "check_test"},
            {
                "from": "check_test",
                "to": "debug",
                "when": "nodes.testing.outputs.passed == false",
            },
            {"from": "check_test", "to": "end", "when": "default"},
            {"from": "debug", "to": "testing", "loop": True, "max_traversals": 1},
        ],
    }
    wf = parse_workflow_dict(raw)
    assert validate_workflow(wf) == []
    run = engine.run(wf)
    assert run.status == "FAILED"
    assert "max_traversals" in (run.error or "")
