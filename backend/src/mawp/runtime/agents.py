"""Minimal Agent runtime for engine scheduling (A · deliver skeleton + C Testing/Ship).

B 可后续替换为真 AgentRuntime；Testing/Ship 由 C 落地真实逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class AgentResult:
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRunContext:
    run_id: str
    params: dict[str, Any]
    nodes_outputs: dict[str, dict[str, Any]]
    node_id: str


class AgentRunner(Protocol):
    def run(
        self,
        agent: str,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult: ...


class MockAgentRunner:
    """按 agent 名调度；Testing/Ship 走 C 实现，其余保持 mock。"""

    def __init__(self, workspace: Path | str | None = None):
        self.workspace = Path(workspace).resolve() if workspace else Path.cwd()

    def run(
        self,
        agent: str,
        input_data: dict[str, Any],
        ctx: AgentRunContext,
    ) -> AgentResult:
        name = (agent or "").strip().lower()
        handlers = {
            "planner": self._planner,
            "requirement": self._requirement,
            "coding": self._coding,
            "frontend": self._frontend,
            "debug": self._debug,
            "testing": self._testing,
            "review": self._review,
            "ship": self._ship,
        }
        handler = handlers.get(name)
        if handler is None:
            return AgentResult(
                success=True,
                output={
                    "status": "ok",
                    "agent": name or agent,
                    "echo": input_data,
                },
            )
        try:
            return AgentResult(success=True, output=handler(input_data, ctx))
        except Exception as exc:  # noqa: BLE001 — 边界转失败结果
            return AgentResult(success=False, error=str(exc))

    def _planner(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> dict[str, Any]:
        tasks = input_data.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            tasks = [
                {
                    "id": "T1",
                    "title": str(ctx.params.get("goal") or "implement feature"),
                    "depends_on": [],
                }
            ]
        return {"tasks": tasks, "status": "ok", "count": len(tasks)}

    def _requirement(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> dict[str, Any]:
        # 对接 Planner：优先吃 nodes.planner.outputs.tasks（键名与 A 冻结一致）
        planner_tasks = (ctx.nodes_outputs.get("planner") or {}).get("tasks") or []
        tasks = input_data.get("tasks") if isinstance(input_data.get("tasks"), list) else planner_tasks
        ui_points = input_data.get("ui_key_points")
        if not isinstance(ui_points, list) or not ui_points:
            ui_points = [
                "主页面展示交付状态",
                "Ship 前需人工确认入口",
            ]
        return {
            "status": "ok",
            "summary": str(input_data.get("summary") or ctx.params.get("goal") or ""),
            "spec_ref": str(input_data.get("spec_ref") or "specs/uc08.md"),
            "tasks": tasks,
            "ui_key_points": ui_points,
            "acceptance_criteria": list(
                input_data.get("acceptance_criteria")
                or [
                    "可打开生成页或 mock HTML",
                    "主链跑到 Ship 且无自动 push",
                ]
            ),
        }

    def _coding(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> dict[str, Any]:
        tasks = (
            (ctx.nodes_outputs.get("planner") or {}).get("tasks")
            or (ctx.nodes_outputs.get("requirement") or {}).get("tasks")
            or input_data.get("tasks")
            or []
        )
        return {
            "status": "ok",
            "changed_files": list(input_data.get("changed_files") or ["src/app.py"]),
            "tasks_done": [t.get("id") for t in tasks if isinstance(t, dict)],
        }

    def _frontend(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> dict[str, Any]:
        """生成页 / mock 前端产物（AC-08）；不改动 A 已冻结的其它 Agent outputs 键。"""
        req = ctx.nodes_outputs.get("requirement") or {}
        ui_points = list(req.get("ui_key_points") or input_data.get("ui_key_points") or [])
        out_dir = str(input_data.get("frontend_dir") or "apps/demo-code-agent/frontend")
        pages = list(
            input_data.get("pages")
            or [
                {
                    "path": f"{out_dir}/index.html",
                    "title": "Deliver Status",
                    "mock": True,
                }
            ]
        )
        return {
            "status": "ok",
            "frontend_dir": out_dir,
            "pages": pages,
            "artifacts": [p.get("path") for p in pages if isinstance(p, dict)],
            "ui_key_points": ui_points,
        }

    def _debug(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> dict[str, Any]:
        prev = ctx.nodes_outputs.get("testing") or ctx.nodes_outputs.get("testing_1") or {}
        return {
            "status": "ok",
            "fixed": True,
            "based_on_failures": list(prev.get("failures") or []),
            "note": str(input_data.get("note") or "mock debug applied"),
        }

    def _testing(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> dict[str, Any]:
        from mawp.runtime.testing_agent import run_testing_agent

        return run_testing_agent(input_data, ctx, workspace=self.workspace)

    def _review(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> dict[str, Any]:
        status = str(
            ctx.params.get("review_status")
            or input_data.get("status")
            or "pass"
        ).lower()
        if status not in ("pass", "blocking"):
            status = "pass"
        findings = list(input_data.get("findings") or [])
        if status == "blocking" and not findings:
            findings = [
                {
                    "level": "blocking",
                    "file": "src/app.py",
                    "message": "mock blocking finding",
                }
            ]
        blocking_count = sum(
            1
            for f in findings
            if isinstance(f, dict) and str(f.get("level", "")).lower() == "blocking"
        )
        if status == "blocking" and blocking_count == 0:
            blocking_count = 1
        return {
            "status": status,
            "blocking_count": blocking_count,
            "findings": findings,
        }

    def _ship(
        self, input_data: dict[str, Any], ctx: AgentRunContext
    ) -> dict[str, Any]:
        from mawp.runtime.ship_agent import run_ship_agent

        return run_ship_agent(input_data, ctx, workspace=self.workspace)
