# -*- coding: utf-8 -*-
"""工作流自愈决策：只给出下一步，不执行 Agent、不写文件。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from mawp.runtime.error_classifier import build_repair_instruction, classify_error
from mawp.runtime.heal_models import category_from_heal_reason, select_heal_model

if TYPE_CHECKING:
    from mawp.config.loader import AgentConfig
    from mawp.core.models import Workflow, WorkflowNode
    from mawp.runtime.agents import AgentResult
    from mawp.storage.store import RunRecord

TRANSIENT_MARKERS = (
    "disconnected",
    "timeout",
    "temporar",
    "429",
    "502",
    "503",
    "504",
    "connection reset",
    "server disconnected",
    "empty response",
)


class HealReason(str, Enum):
    TRANSIENT = "transient"
    MAX_STEPS = "max_steps"
    TEST_FAILED = "test_failed"
    REVIEW_BLOCKING = "review_blocking"
    AGENT_FAILED = "agent_failed"
    NONE = "none"


class HealAction(str, Enum):
    CONTINUE = "continue"
    RETRY_NODE = "retry_node"
    RERUN_WITH_SUMMARY = "rerun_with_summary"
    GOTO = "goto"
    HANDOFF = "handoff"


@dataclass
class HealDecision:
    action: HealAction
    reason: HealReason
    target_node_id: str | None = None
    consume_heal_round: bool = False
    context: dict[str, Any] = field(default_factory=dict)


def is_transient_error(text: str | None) -> bool:
    blob = (text or "").lower()
    return any(marker in blob for marker in TRANSIENT_MARKERS)


def is_max_steps_error(text: str | None) -> bool:
    return "max_steps" in (text or "").lower()


def node_agent_name(node: WorkflowNode) -> str:
    return str(node.agent or node.id or "").strip().lower()


def is_deliver_graph(workflow: Workflow) -> bool:
    ids = {n.id.lower() for n in workflow.nodes}
    agents = {str(n.agent).lower() for n in workflow.nodes if n.agent}
    names = ids | agents
    has_quality = "testing" in names
    has_review = "review" in names
    has_fix = "coding" in names or "debug" in names
    return has_quality and has_review and has_fix


def self_heal_enabled(workflow: Workflow, run: RunRecord) -> bool:
    if not is_deliver_graph(workflow):
        return False
    params = run.params or {}
    if "self_heal" in params:
        return bool(params.get("self_heal"))
    return True


def heal_budget_left(run: RunRecord) -> bool:
    params = run.params or {}
    max_rounds = int(params.get("heal_max_rounds") or 3)
    current = 0
    if run.heal:
        current = int(run.heal.get("round") or 0)
        max_rounds = int(run.heal.get("max_rounds") or max_rounds)
    return current < max_rounds


def first_human_node_id(workflow: Workflow) -> str | None:
    for node in workflow.nodes:
        if node.type == "human_checkpoint":
            return node.id
    return None


def _existing_target(workflow: Workflow, *candidates: str) -> str | None:
    node_map = workflow.node_map()
    for cid in candidates:
        if cid and cid in node_map:
            return cid
    return None


class SelfHealPolicy:
    """根据当前节点结果给出自愈下一步。"""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config

    def _model_context(
        self,
        *,
        reason: HealReason,
        agent: str,
        run: RunRecord,
        result: AgentResult,
        failover_attempt: int = 0,
    ) -> dict[str, Any]:
        if self.config is None:
            return {}
        output = result.output or {}
        category = category_from_heal_reason(
            reason.value,
            error_text=str(result.error or ""),
            failures=list(output.get("failures") or []),
            log_summary=str(output.get("log_summary") or ""),
        )
        upcoming = int((run.heal or {}).get("round") or 0) + 1
        choice = select_heal_model(
            category=category,
            agent=agent,
            heal_round=upcoming,
            agent_models=dict(self.config.agents.models or {}),
            heal_cfg=self.config.heal_models,
            failover_attempt=failover_attempt,
            global_default=self.config.llm.model,
        )
        return {
            "error_category": choice.category,
            "selected_model": choice.model,
            "model_strategy": choice.strategy,
        }

    def decide(
        self,
        workflow: Workflow,
        run: RunRecord,
        node: WorkflowNode,
        result: AgentResult,
        *,
        allow_transient_retry: bool = True,
        allow_rerun: bool = True,
    ) -> HealDecision:
        if not self_heal_enabled(workflow, run):
            return HealDecision(action=HealAction.CONTINUE, reason=HealReason.NONE)

        error = result.error
        output = result.output or {}
        agent = node_agent_name(node)
        human_id = first_human_node_id(workflow)

        def handoff(reason: HealReason) -> HealDecision:
            return HealDecision(
                action=HealAction.HANDOFF,
                reason=reason,
                target_node_id=human_id,
                consume_heal_round=False,
            )

        def goto(target: str | None, reason: HealReason) -> HealDecision:
            if not target:
                return handoff(reason)
            target_node = workflow.node_map().get(target)
            target_agent = (
                str(target_node.agent or target).strip().lower()
                if target_node
                else target
            )
            ctx = self._model_context(
                reason=reason, agent=target_agent, run=run, result=result
            )
            return HealDecision(
                action=HealAction.GOTO,
                reason=reason,
                target_node_id=target,
                consume_heal_round=True,
                context=ctx,
            )

        if not result.success and is_transient_error(error):
            if allow_transient_retry:
                ctx = self._model_context(
                    reason=HealReason.TRANSIENT,
                    agent=agent,
                    run=run,
                    result=result,
                    failover_attempt=0,
                )
                return HealDecision(
                    action=HealAction.RETRY_NODE,
                    reason=HealReason.TRANSIENT,
                    consume_heal_round=False,
                    context=ctx,
                )
            if heal_budget_left(run):
                if agent == "debug":
                    target = _existing_target(workflow, "coding", "debug")
                else:
                    target = _existing_target(workflow, "debug", "coding")
                return goto(target, HealReason.AGENT_FAILED)
            return handoff(HealReason.TRANSIENT)

        if not result.success and is_max_steps_error(error):
            if allow_rerun and heal_budget_left(run):
                ctx = {
                    "heal_summary": error,
                    "tool_summary": list(result.tool_calls or [])[-8:],
                }
                ctx.update(
                    self._model_context(
                        reason=HealReason.MAX_STEPS,
                        agent=agent,
                        run=run,
                        result=result,
                    )
                )
                return HealDecision(
                    action=HealAction.RERUN_WITH_SUMMARY,
                    reason=HealReason.MAX_STEPS,
                    consume_heal_round=True,
                    context=ctx,
                )
            if heal_budget_left(run):
                if agent == "debug":
                    target = _existing_target(workflow, "coding", "debug")
                else:
                    target = _existing_target(workflow, "debug", "coding")
                return goto(target, HealReason.MAX_STEPS)
            return handoff(HealReason.MAX_STEPS)

        if agent == "testing" and output.get("passed") is False:
            failures = output.get("failures") or []
            log_summary = str(output.get("log_summary") or "")
            raw = "\n".join(str(f) for f in failures) or log_summary
            instruction = build_repair_instruction(classify_error(raw, log_summary))
            if heal_budget_left(run):
                ctx: dict[str, Any] = {"repair_instruction": instruction}
                ctx.update(
                    self._model_context(
                        reason=HealReason.TEST_FAILED,
                        agent="debug",
                        run=run,
                        result=result,
                    )
                )
                return HealDecision(
                    action=HealAction.CONTINUE,
                    reason=HealReason.TEST_FAILED,
                    consume_heal_round=True,
                    context=ctx,
                )
            return handoff(HealReason.TEST_FAILED)

        if agent == "review" and str(output.get("status") or "").lower() == "blocking":
            if not bool((run.params or {}).get("heal_on_review_blocking", True)):
                return HealDecision(action=HealAction.CONTINUE, reason=HealReason.NONE)
            if heal_budget_left(run):
                return goto(
                    _existing_target(workflow, "coding", "debug"),
                    HealReason.REVIEW_BLOCKING,
                )
            return handoff(HealReason.REVIEW_BLOCKING)

        if not result.success:
            if heal_budget_left(run):
                if agent == "debug":
                    target = _existing_target(workflow, "coding", "debug")
                else:
                    target = _existing_target(workflow, "debug", "coding")
                return goto(target, HealReason.AGENT_FAILED)
            return handoff(HealReason.AGENT_FAILED)

        return HealDecision(action=HealAction.CONTINUE, reason=HealReason.NONE)
