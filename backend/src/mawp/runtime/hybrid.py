# -*- coding: utf-8 -*-
"""B · HybridAgentRunner：有 DeepSeek Key 时八 Agent 走 LLM；否则 stub/Mock。"""

from __future__ import annotations

import json
from typing import Any
import re

from mawp.config.loader import AgentConfig
from mawp.llm.base import LLMAdapter
from mawp.llm.factory import create_llm_adapter
from mawp.runtime.agent_runtime import AgentRuntime, RuntimeContext
from mawp.runtime.agents import (
    AgentResult,
    AgentRunContext,
    AgentRunner,
    MockAgentRunner,
)
from mawp.runtime.deliver_specs import DELIVER_AGENTS, build_deliver_specs
from mawp.runtime.web_scaffold import (
    HEALTH_PROBE_JS,
    health_probe_html,
    repair_note_html,
    web_asset_files,
)
from mawp.tools.registry import ToolRegistry
from mawp.tools.types import ToolCallContext


def _heal_model_override(
    input_data: dict[str, Any],
    ctx: AgentRunContext,
) -> str | None:
    raw = input_data.get("heal_model") or ctx.params.get("heal_model")
    if not isinstance(raw, str):
        return None
    name = raw.strip()
    if not name or name in ("keep", "mock"):
        return None
    return name


