from __future__ import annotations

from mawp.core.models import Workflow, WorkflowEdge, WorkflowNode
from mawp.runtime.agents import AgentResult
from mawp.runtime.self_heal import HealAction, HealReason, SelfHealPolicy
from mawp.storage.store import RunRecord


def _deliver_wf(**params: object) -> Workflow:
    merged = {
        "self_heal": True,
        "heal_max_rounds": 3,
        "heal_on_review_blocking": True,
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
            WorkflowNode(id="coding", type="agent", agent="coding"),
            WorkflowNode(id="testing", type="agent", agent="testing"),
            WorkflowNode(id="debug", type="agent", agent="debug"),
            WorkflowNode(id="review", type="agent", agent="review"),
            WorkflowNode(id="check_review", type="condition"),
            WorkflowNode(id="human_review", type="human_checkpoint"),
            WorkflowNode(id="end", type="end"),
        ],
        edges=[
            WorkflowEdge(from_id="start", to_id="coding"),
            WorkflowEdge(from_id="coding", to_id="testing"),
            WorkflowEdge(
                from_id="testing",
                to_id="debug",
                when="nodes.testing.outputs.passed == false",
                loop=True,
                max_traversals=5,
            ),
            WorkflowEdge(from_id="testing", to_id="review", when="default"),
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


def _run(*, round: int = 0, **params: object) -> RunRecord:
    merged = {"self_heal": True, "heal_max_rounds": 3}
    merged.update(params)
    return RunRecord(
        run_id="r1",
        workflow_id="demo-code-agent-deliver",
        status="RUNNING",
        params=merged,
        heal={
            "enabled": True,
            "round": round,
            "max_rounds": int(merged.get("heal_max_rounds") or 3),
            "last_reason": None,
            "last_from": None,
            "last_to": None,
        },
    )


def test_disabled_returns_continue() -> None:
    wf = _deliver_wf(self_heal=False)
    run = _run(self_heal=False)
    d = SelfHealPolicy().decide(
        wf,
        run,
        wf.node_map()["testing"],
        AgentResult(success=True, output={"passed": False}),
    )
    assert d.action == HealAction.CONTINUE
    assert d.reason == HealReason.NONE
    assert d.consume_heal_round is False


def test_hello_graph_not_deliver() -> None:
    wf = Workflow(
        id="hello",
        name="h",
        version="1",
        entry="start",
        nodes=[
            WorkflowNode(id="start", type="start"),
            WorkflowNode(id="end", type="end"),
        ],
        edges=[WorkflowEdge(from_id="start", to_id="end")],
    )
    run = RunRecord(run_id="r", workflow_id="hello", status="RUNNING", params={})
    d = SelfHealPolicy().decide(
        wf, run, wf.node_map()["start"], AgentResult(success=False, error="x")
    )
    assert d.action == HealAction.CONTINUE
    assert d.reason == HealReason.NONE


def test_transient_retry_node() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(
        wf,
        _run(),
        wf.node_map()["coding"],
        AgentResult(
            success=False,
            error="OpenAI 请求失败: Server disconnected without sending a response.",
        ),
    )
    assert d.action == HealAction.RETRY_NODE
    assert d.reason == HealReason.TRANSIENT
    assert d.consume_heal_round is False


def test_transient_after_retries_exhausted_is_agent_failed() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(
        wf,
        _run(),
        wf.node_map()["coding"],
        AgentResult(
            success=False,
            error="OpenAI 请求失败: Server disconnected without sending a response.",
        ),
        allow_transient_retry=False,
    )
    assert d.action == HealAction.GOTO
    assert d.target_node_id == "debug"
    assert d.reason == HealReason.AGENT_FAILED
    assert d.consume_heal_round is True


def test_max_steps_rerun_with_summary() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(
        wf,
        _run(),
        wf.node_map()["review"],
        AgentResult(success=False, error="超过 max_steps=6"),
    )
    assert d.action == HealAction.RERUN_WITH_SUMMARY
    assert d.reason == HealReason.MAX_STEPS
    assert d.consume_heal_round is True


def test_test_failed_continue_yaml_debug_and_consume_heal() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(
        wf,
        _run(),
        wf.node_map()["testing"],
        AgentResult(
            success=True,
            output={"passed": False, "failures": ["boom"], "log_summary": "err"},
        ),
    )
    assert d.action == HealAction.CONTINUE
    assert d.reason == HealReason.TEST_FAILED
    assert d.consume_heal_round is True
    assert "repair_instruction" in d.context


def test_review_blocking_goto_coding() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(
        wf,
        _run(),
        wf.node_map()["review"],
        AgentResult(
            success=True,
            output={"status": "blocking", "blocking_count": 1, "findings": ["x"]},
        ),
    )
    assert d.action == HealAction.GOTO
    assert d.target_node_id == "coding"
    assert d.reason == HealReason.REVIEW_BLOCKING
    assert d.consume_heal_round is True


def test_review_blocking_selects_pro_with_config() -> None:
    from mawp.config.loader import AgentConfig

    wf = _deliver_wf()
    d = SelfHealPolicy(AgentConfig()).decide(
        wf,
        _run(),
        wf.node_map()["review"],
        AgentResult(
            success=True,
            output={"status": "blocking", "blocking_count": 1, "findings": ["x"]},
        ),
    )
    assert d.action == HealAction.GOTO
    assert d.context.get("selected_model") == "deepseek-v4-pro"
    assert d.context.get("error_category") == "review_blocking"
    assert d.context.get("model_strategy") == "by_category"


def test_syntax_test_failed_selects_flash_for_debug() -> None:
    from mawp.config.loader import AgentConfig

    wf = _deliver_wf()
    d = SelfHealPolicy(AgentConfig()).decide(
        wf,
        _run(),
        wf.node_map()["testing"],
        AgentResult(
            success=True,
            output={
                "passed": False,
                "failures": ["SyntaxError: invalid syntax"],
                "log_summary": "boom",
            },
        ),
    )
    assert d.reason == HealReason.TEST_FAILED
    assert d.context.get("selected_model") == "deepseek-v4-flash"
    assert d.context.get("error_category") == "syntax_error"
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(
        wf,
        _run(round=3),
        wf.node_map()["review"],
        AgentResult(success=True, output={"status": "blocking", "blocking_count": 1}),
    )
    assert d.action == HealAction.HANDOFF
    assert d.target_node_id == "human_review"


def test_agent_failed_goto_debug() -> None:
    wf = _deliver_wf()
    d = SelfHealPolicy().decide(
        wf,
        _run(),
        wf.node_map()["coding"],
        AgentResult(success=False, error="unknown boom"),
    )
    assert d.action == HealAction.GOTO
    assert d.target_node_id == "debug"
    assert d.reason == HealReason.AGENT_FAILED
