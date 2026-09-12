from __future__ import annotations

from typing import Any, Literal

from mawp.config.loader import AgentConfig
from mawp.core.expr import ExprError, ExprEvaluator
from mawp.core.loader import load_workflow
from mawp.core.models import Workflow, WorkflowNode
from mawp.core.template import render_value
from mawp.core.validate import validate_workflow
from mawp.runtime.agent_runtime import AgentRuntime
from mawp.runtime.agents import AgentResult, AgentRunContext, AgentRunner, MockAgentRunner
from mawp.runtime.artifact_saver import save_deliver_artifacts
from mawp.runtime.hybrid import AgentRuntimeAsRunner, HybridAgentRunner
from mawp.runtime.self_heal import (
    HealAction,
    HealDecision,
    SelfHealPolicy,
    is_transient_error,
    self_heal_enabled,
)
from mawp.storage.store import RunRecord, RunStore, new_run_id, utc_now_iso
from mawp.tools.registry import ToolRegistry
from mawp.tools.types import ToolCallContext

ResumeAction = Literal["approve", "reject", "input"]


class IllegalStateError(RuntimeError):
    """Run is not in the expected status for the requested operation."""


class ResumeError(RuntimeError):
    """Resume rejected due to missing checkpoint / bad action / routing."""


class WorkflowEngine:
    def __init__(
        self,
        config: AgentConfig,
        *,
        registry: ToolRegistry | None = None,
        store: RunStore | None = None,
        agent_runner: AgentRunner | None = None,
        agent_runtime: AgentRuntime | None = None,
    ):
        self.config = config
        self.registry = registry or ToolRegistry(config)
        self.store = store or RunStore(config.workspace_path())
        mock = MockAgentRunner(config.workspace_path())
        if agent_runner is not None:
            self.agent_runner: AgentRunner = agent_runner
        elif agent_runtime is not None:
            # Coding/Debug → Hybrid；已注册 Spec → AgentRuntime；其余含 Testing/Ship → Mock(C)
            self.agent_runner = HybridAgentRunner(
                config,
                registry=self.registry,
                fallback=AgentRuntimeAsRunner(agent_runtime, fallback=mock),
            )
        else:
            self.agent_runner = HybridAgentRunner(
                config, registry=self.registry, fallback=mock
            )
        self._expr = ExprEvaluator()
        self.agent_runtime = agent_runtime
        self._heal = SelfHealPolicy(config)

    def run(
        self,
        workflow: Workflow | str,
        *,
        params_override: dict[str, Any] | None = None,
    ) -> RunRecord:
        if not isinstance(workflow, Workflow):
            workflow = load_workflow(workflow)

        errors = validate_workflow(workflow)
        if errors:
            raise ValueError("工作流校验失败:\n" + "\n".join(f"- {e}" for e in errors))

        params = dict(workflow.params)
        if params_override:
            params.update(params_override)

        run = RunRecord(
            run_id=new_run_id(),
            workflow_id=workflow.id,
            status="INIT",
            params=params,
            workflow_path=workflow.source_path,
        )
        self.store.save_run(run)
        self.store.append_event(run.run_id, {"type": "run_start", "status": "INIT"})

        run.status = "RUNNING"
        run.current_node_id = workflow.entry
        self.store.save_run(run)

        return self._schedule(workflow, run)

    def run_async(
        self,
        workflow: Workflow | str,
        *,
        params_override: dict[str, Any] | None = None,
    ) -> RunRecord:
        """异步执行：立即返回 RUNNING 的 RunRecord，后台继续调度。"""
        import threading

        if not isinstance(workflow, Workflow):
            workflow = load_workflow(workflow)

        errors = validate_workflow(workflow)
        if errors:
            raise ValueError("工作流校验失败:\n" + "\n".join(f"- {e}" for e in errors))

        params = dict(workflow.params)
        if params_override:
            params.update(params_override)

        run = RunRecord(
            run_id=new_run_id(),
            workflow_id=workflow.id,
            status="INIT",
            params=params,
            workflow_path=workflow.source_path,
        )
        self.store.save_run(run)
        self.store.append_event(run.run_id, {"type": "run_start", "status": "INIT"})

        run.status = "RUNNING"
        run.current_node_id = workflow.entry
        self.store.save_run(run)

        def worker() -> None:
            try:
                self._schedule(workflow, run)
            except Exception as exc:  # noqa: BLE001
                latest = self.store.load_run(run.run_id) or run
                latest.status = "FAILED"
                latest.error = str(exc)
                self.store.append_event(
                    latest.run_id,
                    {"type": "run_end", "status": "FAILED", "error": latest.error},
                )
                self.store.save_run(latest)

        threading.Thread(target=worker, daemon=True, name=f"mawp-run-{run.run_id}").start()
        return run

    def resume(
        self,
        run_id: str,
        action: ResumeAction,
        data: dict[str, Any] | None = None,
    ) -> RunRecord:
        """Resume WAITING_USER run after approve / reject / input (W3 §5)."""
        run = self.store.load_run(run_id)
        if run is None:
            raise ResumeError(f"run not found: {run_id}")
        if run.status != "WAITING_USER":
            raise IllegalStateError(
                f"[run={run_id}] illegal state: expected WAITING_USER, got {run.status}"
            )

        cp = run.checkpoint or self.store.load_checkpoint(run_id)
        if not cp:
            raise ResumeError(f"[run={run_id}] checkpoint not found")

        if action not in ("approve", "reject", "input"):
            raise ResumeError(f"[run={run_id}] invalid action {action!r}")

        if not run.workflow_path:
            raise ResumeError(f"[run={run_id}] missing workflow_path")
        workflow = load_workflow(run.workflow_path)

        node_id = str(cp.get("node_id") or run.current_node_id or "")
        human_node = workflow.node_map().get(node_id)
        if human_node is None or human_node.type != "human_checkpoint":
            raise ResumeError(f"[run={run_id}] checkpoint node invalid: {node_id}")

        allowed = cp.get("allowed") or human_node.raw.get("allowed") or [
            "approve",
            "reject",
            "input",
        ]
        if action not in allowed:
            raise ResumeError(
                f"[run={run_id}] action {action!r} not in allowed={allowed}"
            )

        resolution = {
            "action": action,
            "data": data or {},
            "at": utc_now_iso(),
        }
        cp = dict(cp)
        cp["resolution"] = resolution
        run.checkpoint = cp
        self.store.save_checkpoint(run_id, cp)

        run.node_outputs[node_id] = {
            "decision": action,
            "input": (data or {}).get("text")
            if action == "input"
            else ((data or {}) if data else None),
        }

        self.store.append_event(
            run.run_id,
            {
                "type": "resumed",
                "node_id": node_id,
                "action": action,
                "data": data or {},
            },
        )

        outs = workflow.outgoing(node_id)
        if not outs:
            run.status = "FAILED"
            run.error = f"[node={node_id}] human_checkpoint 无出边，无法恢复"
            run.checkpoint = cp
            self.store.append_event(
                run.run_id, {"type": "run_end", "status": "FAILED", "error": run.error}
            )
            self.store.save_run(run)
            return run

        next_id = outs[0].to_id
        edge_counts: dict[tuple[str, str], int] = {}
        for k, v in (cp.get("edge_loop_counts") or {}).items():
            if isinstance(k, str) and "\x1f" in k:
                a, b = k.split("\x1f", 1)
                edge_counts[(a, b)] = int(v)
        try:
            next_id = self._take_edge(
                workflow, node_id, next_id, edge_counts=edge_counts
            )
        except RuntimeError as exc:
            run.status = "FAILED"
            run.error = str(exc)
            run.checkpoint = cp
            self.store.append_event(
                run.run_id, {"type": "run_end", "status": "FAILED", "error": run.error}
            )
            self.store.save_run(run)
            return run

        run.checkpoint = None
        self.store.delete_checkpoint(run_id)
        run.status = "RUNNING"
        run.current_node_id = next_id
        self.store.save_run(run)
        return self._schedule(workflow, run, edge_counts=edge_counts)

    def _schedule(
        self,
        workflow: Workflow,
        run: RunRecord,
        *,
        edge_counts: dict[tuple[str, str], int] | None = None,
    ) -> RunRecord:
        node_map = workflow.node_map()
        params = run.params
        nodes_outputs = dict(run.node_outputs)
        current_id: str | None = run.current_node_id
        edge_counts = dict(edge_counts or {})
        self._ensure_heal_state(workflow, run)

        try:
            while current_id is not None:
                node = node_map[current_id]
                run.current_node_id = current_id
                run.node_outputs = nodes_outputs
                self.store.save_run(run)
                self.store.append_event(
                    run.run_id,
                    {
                        "type": "node_start",
                        "node_id": current_id,
                        "node_type": node.type,
                    },
                )

                if node.type == "start":
                    self.store.append_event(
                        run.run_id,
                        {"type": "node_end", "node_id": current_id, "status": "ok"},
                    )
                    nxt = self._next_node(
                        workflow, current_id, params=params, nodes_outputs=nodes_outputs
                    )
                    current_id = (
                        self._take_edge(
                            workflow, current_id, nxt, edge_counts=edge_counts
                        )
                        if nxt
                        else None
                    )
                    continue

                if node.type == "end":
                    run.status = "DONE"
                    run.current_node_id = current_id
                    run.node_outputs = nodes_outputs
                    self.store.append_event(
                        run.run_id,
                        {"type": "node_end", "node_id": current_id, "status": "ok"},
                    )
                    self.store.append_event(
                        run.run_id, {"type": "run_end", "status": "DONE"}
                    )
                    self.store.save_run(run)

                    # 如果是 project_mode，把产物自动保存到 project_root
                    project_root = run.params.get("project_root")
                    if project_root and nodes_outputs:
                        try:
                            save_deliver_artifacts(
                                workspace=self.config.workspace_path(),
                                run=run,
                                node_outputs=nodes_outputs,
                                project_root=project_root,
                            )
                        except Exception as exc:  # noqa: BLE001
                            # 不让保存失败阻断主流程
                            self.store.append_event(
                                run.run_id,
                                {
                                    "type": "artifact_save_failed",
                                    "error": str(exc),
                                },
                            )

                    return run

                if node.type == "tool":
                    outputs, duration_ms = self._run_tool_node(
                        node,
                        params=params,
                        nodes_outputs=nodes_outputs,
                        run_id=run.run_id,
                    )
                    nodes_outputs[node.id] = outputs
                    run.node_outputs = nodes_outputs
                    self.store.append_event(
                        run.run_id,
                        {
                            "type": "node_end",
                            "node_id": current_id,
                            "status": "ok",
                            "duration_ms": duration_ms,
                        },
                    )
                    nxt = self._next_node(
                        workflow, current_id, params=params, nodes_outputs=nodes_outputs
                    )
                    current_id = (
                        self._take_edge(
                            workflow, current_id, nxt, edge_counts=edge_counts
                        )
                        if nxt
                        else None
                    )
                    continue

                if node.type == "agent":
                    stepped = self._execute_agent_node(
                        workflow,
                        run,
                        node,
                        params=params,
                        nodes_outputs=nodes_outputs,
                        edge_counts=edge_counts,
                    )
                    if isinstance(stepped, RunRecord):
                        return stepped
                    current_id = stepped
                    continue

                if node.type == "condition":
                    nxt = self._select_condition_edge(
                        workflow,
                        node.id,
                        params=params,
                        nodes_outputs=nodes_outputs,
                    )
                    self.store.append_event(
                        run.run_id,
                        {
                            "type": "node_end",
                            "node_id": current_id,
                            "status": "ok",
                            "next": nxt,
                        },
                    )
                    current_id = self._take_edge(
                        workflow, current_id, nxt, edge_counts=edge_counts
                    )
                    continue

                if node.type == "human_checkpoint":
                    return self._pause_human(
                        workflow,
                        run,
                        node,
                        nodes_outputs=nodes_outputs,
                        edge_counts=edge_counts,
                    )

                raise RuntimeError(f"未知节点类型: {node.type}（节点 {node.id}）")
        except Exception as exc:
            run.status = "FAILED"
            run.failed_node_id = run.current_node_id
            run.error = str(exc)
            run.node_outputs = nodes_outputs
            self.store.append_event(
                run.run_id,
                {
                    "type": "node_end",
                    "node_id": run.current_node_id,
                    "status": "failed",
                    "error": str(exc),
                },
            )
            self.store.append_event(
                run.run_id, {"type": "run_end", "status": "FAILED", "error": str(exc)}
            )
            self.store.save_run(run)

            project_root = run.params.get("project_root")
            if project_root and nodes_outputs:
                try:
                    save_deliver_artifacts(
                        workspace=self.config.workspace_path(),
                        run=run,
                        node_outputs=nodes_outputs,
                        project_root=project_root,
                    )
                except Exception as save_exc:  # noqa: BLE001
                    self.store.append_event(
                        run.run_id,
                        {
                            "type": "artifact_save_failed",
                            "error": str(save_exc),
                        },
                    )
            return run

        run.status = "FAILED"
        run.error = "执行意外结束（未到达 end / WAITING_USER）"
        self.store.append_event(
            run.run_id, {"type": "run_end", "status": "FAILED", "error": run.error}
        )
        self.store.save_run(run)
        return run

    def _take_edge(
        self,
        workflow: Workflow,
        from_id: str,
        to_id: str | None,
        *,
        edge_counts: dict[tuple[str, str], int],
    ) -> str | None:
        if to_id is None:
            return None
        candidates = [
            e for e in workflow.outgoing(from_id) if e.to_id == to_id and e.loop
        ]
        for edge in candidates:
            key = (edge.from_id, edge.to_id)
            edge_counts[key] = edge_counts.get(key, 0) + 1
            limit = (
                edge.max_traversals
                if edge.max_traversals is not None
                else workflow.default_loop_max
            )
            if edge_counts[key] > int(limit):
                raise RuntimeError(
                    f"显式回边超过上限 max_traversals={limit}: "
                    f"{edge.from_id} -> {edge.to_id} (count={edge_counts[key]})"
                )
        return to_id

    def _pause_human(
        self,
        workflow: Workflow,
        run: RunRecord,
        node: WorkflowNode,
        *,
        nodes_outputs: dict[str, dict[str, Any]],
        edge_counts: dict[tuple[str, str], int] | None = None,
    ) -> RunRecord:
        reason = str(node.raw.get("reason") or "").strip()
        allowed = node.raw.get("allowed") or ["approve", "reject", "input"]
        if isinstance(allowed, list):
            allowed = [str(x) for x in allowed]
        else:
            allowed = ["approve", "reject", "input"]

        try:
            reason = render_value(
                reason, params=run.params, nodes_outputs=nodes_outputs, vars={}
            )
            if not isinstance(reason, str):
                reason = str(reason)
        except Exception:
            pass

        checkpoint = {
            "run_id": run.run_id,
            "node_id": node.id,
            "reason": reason,
            "allowed": allowed,
            "created_at": utc_now_iso(),
            "resolution": None,
            "edge_loop_counts": {
                f"{a}\x1f{b}": c for (a, b), c in (edge_counts or {}).items()
            },
        }
        run.checkpoint = checkpoint
        run.node_outputs = nodes_outputs
        run.status = "WAITING_USER"
        run.current_node_id = node.id
        self.store.save_checkpoint(run.run_id, checkpoint)
        self.store.append_event(
            run.run_id,
            {
                "type": "waiting_user",
                "node_id": node.id,
                "reason": reason,
                "allowed": allowed,
            },
        )
        self.store.append_event(
            run.run_id,
            {"type": "node_end", "node_id": node.id, "status": "paused"},
        )
        self.store.save_run(run)
        return run

    def _select_condition_edge(
        self,
        workflow: Workflow,
        node_id: str,
        *,
        params: dict[str, Any],
        nodes_outputs: dict[str, dict[str, Any]],
    ) -> str:
        outs = workflow.outgoing(node_id)
        ctx = {
            "params": params,
            "vars": {},
            "nodes": {
                nid: {"outputs": outs_map} for nid, outs_map in nodes_outputs.items()
            },
        }
        default_to: str | None = None
        for edge in outs:
            when = edge.when
            if when == "default":
                default_to = edge.to_id
                continue
            if not isinstance(when, str) or not when.strip():
                continue
            try:
                matched = self._expr.evaluate(when, ctx)
            except ExprError as exc:
                raise RuntimeError(
                    f"[node={node_id}] 条件表达式求值失败 ({when!r}): {exc}"
                ) from exc
            if bool(matched):
                return edge.to_id
        if default_to is None:
            raise RuntimeError(f"[node={node_id}] 无匹配分支且缺少 when: default")
        return default_to

    def _consume_heal_inject(self, run: RunRecord) -> dict[str, Any] | None:
        heal = run.heal
        if not isinstance(heal, dict) or not heal.get("inject"):
            return None
        inject = dict(heal.get("inject") or {})
        updated = dict(heal)
        updated.pop("inject", None)
        run.heal = updated
        return inject

    def _ensure_heal_state(self, workflow: Workflow, run: RunRecord) -> None:
        if run.heal is not None:
            return
        if not self_heal_enabled(workflow, run):
            return
        run.heal = {
            "enabled": True,
            "round": 0,
            "max_rounds": int((run.params or {}).get("heal_max_rounds") or 3),
            "last_reason": None,
            "last_from": None,
            "last_to": None,
        }

    def _bump_heal(
        self, run: RunRecord, node: WorkflowNode, decision: HealDecision
    ) -> None:
        params = run.params or {}
        heal = dict(run.heal or {})
        heal["enabled"] = True
        heal["round"] = int(heal.get("round") or 0) + 1
        heal["max_rounds"] = int(
            params.get("heal_max_rounds") or heal.get("max_rounds") or 3
        )
        heal["last_reason"] = decision.reason.value
        heal["last_from"] = node.id
        heal["last_to"] = decision.target_node_id
        if decision.context.get("selected_model"):
            heal["selected_model"] = decision.context["selected_model"]
            heal["model_strategy"] = decision.context.get("model_strategy")
            heal["error_category"] = decision.context.get("error_category")
        run.heal = heal
        self.store.save_run(run)

    def _emit_heal_attempt(
        self, run: RunRecord, node: WorkflowNode, decision: HealDecision
    ) -> None:
        heal = run.heal or {}
        self.store.append_event(
            run.run_id,
            {
                "type": "heal_attempt",
                "node_id": node.id,
                "reason": decision.reason.value,
                "from": node.id,
                "to": decision.target_node_id,
                "round": int(heal.get("round") or 0),
                "max_rounds": int(heal.get("max_rounds") or 3),
                "selected_model": decision.context.get("selected_model")
                or heal.get("selected_model"),
                "model_strategy": decision.context.get("model_strategy")
                or heal.get("model_strategy"),
                "error_category": decision.context.get("error_category")
                or heal.get("error_category"),
            },
        )

    def _store_agent_output(
        self,
        node: WorkflowNode,
        result: AgentResult,
        nodes_outputs: dict[str, dict[str, Any]],
        run: RunRecord,
        *,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        out = dict(result.output or {})
        if result.error:
            out["_error"] = result.error
            out["_success"] = bool(result.success)
        if result.usage:
            out["_usage"] = dict(result.usage)
        if extra:
            out.update(extra)
        nodes_outputs[node.id] = out
        run.node_outputs = nodes_outputs
        return out

    def _execute_agent_node(
        self,
        workflow: Workflow,
        run: RunRecord,
        node: WorkflowNode,
        *,
        params: dict[str, Any],
        nodes_outputs: dict[str, dict[str, Any]],
        edge_counts: dict[tuple[str, str], int],
    ) -> RunRecord | str | None:
        result = self._run_agent_node(
            node,
            params=params,
            nodes_outputs=nodes_outputs,
            run_id=run.run_id,
            extra_input=self._consume_heal_inject(run),
        )
        self._store_agent_output(node, result, nodes_outputs, run)
        decision = self._heal.decide(
            workflow, run, node, result, allow_transient_retry=False
        )

        if decision.action == HealAction.RERUN_WITH_SUMMARY:
            extra = {
                "heal_summary": (decision.context or {}).get("heal_summary")
                or result.error,
                "tool_summary": (decision.context or {}).get("tool_summary")
                or list(result.tool_calls or [])[-8:],
            }
            if decision.context.get("selected_model"):
                extra["heal_model"] = decision.context["selected_model"]
            if decision.consume_heal_round:
                self._bump_heal(run, node, decision)
            self._emit_heal_attempt(run, node, decision)
            result = self._run_agent_node(
                node,
                params=params,
                nodes_outputs=nodes_outputs,
                run_id=run.run_id,
                extra_input=extra,
            )
            self._store_agent_output(node, result, nodes_outputs, run)
            decision = self._heal.decide(
                workflow,
                run,
                node,
                result,
                allow_transient_retry=False,
                allow_rerun=False,
            )

        repair = (decision.context or {}).get("repair_instruction")
        if repair:
            self._store_agent_output(
                node, result, nodes_outputs, run, extra={"repair_instruction": repair}
            )

        if decision.consume_heal_round and decision.action != HealAction.RERUN_WITH_SUMMARY:
            self._bump_heal(run, node, decision)
            self._emit_heal_attempt(run, node, decision)
            # TEST_FAILED 走 YAML → debug：把选型塞进 inject
            if decision.reason.value == "test_failed" and decision.context.get(
                "selected_model"
            ):
                heal = dict(run.heal or {})
                heal["inject"] = {
                    **(heal.get("inject") or {}),
                    "heal_model": decision.context["selected_model"],
                    "repair_instruction": repair,
                    "heal_reason": decision.reason.value,
                }
                run.heal = heal
                self.store.save_run(run)

        usage = dict(result.usage or {})
        self.store.append_event(
            run.run_id,
            {
                "type": "node_end",
                "node_id": node.id,
                "status": "ok" if result.success else "failed",
                "agent": node.agent,
                "usage": usage,
            },
        )
        if usage.get("total_tokens"):
            self.store.append_event(
                run.run_id,
                {
                    "type": "agent_usage",
                    "node_id": node.id,
                    "agent": node.agent,
                    "usage": usage,
                    "model": usage.get("model"),
                },
            )

        if decision.action == HealAction.GOTO and decision.target_node_id:
            inject_payload = {
                "heal_reason": decision.reason.value,
                "from_node": node.id,
                "error": result.error,
                "findings": (result.output or {}).get("findings"),
                "repair_instruction": repair,
            }
            if decision.context.get("selected_model"):
                inject_payload["heal_model"] = decision.context["selected_model"]
            heal = dict(run.heal or {})
            heal["inject"] = inject_payload
            run.heal = heal
            self.store.save_run(run)
            return decision.target_node_id

        if decision.action == HealAction.HANDOFF:
            self.store.append_event(
                run.run_id,
                {
                    "type": "heal_handoff",
                    "node_id": node.id,
                    "reason": decision.reason.value,
                    "round": int((run.heal or {}).get("round") or 0),
                    "max_rounds": int((run.heal or {}).get("max_rounds") or 3),
                },
            )
            hid = decision.target_node_id
            human = workflow.node_map().get(hid) if hid else None
            if human is not None and human.type == "human_checkpoint":
                return self._pause_human(
                    workflow,
                    run,
                    human,
                    nodes_outputs=nodes_outputs,
                    edge_counts=edge_counts,
                )
            raise RuntimeError(
                result.error
                or f"自愈耗尽 ({decision.reason.value})"
            )

        if not result.success:
            raise RuntimeError(
                result.error or f"agent 执行失败: {node.agent}"
            )

        nxt = self._next_node(
            workflow, node.id, params=params, nodes_outputs=nodes_outputs
        )
        if not nxt:
            return None
        return self._take_edge(workflow, node.id, nxt, edge_counts=edge_counts)

    def _run_agent_node(
        self,
        node: WorkflowNode,
        *,
        params: dict[str, Any],
        nodes_outputs: dict[str, dict[str, Any]],
        run_id: str,
        extra_input: dict[str, Any] | None = None,
    ) -> AgentResult:
        assert node.agent
        max_retries = int(params.get("node_max_retries") or 2)
        retry_delay = float(params.get("node_retry_delay") or 1.0)
        last: AgentResult | None = None

        for attempt in range(1, max_retries + 1):
            rendered = render_value(
                node.input, params=params, nodes_outputs=nodes_outputs, vars={}
            )
            if rendered is None:
                rendered = {}
            if not isinstance(rendered, dict):
                raise TypeError(f"agent 节点 input 必须是对象: {node.id}")
            merged = dict(rendered)
            if extra_input:
                merged.update(extra_input)
            testing_out = nodes_outputs.get("testing") or {}
            if node.agent == "debug" and testing_out.get("repair_instruction"):
                merged.setdefault(
                    "repair_instruction", testing_out["repair_instruction"]
                )

            # 瞬时故障重试：按 failover 列表换模型
            if (
                last is not None
                and not last.success
                and is_transient_error(last.error)
                and "heal_model" not in merged
            ):
                from mawp.runtime.heal_models import select_heal_model

                choice = select_heal_model(
                    category="transient",
                    agent=str(node.agent or node.id),
                    heal_round=1,
                    agent_models=dict(self.config.agents.models or {}),
                    heal_cfg=self.config.heal_models,
                    failover_attempt=max(0, attempt - 2),
                    global_default=self.config.llm.model,
                )
                merged["heal_model"] = choice.model

            result = self.agent_runner.run(
                node.agent,
                merged,
                AgentRunContext(
                    run_id=run_id,
                    params=params,
                    nodes_outputs=nodes_outputs,
                    node_id=node.id,
                ),
            )
            last = result
            if result.success:
                return result
            if not is_transient_error(result.error) or attempt >= max_retries:
                return result

            self.store.append_event(
                run_id,
                {
                    "type": "node_retry",
                    "node_id": node.id,
                    "agent": node.agent,
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "error": str(result.error)[:500],
                },
            )
            if retry_delay > 0:
                import time

                time.sleep(retry_delay)

        assert last is not None
        return last

    def _run_tool_node(
        self,
        node: WorkflowNode,
        *,
        params: dict[str, Any],
        nodes_outputs: dict[str, dict[str, Any]],
        run_id: str,
    ) -> tuple[dict[str, Any], int]:
        assert node.tool
        rendered = render_value(
            node.input, params=params, nodes_outputs=nodes_outputs, vars={}
        )
        if not isinstance(rendered, dict):
            raise TypeError(f"tool 节点 input 必须是对象: {node.id}")

        ctx = ToolCallContext(agent_name="workflow", session_id=run_id, actor_id="platform")
        result = self.registry.execute(node.tool, rendered, ctx)
        if not result.success:
            raise RuntimeError(result.error or f"工具执行失败: {node.tool}")

        data = result.data if isinstance(result.data, dict) else {"data": result.data}
        return data, result.duration_ms

    def _next_node(
        self,
        workflow: Workflow,
        node_id: str,
        *,
        params: dict[str, Any],
        nodes_outputs: dict[str, dict[str, Any]],
    ) -> str | None:
        node = workflow.node_map().get(node_id)
        if node and node.type == "condition":
            return self._select_condition_edge(
                workflow, node_id, params=params, nodes_outputs=nodes_outputs
            )
        outs = workflow.outgoing(node_id)
        if not outs:
            return None
        if len(outs) > 1:
            return outs[0].to_id
        return outs[0].to_id