class AgentRuntimeAsRunner:
    """把 AgentRuntime 适配为引擎 AgentRunner（已注册 spec 走 LLM，否则 fallback）。"""

    def __init__(
        self,
        runtime: AgentRuntime,
        *,
        fallback: AgentRunner | None = None,
    ) -> None:
        self.runtime = runtime
        self.fallback: AgentRunner = fallback or MockAgentRunner()

    def run(
        self,
        agent: str,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        name = (agent or "").strip()
        if not name or self.runtime.get(name) is None:
            return self.fallback.run(agent, input_data, ctx)
        payload = {
            "input": input_data,
            "params": ctx.params,
            "prior_outputs": ctx.nodes_outputs,
            "node_id": ctx.node_id,
        }
        result = self.runtime.run(
            name,
            {"text": json.dumps(payload, ensure_ascii=False, default=str)},
            RuntimeContext(session_id=ctx.run_id, actor_id="platform"),
            model_override=_heal_model_override(input_data, ctx),
        )
        return AgentResult(
            success=result.success,
            output=dict(result.output or {}),
            error=result.error,
            tool_calls=list(result.tool_calls or []),
            usage=dict(result.usage or {}),
        )


class HybridAgentRunner:
    """deliver 用 AgentRunner。

    - provider!=mock 且能创建 LLM（如 DEEPSEEK_API_KEY）→ 八 Agent 全走 AgentRuntime
    - 否则 Coding/Debug 走 stub 写文件，其余走 Mock / Testing/Ship(C)
    """

    def __init__(
        self,
        config: AgentConfig,
        *,
        registry: ToolRegistry | None = None,
        fallback: AgentRunner | None = None,
        llm: LLMAdapter | None = None,
        force_llm: bool = False,
    ) -> None:
        self.config = config
        self.registry = registry or ToolRegistry(config)
        self.fallback: AgentRunner = fallback or MockAgentRunner(config.workspace_path())
        self._llm_override = llm
        self._force_llm = force_llm
        self._runtime: AgentRuntime | None = None
        self._runtime_project_mode: bool | None = None
        if self.llm_enabled:
            self._runtime = self._build_runtime(project_mode=False)

    @property
    def llm_enabled(self) -> bool:
        if self._force_llm and self._resolve_llm() is not None:
            return True
        if self.config.llm.provider.lower() == "mock":
            return False
        return self._resolve_llm() is not None

    def _resolve_llm(self) -> LLMAdapter | None:
        if self._llm_override is not None:
            return self._llm_override
        return create_llm_adapter(self.config)

    def _build_runtime(self, *, project_mode: bool = False) -> AgentRuntime:
        runtime = AgentRuntime(
            self.config,
            llm=self._resolve_llm(),
            registry=self.registry,
        )
        for spec in build_deliver_specs(
            model=self.config.llm.model,
            models=dict(self.config.agents.models or {}),
            project_mode=project_mode,
        ):
            runtime.register(spec)
        self._runtime_project_mode = project_mode
        return runtime

    def _ensure_runtime(self, *, project_mode: bool) -> AgentRuntime:
        if (
            self._runtime is None
            or self._runtime_project_mode != project_mode
        ):
            self._runtime = self._build_runtime(project_mode=project_mode)
        return self._runtime

    def run(
        self,
        agent: str,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        name = (agent or "").strip().lower()
        project_mode = bool(ctx.params.get("project_mode"))
        has_metric = bool(
            input_data.get("metric_command")
            or ctx.params.get("metric_command")
            or input_data.get("verify_command")
            or ctx.params.get("verify_command")
            or project_mode
        )
        # 有 metric / project_mode：强制真实验收，禁止 LLM 编造 pass
        if name == "testing" and has_metric:
            return self._run_real_testing(input_data, ctx)
        # 无冒烟命令：走确定性演示逻辑（pass_on_attempt），避免 LLM+工具挂死
        if name == "testing":
            return self.fallback.run(agent, input_data, ctx)
        # 大项目：按 planner 任务循环 Coding 子运行
        if name == "coding" and project_mode:
            return self._run_coding_project_loop(input_data, ctx)
        # 大项目：Testing 失败后 Debug 必须带着失败上下文真修代码
        if name == "debug" and project_mode:
            return self._run_project_debug_repair(input_data, ctx)
        if self.llm_enabled and name in DELIVER_AGENTS:
            self._ensure_runtime(project_mode=project_mode)
            return self._run_llm_agent(name, input_data, ctx)
        if name == "coding":
            return self._run_coding(input_data, ctx)
        if name == "frontend":
            if ctx.params.get("project_mode"):
                return self._run_frontend_project_stub(input_data, ctx)
            return self.fallback.run(agent, input_data, ctx)
        if name == "debug":
            return self._run_debug(input_data, ctx)
        return self.fallback.run(agent, input_data, ctx)

    def _run_real_testing(
        self,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        from mawp.runtime.project_deliver import ensure_project_metric
        from mawp.runtime.testing_agent import run_testing_agent

        workspace = self.config.workspace_path()
        ensure_project_metric(workspace, ctx.params, write_acceptance=True)
        payload = dict(input_data)
        metric = (
            payload.get("metric_command")
            or ctx.params.get("metric_command")
            or payload.get("verify_command")
            or ctx.params.get("verify_command")
        )
        if metric:
            payload["metric_command"] = str(metric).strip()
        try:
            output = run_testing_agent(payload, ctx, workspace=workspace)
            passed = bool(output.get("passed"))
            # 节点本身执行成功，把 passed 留给 YAML check_test 分支；
            # success=False 会让引擎在走到 debug 之前就整次 FAILED。
            return AgentResult(
                success=True,
                output=output,
                error=None if passed else str(output.get("log_summary") or "smoke failed"),
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResult(success=False, error=f"testing failed: {exc}")

    def _run_coding_project_loop(
        self,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        """按 planner 任务逐个 Coding；有 LLM 则子运行，无 LLM 走多文件 stub。"""
        from mawp.runtime.project_deliver import (
            ensure_project_metric,
            extract_tasks_from_ctx,
        )

        ensure_project_metric(
            self.config.workspace_path(), ctx.params, write_acceptance=True
        )
        goal = str(ctx.params.get("goal") or input_data.get("goal") or "feature")
        tasks = extract_tasks_from_ctx(
            input_data, ctx.nodes_outputs, goal=goal, params=ctx.params
        )
        max_tasks = max(1, min(int(ctx.params.get("coding_max_tasks") or 5), 12))
        tasks = tasks[:max_tasks]

        from mawp.runtime.cost_ledger import merge_usage
        from mawp.runtime.task_split import (
            plan_coding_resume,
            prior_coding_output,
            should_retry_coding_task,
        )

        prior = prior_coding_output(input_data, ctx.nodes_outputs)
        resume = plan_coding_resume(
            tasks,
            prior,
            rerun_all=bool(
                ctx.params.get("rerun_all_tasks") or input_data.get("rerun_all_tasks")
            ),
        )
        pending = list(resume["pending"])
        skipped_n = len(resume["skipped"])

        if not self.llm_enabled:
            # stub：无待跑项时直接带回上次成功结果，不重写文件
            if resume["resumed"] and not pending:
                return self._apply_assembly_gate(
                    AgentResult(
                        success=True,
                        output={
                            "status": "ok",
                            "changed_files": list(resume["carried_changed_files"]),
                            "tasks_done": list(resume["carried_done"]),
                            "task_runs": list(resume["carried_task_runs"]),
                            "api_contract": (input_data.get("api_contract") or {}),
                            "project_root": ctx.params.get("project_root"),
                            "mode": "project_stub_loop",
                            "resumed": True,
                            "skipped_tasks": skipped_n,
                        },
                    ),
                    ctx,
                )
            stub_tasks = pending or tasks
            result = self._run_coding_project_stub(goal, stub_tasks, input_data, ctx)
            if result.success and isinstance(result.output, dict):
                new_runs = [
                    {
                        "task_id": t.get("id"),
                        "title": t.get("title"),
                        "status": "stub_batch",
                        "success": True,
                        "changed_files": list(result.output.get("changed_files") or []),
                    }
                    for t in stub_tasks
                ]
                carried = list(resume["carried_task_runs"])
                # 去掉同 id 的旧失败记录，再接上本次 stub
                pending_ids = {str(t.get("id") or "") for t in stub_tasks}
                carried = [
                    r
                    for r in carried
                    if str(r.get("task_id") or "") not in pending_ids
                ]
                all_files = list(resume["carried_changed_files"])
                for p in result.output.get("changed_files") or []:
                    if p not in all_files:
                        all_files.append(p)
                result.output["changed_files"] = all_files
                result.output["task_runs"] = carried + new_runs
                result.output["tasks_done"] = list(resume["carried_done"]) + [
                    str(t.get("id") or "") for t in stub_tasks if t.get("id")
                ]
                result.output["mode"] = "project_stub_loop"
                if resume["resumed"]:
                    result.output["resumed"] = True
                    result.output["skipped_tasks"] = skipped_n
            return self._apply_assembly_gate(result, ctx)

        all_changed: list[str] = list(resume["carried_changed_files"])
        all_tool_calls: list[dict[str, Any]] = []
        tasks_done: list[str] = list(resume["carried_done"])
        task_runs: list[dict[str, Any]] = list(resume["carried_task_runs"])
        last_error: str | None = None
        usage_acc: dict[str, Any] = {}
        total_n = len(tasks)

        for i, task in enumerate(pending):
            focused = {
                "current_task": task,
                "task_index": skipped_n + i + 1,
                "tasks_total": total_n,
                "already_changed_files": list(all_changed),
                "api_contract": input_data.get("api_contract")
                or prior.get("api_contract"),
                "instruction": (
                    f"只实现当前任务 [{task.get('id')}] {task.get('title')}: "
                    f"{task.get('description') or task.get('detail') or ''}。"
                    "用 write_files 写入 project_root；不要重做已完成文件。"
                ),
            }
            focused_ctx = AgentRunContext(
                run_id=ctx.run_id,
                params={
                    **ctx.params,
                    "current_task_id": task.get("id"),
                    "current_task_title": task.get("title"),
                    "compact_coding": True,
                },
                nodes_outputs=ctx.nodes_outputs,
                node_id=ctx.node_id,
            )
            attempt = 1
            sub = self._run_coding_subtask(focused, focused_ctx)
            while (
                not sub.success
                and should_retry_coding_task(sub.error, attempt)
            ):
                attempt += 1
                sub = self._run_coding_subtask(focused, focused_ctx)
            changed = list((sub.output or {}).get("changed_files") or [])
            for p in changed:
                if p not in all_changed:
                    all_changed.append(p)
            all_tool_calls.extend(list(sub.tool_calls or []))
            usage_acc = merge_usage(usage_acc, getattr(sub, "usage", None))
            tid = str(task.get("id") or f"T{skipped_n + i + 1}")
            run_meta = {
                "task_id": tid,
                "title": task.get("title"),
                "success": sub.success,
                "changed_files": changed,
                "error": sub.error,
                "attempts": attempt,
            }
            task_runs.append(run_meta)
            if sub.success:
                tasks_done.append(tid)
            else:
                last_error = sub.error or f"task {tid} failed"
                # 继续后续任务，尽量交付更多增量

        resume_meta = {
            "resumed": bool(resume["resumed"]),
            "skipped_tasks": skipped_n,
        }

        if not tasks_done and last_error:
            return self._apply_assembly_gate(
                AgentResult(
                    success=False,
                    error=last_error,
                    output={
                        "status": "fail",
                        "changed_files": all_changed,
                        "tasks_done": [],
                        "task_runs": task_runs,
                        "mode": "project_task_loop",
                        **resume_meta,
                    },
                    tool_calls=all_tool_calls,
                    usage=usage_acc,
                ),
                ctx,
            )

        # 无待跑项且已全部跳过成功 → 视为续跑完成
        if not pending and resume["resumed"]:
            return self._apply_assembly_gate(
                AgentResult(
                    success=True,
                    output={
                        "status": "ok",
                        "changed_files": all_changed,
                        "tasks_done": tasks_done,
                        "task_runs": task_runs,
                        "api_contract": (input_data.get("api_contract") or prior.get("api_contract") or {}),
                        "project_root": ctx.params.get("project_root"),
                        "mode": "project_task_loop",
                        **resume_meta,
                    },
                    usage=usage_acc,
                ),
                ctx,
            )

        return self._apply_assembly_gate(
            AgentResult(
                success=True,
                output={
                    "status": "ok",
                    "changed_files": all_changed,
                    "tasks_done": tasks_done,
                    "task_runs": task_runs,
                    "api_contract": (
                        input_data.get("api_contract")
                        or prior.get("api_contract")
                        or {}
                    ),
                    "project_root": ctx.params.get("project_root"),
                    "mode": "project_task_loop",
                    **resume_meta,
                },
                tool_calls=all_tool_calls,
                usage=usage_acc,
            ),
            ctx,
        )

    def _run_coding_subtask(
        self,
        focused: dict[str, Any],
        focused_ctx: AgentRunContext,
    ) -> AgentResult:
        try:
            return self._run_llm_agent("coding", focused, focused_ctx)
        except Exception as exc:  # noqa: BLE001
            return AgentResult(success=False, error=str(exc), output={})

    def _apply_assembly_gate(
        self,
        result: AgentResult,
        ctx: AgentRunContext,
    ) -> AgentResult:
        """coding/debug 之后扫描 routers/ 补挂 main.py。不新增工作流节点。"""
        if not ctx.params.get("project_mode"):
            return result
        root = str(ctx.params.get("project_root") or "").replace("\\", "/").rstrip("/")
        if not root:
            return result
        from mawp.runtime.assembly_gate import assemble_project

        report = assemble_project(self.config.workspace_path(), root)
        output = dict(result.output or {})
        output["assembly"] = report.to_dict()
        changed = list(output.get("changed_files") or [])
        if report.mounted:
            main_rel = f"{root}/apps/api/main.py"
            if main_rel not in changed:
                changed.append(main_rel)
        if report.linked_pages:
            index_rel = f"{root}/apps/web/index.html"
            if index_rel not in changed:
                changed.append(index_rel)

        from mawp.runtime.data_layer_gate import assemble_data_layer

        data_report = assemble_data_layer(
            self.config.workspace_path(),
            root,
            phase_id=str(ctx.params.get("phase_id") or "") or None,
        )
        output["data_layer"] = data_report.to_dict()
        for rel in data_report.scaffolded:
            full = f"{root}/{rel}" if not rel.startswith(root) else rel
            if full not in changed:
                changed.append(full)
        if report.mounted or report.linked_pages or data_report.scaffolded:
            output["changed_files"] = changed
        return AgentResult(
            success=result.success,
            output=output,
            error=result.error,
            tool_calls=list(result.tool_calls or []),
            usage=dict(result.usage or {}),
        )

    def _run_llm_agent(
        self,
        name: str,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        runtime = self._ensure_runtime(project_mode=bool(ctx.params.get("project_mode")))
        if name == "coding" and ctx.params.get("project_mode"):
            from mawp.runtime.task_split import compact_coding_payload

            payload = compact_coding_payload(
                input_data=input_data,
                params=ctx.params,
                prior_outputs=ctx.nodes_outputs,
                task=input_data.get("current_task")
                if isinstance(input_data.get("current_task"), dict)
                else None,
            )
            payload["node_id"] = ctx.node_id
            payload["run_id"] = ctx.run_id
        else:
            payload = {
                "input": input_data,
                "params": ctx.params,
                "prior_outputs": ctx.nodes_outputs,
                "node_id": ctx.node_id,
                "run_id": ctx.run_id,
            }
            if ctx.params.get("project_mode"):
                payload["project_constraints"] = {
                    "project_root": ctx.params.get("project_root"),
                    "frontend_dir": ctx.params.get("frontend_dir"),
                    "phase_id": ctx.params.get("phase_id"),
                    "srs_excerpt_chars": len(str(ctx.params.get("srs_excerpt") or "")),
                    "rule": "只在 project_root 下写代码；禁止修改平台源码",
                }
        result = runtime.run(
            name,
            {"text": json.dumps(payload, ensure_ascii=False, default=str)},
            RuntimeContext(session_id=ctx.run_id, actor_id="platform"),
            model_override=_heal_model_override(input_data, ctx),
        )
        if not result.success:
            return AgentResult(
                success=False,
                output=dict(result.output or {}),
                error=result.error,
                tool_calls=list(result.tool_calls or []),
                usage=dict(result.usage or {}),
            )
        output = self._normalize_output(name, dict(result.output or {}), input_data, ctx)
        return AgentResult(
            success=True,
            output=output,
            tool_calls=list(result.tool_calls or []),
            usage=dict(result.usage or {}),
        )

    def _normalize_output(
        self,
        name: str,
        output: dict[str, Any],
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> dict[str, Any]:
        """补齐冻结键，并应用演示 params 覆盖（pass_on_attempt / review_status）。"""
        if "text" in output and len(output) == 1:
            # 未能解析 JSON 时，回退 Mock 以保证工作流不崩
            fallback = self.fallback.run(name, input_data, ctx)
            return dict(fallback.output or {})

        if name == "planner":
            tasks = output.get("tasks")
            if not isinstance(tasks, list):
                tasks = (input_data.get("tasks") or []) if isinstance(
                    input_data.get("tasks"), list
                ) else []
            output.setdefault("status", "ok")
            output["tasks"] = tasks
            output["count"] = len(tasks)
        elif name == "requirement":
            output.setdefault("status", "ok")
            output.setdefault("summary", str(ctx.params.get("goal") or ""))
            output.setdefault("tasks", (ctx.nodes_outputs.get("planner") or {}).get("tasks") or [])
            output.setdefault("ui_key_points", [])
            output.setdefault("acceptance_criteria", [])
        elif name == "coding":
            output.setdefault("status", "ok")
            output.setdefault("changed_files", [])
            output.setdefault("tasks_done", [])
        elif name == "frontend":
            output.setdefault("status", "ok")
            output.setdefault(
                "frontend_dir",
                str(input_data.get("frontend_dir") or "frontend"),
            )
            pages = output.get("pages") if isinstance(output.get("pages"), list) else []
            output["pages"] = pages
            if "artifacts" not in output:
                output["artifacts"] = [
                    p.get("path") for p in pages if isinstance(p, dict) and p.get("path")
                ]
        elif name == "testing":
            output = self._normalize_testing(output, input_data, ctx)
        elif name == "debug":
            output.setdefault("status", "ok")
            output.setdefault("fixed", True)
            prev = ctx.nodes_outputs.get("testing") or {}
            output.setdefault(
                "based_on_failures",
                list(prev.get("failures") or input_data.get("failures") or []),
            )
            output.setdefault("note", str(input_data.get("note") or "llm debug"))
        elif name == "review":
            output = self._normalize_review(output, input_data, ctx)
        elif name == "ship":
            output.setdefault("status", "ok")
            output.setdefault(
                "delivery_notes",
                str(input_data.get("delivery_notes") or "LLM ship notes"),
            )
            output["auto_push"] = False
            output["auto_merge"] = False
        return output

    def _normalize_testing(
        self,
        output: dict[str, Any],
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> dict[str, Any]:
        # 演示契约：无 metric_command 时按 pass_on_attempt 决定 passed
        attempt = int(output.get("attempt") or 0)
        if attempt <= 0:
            prev = ctx.nodes_outputs.get(ctx.node_id) or {}
            attempt = int(prev.get("attempt") or 0) + 1
        metric = (
            input_data.get("metric_command")
            or ctx.params.get("metric_command")
            or input_data.get("verify_command")
            or ctx.params.get("verify_command")
        )
        project_mode = bool(ctx.params.get("project_mode"))
        # project_mode / 有 metric：禁止用 LLM 编造的 passed 覆盖真实验收
        if metric or project_mode:
            ran_smoke = "metric_command" in output or "exit_code" in output
            if not ran_smoke:
                output["passed"] = False
                output["status"] = "fail"
                output.setdefault(
                    "failures",
                    ["project_mode requires executed smoke (metric_command)"],
                )
                output.setdefault(
                    "log_summary",
                    "refusing demo/LLM pass: smoke was not executed",
                )
            else:
                output["passed"] = bool(output.get("passed"))
                output["status"] = "pass" if output.get("passed") else "fail"
                output.setdefault("failures", [])
                output.setdefault("log_summary", "")
            output["attempt"] = attempt
            return output
        target = int(ctx.params.get("pass_on_attempt") or 1)
        force = ctx.params.get("force_test_status")
        if force == "pass":
            passed = True
        elif force == "fail":
            passed = False
        else:
            passed = attempt >= target
        output["passed"] = passed
        output["status"] = "pass" if passed else "fail"
        output.setdefault(
            "failures",
            [] if passed else [f"simulated fail before attempt {target}"],
        )
        output.setdefault(
            "log_summary",
            f"LLM testing attempt={attempt} passed={passed}",
        )
        output["attempt"] = attempt
        return output

    def _normalize_review(
        self,
        output: dict[str, Any],
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> dict[str, Any]:
        status = str(
            ctx.params.get("review_status")
            or output.get("status")
            or input_data.get("status")
            or "pass"
        ).lower()
        if status not in ("pass", "blocking"):
            status = "pass"
        findings = list(output.get("findings") or input_data.get("findings") or [])
        if status == "blocking" and not findings:
            findings = [
                {
                    "level": "blocking",
                    "file": "src/app.py",
                    "message": "review_status=blocking",
                }
            ]
        blocking_count = sum(
            1
            for f in findings
            if isinstance(f, dict) and str(f.get("level", "")).lower() == "blocking"
        )
        if status == "blocking" and blocking_count == 0:
            blocking_count = 1
        if status == "pass":
            blocking_count = 0
        return {
            "status": status,
            "blocking_count": blocking_count,
            "findings": findings,
        }

    def _call_ctx(self, agent_name: str, run_id: str) -> ToolCallContext:
        return ToolCallContext(
            agent_name=agent_name,
            session_id=run_id,
            actor_id="platform",
        )

    def _run_coding(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> AgentResult:
        tasks = (
            (ctx.nodes_outputs.get("planner") or {}).get("tasks")
            or (ctx.nodes_outputs.get("requirement") or {}).get("tasks")
            or input_data.get("tasks")
            or []
        )
        goal = str(ctx.params.get("goal") or input_data.get("goal") or "feature")

        if ctx.params.get("project_mode"):
            return self._run_coding_project_stub(goal, tasks, input_data, ctx)

        rel_path = str(input_data.get("target_path") or "src/mawp_coding_stub.py")
        content = (
            '"""Generated by Coding Agent (HybridAgentRunner)."""\n'
            f"GOAL = {goal!r}\n"
            f"TASKS = {[t.get('id') for t in tasks if isinstance(t, dict)]!r}\n"
        )
        tool = self.registry.execute(
            "write_file",
            {"path": rel_path, "content": content},
            self._call_ctx("coding", ctx.run_id),
        )
        if not tool.success:
            return AgentResult(success=False, error=tool.error or "coding write failed")

        changed = list(input_data.get("changed_files") or [rel_path])
        if rel_path not in changed:
            changed = [rel_path, *changed]
        api_contract = input_data.get("api_contract") or {
            "endpoints": [{"method": "GET", "path": "/health", "note": "stub"}],
        }
        return AgentResult(
            success=True,
            output={
                "status": "ok",
                "changed_files": changed,
                "tasks_done": [t.get("id") for t in tasks if isinstance(t, dict)],
                "api_contract": api_contract,
            },
            tool_calls=[
                {
                    "name": "write_file",
                    "success": True,
                    "path": rel_path,
                    "duration_ms": tool.duration_ms,
                }
            ],
        )

    def _run_coding_project_stub(
        self,
        goal: str,
        tasks: list[Any],
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        """无 LLM 时的大项目兜底：在 project_root 下写多文件骨架。"""
        root = str(
            ctx.params.get("project_root")
            or input_data.get("project_root")
            or "workspaces/stub-project"
        ).replace("\\", "/").rstrip("/")
        title = str(ctx.params.get("project_title") or goal)[:80]
        api_main = f"{root}/apps/api/main.py"
        req = f"{root}/apps/api/requirements.txt"
        readme = f"{root}/apps/api/README.md"
        files = [
            {
                "path": api_main,
                "content": (
                    '"""Project-mode coding stub (no LLM)."""\n'
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI(title=" + repr(title) + ")\n\n"
                    "@app.get('/health')\n"
                    "def health():\n"
                    "    return {'ok': True, 'goal': " + repr(goal[:200]) + "}\n"
                ),
            },
            {
                "path": req,
                "content": "fastapi>=0.110\nuvicorn>=0.27\n",
            },
            {
                "path": readme,
                "content": (
                    f"# {title}\n\n"
                    f"Goal: {goal}\n\n"
                    "```bash\npip install -r requirements.txt\n"
                    "uvicorn main:app --reload --port 8001\n```\n"
                ),
            },
        ]
        tool = self.registry.execute(
            "write_files",
            {"files": files},
            self._call_ctx("coding", ctx.run_id),
        )
        if not tool.success:
            return AgentResult(success=False, error=tool.error or "project stub write failed")
        paths = [f["path"] for f in files]
        return AgentResult(
            success=True,
            output={
                "status": "ok",
                "changed_files": paths,
                "tasks_done": [t.get("id") for t in tasks if isinstance(t, dict)],
                "api_contract": {
                    "endpoints": [
                        {"method": "GET", "path": "/health", "note": "project stub"},
                    ]
                },
                "project_root": root,
                "mode": "project_stub",
            },
            tool_calls=[
                {
                    "name": "write_files",
                    "success": True,
                    "paths": paths,
                    "duration_ms": tool.duration_ms,
                }
            ],
        )

    def _run_frontend_project_stub(
        self,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        root = str(ctx.params.get("project_root") or "workspaces/stub-project").replace(
            "\\", "/"
        ).rstrip("/")
        frontend_dir = str(
            ctx.params.get("frontend_dir")
            or input_data.get("frontend_dir")
            or f"{root}/apps/web"
        ).replace("\\", "/").rstrip("/")
        title = str(ctx.params.get("project_title") or ctx.params.get("goal") or "项目")[:60]
        index_path = f"{frontend_dir}/index.html"
        app_path = f"{frontend_dir}/app.js"
        files = web_asset_files(frontend_dir) + [
            {"path": index_path, "content": health_probe_html(title)},
            {"path": app_path, "content": HEALTH_PROBE_JS},
        ]
        tool = self.registry.execute(
            "write_files",
            {"files": files},
            self._call_ctx("frontend", ctx.run_id),
        )
        if not tool.success:
            return AgentResult(success=False, error=tool.error or "frontend stub failed")
        paths = [f["path"] for f in files]
        return AgentResult(
            success=True,
            output={
                "status": "ok",
                "frontend_dir": frontend_dir,
                "pages": [{"path": index_path, "title": title}],
                "artifacts": paths,
                "ui_key_points": ["health probe page"],
                "mode": "project_stub",
            },
            tool_calls=[
                {
                    "name": "write_files",
                    "success": True,
                    "paths": paths,
                    "duration_ms": tool.duration_ms,
                }
            ],
        )

    def _run_debug(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> AgentResult:
        prev = ctx.nodes_outputs.get("testing") or {}
        failures = list(prev.get("failures") or input_data.get("failures") or [])
        note = str(input_data.get("note") or "hybrid debug applied")
        rel_path = str(input_data.get("fix_path") or "src/.mawp_debug_fix")
        body = (
            "# Debug Agent fix marker\n"
            f"# note: {note}\n"
            f"# failures: {failures!r}\n"
        )
        tool = self.registry.execute(
            "write_file",
            {"path": rel_path, "content": body},
            self._call_ctx("debug", ctx.run_id),
        )
        if not tool.success:
            return AgentResult(success=False, error=tool.error or "debug write failed")

        return AgentResult(
            success=True,
            output={
                "status": "ok",
                "fixed": True,
                "based_on_failures": failures,
                "note": note,
                "changed_files": [rel_path],
            },
            tool_calls=[
                {
                    "name": "write_file",
                    "success": True,
                    "path": rel_path,
                    "duration_ms": tool.duration_ms,
                }
            ],
        )

    def _run_project_debug_repair(
        self,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        """project_mode：把 testing 失败上下文回投到 Coding/Frontend 修复，并验证。"""
        from mawp.runtime.error_classifier import is_unfixable_debug_failure
        from mawp.runtime.project_deliver import ensure_project_metric

        ensure_project_metric(
            self.config.workspace_path(), ctx.params, write_acceptance=True
        )
        testing = ctx.nodes_outputs.get("testing") or {}
        failures = list(
            input_data.get("failures")
            or testing.get("failures")
            or []
        )
        log_summary = str(
            input_data.get("log_summary") or testing.get("log_summary") or ""
        )
        blob = "\n".join(str(x) for x in failures) + "\n" + log_summary
        metric = str(
            testing.get("metric_command") or ctx.params.get("metric_command") or ""
        )
        root = str(ctx.params.get("project_root") or "").replace("\\", "/").rstrip("/")
        coding_out = ctx.nodes_outputs.get("coding") or {}
        prior_files = list(coding_out.get("changed_files") or [])

        if is_unfixable_debug_failure(blob):
            return AgentResult(
                success=True,
                output={
                    "status": "unfixable",
                    "fixed": False,
                    "based_on_failures": failures,
                    "note": "不可修错误（余额/密钥/LLM 超时），跳过 Debug",
                    "changed_files": prior_files,
                    "mode": "project_debug_repair",
                    "repair_source": "none",
                },
                tool_calls=[],
            )

        # 检查是否已达最大重试次数
        attempt = int(testing.get("attempt") or 0)
        max_attempts = int(ctx.params.get("debug_max_attempts") or 2)
        if attempt >= max_attempts:
            return AgentResult(
                success=True,
                output={
                    "status": "max_attempts_reached",
                    "fixed": False,
                    "based_on_failures": failures,
                    "note": f"已达到最大修复次数 {max_attempts}，停止重试",
                    "changed_files": prior_files,
                    "mode": "project_debug_repair",
                    "repair_source": "none",
                },
                tool_calls=[],
            )

        if self.llm_enabled:
            repair_input = {
                **input_data,
                "repair": True,
                "failures": failures,
                "log_summary": log_summary,
                "metric_command": metric,
                "already_changed_files": prior_files,
                "instruction": (
                    "【修复回合】上一轮 Testing 未通过。"
                    f" metric=`{metric}`；failures={failures!r}；"
                    f"log={log_summary[:500]}。"
                    f"请只在 `{root}` 下用 write_files/edit_file 修复，"
                    "优先恢复 apps/api 与 apps/web 可冒烟通过；不要改平台源码。"
                ),
            }
            repair_ctx = AgentRunContext(
                run_id=ctx.run_id,
                params={**ctx.params, "repair_mode": True},
                nodes_outputs=ctx.nodes_outputs,
                node_id=ctx.node_id,
            )
            # Coding 工具链更强：用 coding 修，再包装成 debug 输出
            coding = self._run_llm_agent("coding", repair_input, repair_ctx)
            changed = list((coding.output or {}).get("changed_files") or [])
            # 前端入口缺失时再补一轮 frontend
            frontend_files: list[str] = []
            need_web = any(
                "web" in str(f).lower() or "index.html" in str(f).lower()
                for f in (failures + [log_summary])
            ) or not any("apps/web" in p.replace("\\", "/") for p in (changed + prior_files))
            if coding.success and need_web:
                fe = self._run_llm_agent(
                    "frontend",
                    {
                        "frontend_dir": ctx.params.get("frontend_dir"),
                        "instruction": (
                            "配合修复回合：确保 frontend_dir 有可打开的入口页，"
                            "复用 shell.css + shell.js + theme.css（侧栏后台壳），禁止裸链接列表；"
                            f"对齐 API。failures={failures!r}"
                        ),
                    },
                    repair_ctx,
                )
                frontend_files = list((fe.output or {}).get("artifacts") or [])
                if fe.tool_calls:
                    coding.tool_calls = list(coding.tool_calls or []) + list(fe.tool_calls)

            if not coding.success and not changed:
                # LLM 修失败：降级 stub 修复，避免回环空转
                stub = self._run_debug_project_stub_repair(
                    failures, log_summary, input_data, ctx
                )
                return self._apply_assembly_gate(stub, ctx)

            all_changed = []
            for p in changed + frontend_files:
                if p not in all_changed:
                    all_changed.append(p)
            return self._apply_assembly_gate(
                AgentResult(
                    success=True,
                    output={
                        "status": "ok",
                        "fixed": True,
                        "based_on_failures": failures,
                        "note": f"project repair via coding; log={log_summary[:200]}",
                        "changed_files": all_changed,
                        "mode": "project_debug_repair",
                        "repair_source": "llm",
                    },
                    tool_calls=list(coding.tool_calls or []),
                ),
                ctx,
            )

        return self._apply_assembly_gate(
            self._run_debug_project_stub_repair(
                failures, log_summary, input_data, ctx
            ),
            ctx,
        )

    def _classify_debug_failure(self, failures: list[Any], log_summary: str) -> str:
        """把失败信息粗分类，便于选择更精准的修复策略。"""
        text = " ".join(str(f) for f in failures) + " " + log_summary
        low = text.lower()
        if any(k in low for k in ["syntaxerror", "indentationerror", "parse error", "unexpected indent", "invalid syntax", "syntax "]):
            return "syntax"
        if any(k in low for k in ["modulenotfounderror", "no module named", "cannot import name", "importerror"]):
            return "dependency"
        if any(k in low for k in ["module not found", "package not found", "npm err", "pnpm err", "yarn err", "package.json"]):
            return "dependency"
        if any(k in low for k in ["build failed", "vite", "webpack", "tsc", "esbuild", "rollup", "compile error"]):
            return "build"
        if any(
            k in low
            for k in (
                "404",
                "route",
                "unmounted",
                "include_router",
                "fastapi",
                "path operation",
                "endpoint",
                "not found",
                "placeholder",
                "acceptance",
            )
        ):
            return "route"
        if any(k in low for k in ["assert", "expected", "received", "test failed", "failed:"]):
            return "test"
        if any(k in low for k in ["permission denied", "eacces", "eperm"]):
            return "permission"
        return "unknown"

    def _run_debug_project_stub_repair(
        self,
        failures: list[Any],
        log_summary: str,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        """无 LLM：按冒烟失败症状重建 api/web 关键文件。"""
        root = str(
            ctx.params.get("project_root") or "workspaces/stub-project"
        ).replace("\\", "/").rstrip("/")
        title = str(ctx.params.get("project_title") or ctx.params.get("goal") or "项目")[
            :60
        ]
        frontend_dir = str(
            ctx.params.get("frontend_dir") or f"{root}/apps/web"
        ).replace("\\", "/").rstrip("/")

        fail_type = self._classify_debug_failure(failures, log_summary)
        fail_text = " ".join(str(f) for f in failures) + " " + log_summary
        files: list[dict[str, str]] = []

        # 1) 语法类错误：优先修 main / app 入口
        if fail_type == "syntax":
            files.append(
                {
                    "path": f"{root}/apps/api/main.py",
                    "content": (
                        '"""Repaired by Debug Agent (syntax fix)."""\n'
                        "from fastapi import FastAPI\n\n"
                        f"app = FastAPI(title={title!r})\n\n"
                        "@app.get('/health')\n"
                        "def health():\n"
                        "    return {'ok': True, 'repaired': True, 'mode': 'syntax'}\n\n"
                        "@app.get('/api/repairs')\n"
                        "def repairs():\n"
                        "    return {'items': [], 'total': 0}\n"
                    ),
                }
            )
            files.append(
                {
                    "path": f"{frontend_dir}/index.html",
                    "content": repair_note_html(title, "Syntax repair page"),
                }
            )
            files.append(
                {
                    "path": f"{frontend_dir}/app.js",
                    "content": "console.log('syntax repair');\n",
                }
            )

        # 2) 依赖类错误：补依赖文件
        elif fail_type == "dependency":
            files.append(
                {
                    "path": f"{root}/apps/api/requirements.txt",
                    "content": "fastapi>=0.110\nuvicorn>=0.27\nhttpx>=0.27\npytest>=8.0\n",
                }
            )
            files.append(
                {
                    "path": f"{frontend_dir}/package.json",
                    "content": (
                        '{\n'
                        f'  "name": {title!r},\n'
                        '  "private": true,\n'
                        '  "type": "module",\n'
                        '  "scripts": {\n'
                        '    "dev": "vite",\n'
                        '    "build": "vite build"\n'
                        '  }\n'
                        '}\n'
                    ),
                }
            )

        # 3) 路由类错误：优先补健康检查/关键 API 路由
        elif fail_type == "route":
            files.append(
                {
                    "path": f"{root}/apps/api/main.py",
                    "content": (
                        '"""Repaired by Debug Agent (route fix)."""\n'
                        "from fastapi import FastAPI\n\n"
                        f"app = FastAPI(title={title!r})\n\n"
                        "@app.get('/health')\n"
                        "def health():\n"
                        "    return {'ok': True, 'repaired': True, 'mode': 'route'}\n\n"
                        "@app.get('/api/health')\n"
                        "def api_health():\n"
                        "    return {'ok': True, 'route': 'api_health'}\n\n"
                        "@app.get('/api/repairs')\n"
                        "def repairs():\n"
                        "    return {'items': [], 'total': 0}\n"
                    ),
                }
            )

        # 4) 构建错误：优先修前端入口和构建脚本
        elif fail_type == "build":
            files.append(
                {
                    "path": f"{frontend_dir}/index.html",
                    "content": repair_note_html(title, "Build repair page"),
                }
            )
            files.append(
                {
                    "path": f"{frontend_dir}/app.js",
                    "content": "document.getElementById('app').innerHTML += '<p>build repaired</p>'\n",
                }
            )
            files.append(
                {
                    "path": f"{frontend_dir}/package.json",
                    "content": (
                        '{\n'
                        f'  "name": {title!r},\n'
                        '  "private": true,\n'
                        '  "type": "module",\n'
                        '  "scripts": {\n'
                        '    "dev": "vite",\n'
                        '    "build": "vite build"\n'
                        '  }\n'
                        '}\n'
                    ),
                }
            )

        # 5) 测试类错误：优先补测试需要的 fixture / smoke 页面
        elif fail_type == "test":
            files.append(
                {
                    "path": f"{root}/docs/DEBUG_REPAIR.md",
                    "content": (
                        f"# Debug repair\n\n"
                        f"- failure type: test\n"
                        f"- failures: {failures!r}\n"
                        f"- log: {log_summary}\n"
                    ),
                }
            )
            files.append(
                {
                    "path": f"{frontend_dir}/index.html",
                    "content": repair_note_html(title, "Test repair page"),
                }
            )
            files.append(
                {
                    "path": f"{frontend_dir}/app.js",
                    "content": "console.log('test repair');\n",
                }
            )

        # 6) 默认：尽量同时修 API 与前端
        else:
            files.append(
                {
                    "path": f"{root}/apps/api/main.py",
                    "content": (
                        '"""Repaired by Debug Agent (project stub)."""\n'
                        "from fastapi import FastAPI\n\n"
                        f"app = FastAPI(title={title!r})\n\n"
                        "@app.get('/health')\n"
                        "def health():\n"
                        "    return {'ok': True, 'repaired': True}\n\n"
                        "@app.get('/api/repairs')\n"
                        "def repairs():\n"
                        "    return {'items': [], 'total': 0}\n"
                    ),
                }
            )
            files.append(
                {
                    "path": f"{root}/apps/api/requirements.txt",
                    "content": "fastapi>=0.110\nuvicorn>=0.27\n",
                }
            )
            files.append(
                {
                    "path": f"{frontend_dir}/index.html",
                    "content": repair_note_html(title, "Debug repair page"),
                }
            )
            files.append(
                {
                    "path": f"{frontend_dir}/app.js",
                    "content": "console.log('debug repair');\n",
                }
            )

        # 记录失败上下文，便于人工审计
        note_path = f"{root}/docs/DEBUG_REPAIR.md"
        files.append(
            {
                "path": note_path,
                "content": (
                    f"# Debug repair\n\n"
                    f"- failure type: {fail_type}\n"
                    f"- failures: {failures!r}\n"
                    f"- log: {log_summary}\n"
                ),
            }
        )

        # 凡写出 index.html 时一并写入侧栏壳 + Civic Trust 内容皮肤
        if any(f.get("path", "").endswith("/index.html") or f.get("path", "").endswith("index.html") for f in files):
            existing = {str(f.get("path") or "") for f in files}
            for asset in reversed(web_asset_files(frontend_dir)):
                if asset["path"] not in existing:
                    files.insert(0, asset)

        if not files:
            return self._run_debug(input_data, ctx)

        tool = self.registry.execute(
            "write_files",
            {"files": files},
            self._call_ctx("debug", ctx.run_id),
        )
        if not tool.success:
            return AgentResult(success=False, error=tool.error or "debug repair failed")
        paths = [f["path"] for f in files]
        return AgentResult(
            success=True,
            output={
                "status": "ok",
                "fixed": True,
                "based_on_failures": failures,
                "note": "project stub repair from testing failures",
                "changed_files": paths,
                "mode": "project_debug_repair",
                "repair_source": "stub",
            },
            tool_calls=[
                {
                    "name": "write_files",
                    "success": True,
                    "paths": paths,
                    "duration_ms": tool.duration_ms,
                }
            ],
        )
