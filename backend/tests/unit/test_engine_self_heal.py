from __future__ import annotations

from pathlib import Path

from mawp.config.loader import AgentConfig
from mawp.core.engine import WorkflowEngine
from mawp.core.models import Workflow, WorkflowEdge, WorkflowNode
from mawp.runtime.agents import AgentResult, AgentRunContext
from mawp.storage.store import RunStore


class ScriptedRunner:
    def __init__(self, script: dict[str, list[AgentResult]]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[str] = []
        self.inputs: list[dict] = []

    def run(self, agent: str, input_data: dict, ctx: AgentRunContext) -> AgentResult:
        self.calls.append(agent)
        self.inputs.append(dict(input_data or {}))
        q = self.script.setdefault(agent, [])
        if q:
            return q.pop(0)
        if agent == "testing":
            return AgentResult(
                success=True,
                output={
                    "passed": True,
                    "status": "pass",
                    "failures": [],
                    "log_summary": "ok",
                    "attempt": 1,
                },
            )
        if agent == "review":
            return AgentResult(
                success=True,
                output={"status": "pass", "blocking_count": 0, "findings": []},
            )
        return AgentResult(success=True, output={"status": "ok", "agent": agent})


def _deliver_wf(**params: object) -> Workflow:
    merged: dict = {
        "self_heal": True,
        "heal_max_rounds": 3,
        "heal_on_review_blocking": True,
        "node_max_retries": 3,
        "node_retry_delay": 0,
    }
    merged.update(params)
    return Workflow(
        id="demo-code-agent-deliver",
        name="deliver",
        version="0.2.0",
        entry="start",
        params=merged,
        nodes=[
            WorkflowNode(id="start", type="start"),
            WorkflowNode(id="coding", type="agent", agent="coding", input={}),
            WorkflowNode(id="testing", type="agent", agent="testing", input={}),
            WorkflowNode(id="check_test", type="condition"),
            WorkflowNode(id="debug", type="agent", agent="debug", input={}),
            WorkflowNode(id="review", type="agent", agent="review", input={}),
            WorkflowNode(id="check_review", type="condition"),
            WorkflowNode(
                id="human_review",
                type="human_checkpoint",
                raw={
                    "reason": "review blocking",
                    "allowed": ["approve", "reject", "input"],
                },
            ),
            WorkflowNode(id="end", type="end"),
        ],
        edges=[
            WorkflowEdge(from_id="start", to_id="coding"),
            WorkflowEdge(from_id="coding", to_id="testing"),
            WorkflowEdge(from_id="testing", to_id="check_test"),
            WorkflowEdge(
                from_id="check_test",
                to_id="debug",
                when="nodes.testing.outputs.passed == false",
            ),
            WorkflowEdge(from_id="check_test", to_id="review", when="default"),
            WorkflowEdge(from_id="debug", to_id="testing", loop=True, max_traversals=5),
            WorkflowEdge(from_id="review", to_id="check_review"),
            WorkflowEdge(
                from_id="check_review",
                to_id="human_review",
                when="nodes.review.outputs.status == 'blocking'",
            ),
            WorkflowEdge(from_id="check_review", to_id="end", when="default"),
            WorkflowEdge(from_id="human_review", to_id="end"),
        ],
    )


def _engine(tmp_path: Path, runner: ScriptedRunner) -> WorkflowEngine:
    config = AgentConfig(workspace=str(tmp_path), llm={"provider": "mock"})
    return WorkflowEngine(config, agent_runner=runner)  # type: ignore[arg-type]


def _events(tmp_path: Path, run_id: str) -> list[dict]:
    return RunStore(tmp_path).read_events(run_id)


def test_transient_disconnect_retries_without_heal(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        {
            "coding": [
                AgentResult(
                    success=False,
                    error="OpenAI 请求失败: Server disconnected without sending a response.",
                ),
                AgentResult(success=True, output={"status": "ok", "changed_files": []}),
            ]
        }
    )
    run = _engine(tmp_path, runner).run(_deliver_wf())
    assert run.status == "DONE"
    assert (run.heal or {}).get("round", 0) == 0
    types = [e["type"] for e in _events(tmp_path, run.run_id)]
    assert "node_retry" in types
    assert "heal_attempt" not in types
    assert runner.calls.count("coding") == 2


def test_review_blocking_goto_coding(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        {
            "review": [
                AgentResult(
                    success=True,
                    output={"status": "blocking", "blocking_count": 1, "findings": ["x"]},
                ),
                AgentResult(
                    success=True,
                    output={"status": "pass", "blocking_count": 0, "findings": []},
                ),
            ]
        }
    )
    run = _engine(tmp_path, runner).run(_deliver_wf())
    assert run.status == "DONE"
    assert (run.heal or {}).get("round") == 1
    assert (run.heal or {}).get("last_reason") == "review_blocking"
    assert (run.heal or {}).get("last_to") == "coding"
    types = [e["type"] for e in _events(tmp_path, run.run_id)]
    assert "heal_attempt" in types
    assert "heal_handoff" not in types
    assert "coding" in runner.calls
    assert runner.calls.count("review") == 2
    assert (run.heal or {}).get("selected_model") == "deepseek-v4-pro"
    assert any(inp.get("heal_model") == "deepseek-v4-pro" for inp in runner.inputs)
    heal_events = [e for e in _events(tmp_path, run.run_id) if e["type"] == "heal_attempt"]
    assert heal_events
    assert heal_events[0].get("selected_model") == "deepseek-v4-pro"


def test_heal_budget_exhausted_waiting_user(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        {
            "review": [
                AgentResult(
                    success=True,
                    output={"status": "blocking", "blocking_count": 1, "findings": ["x"]},
                ),
                AgentResult(
                    success=True,
                    output={"status": "blocking", "blocking_count": 1, "findings": ["x"]},
                ),
            ]
        }
    )
    run = _engine(tmp_path, runner).run(_deliver_wf(heal_max_rounds=1))
    assert run.status == "WAITING_USER"
    assert run.current_node_id == "human_review"
    types = [e["type"] for e in _events(tmp_path, run.run_id)]
    assert "heal_attempt" in types
    assert "heal_handoff" in types
    assert (run.heal or {}).get("round") == 1


def test_self_heal_false_max_steps_fails(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        {
            "review": [
                AgentResult(success=False, error="超过 max_steps=6"),
            ]
        }
    )
    run = _engine(tmp_path, runner).run(_deliver_wf(self_heal=False))
    assert run.status == "FAILED"
    assert "max_steps" in (run.error or "")
    types = [e["type"] for e in _events(tmp_path, run.run_id)]
    assert "heal_attempt" not in types


def test_max_steps_rerun_with_summary(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        {
            "review": [
                AgentResult(success=False, error="超过 max_steps=6"),
                AgentResult(
                    success=True,
                    output={"status": "pass", "blocking_count": 0, "findings": []},
                ),
            ]
        }
    )
    run = _engine(tmp_path, runner).run(_deliver_wf())
    assert run.status == "DONE"
    assert (run.heal or {}).get("round") == 1
    types = [e["type"] for e in _events(tmp_path, run.run_id)]
    assert "heal_attempt" in types
    assert any("heal_summary" in (inp or {}) for inp in runner.inputs)
    assert runner.calls.count("review") == 2


def test_testing_fail_attaches_repair_instruction(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        {
            "testing": [
                AgentResult(
                    success=True,
                    output={
                        "passed": False,
                        "status": "fail",
                        "failures": ["SyntaxError: invalid syntax"],
                        "log_summary": "boom",
                        "attempt": 1,
                    },
                ),
                AgentResult(
                    success=True,
                    output={
                        "passed": True,
                        "status": "pass",
                        "failures": [],
                        "log_summary": "ok",
                        "attempt": 2,
                    },
                ),
            ]
        }
    )
    run = _engine(tmp_path, runner).run(_deliver_wf())
    assert run.status == "DONE"
    assert "debug" in runner.calls
    assert any(bool(inp.get("repair_instruction")) for inp in runner.inputs)
    assert (run.heal or {}).get("round") == 1
    assert any(inp.get("heal_model") == "deepseek-v4-flash" for inp in runner.inputs)
