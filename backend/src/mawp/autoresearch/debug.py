from __future__ import annotations

from mawp.autoresearch.loop import AutoresearchLoop
from mawp.autoresearch.models import LoopResult
from mawp.autoresearch.program import ProgramService
from mawp.autoresearch.store import AutoresearchStore
from mawp.autoresearch.verifier import run_metric_command
from mawp.config.loader import AgentConfig
from mawp.goal.store import GoalStore

DEFAULT_DEBUG_ITERATIONS = 15


class ResearchDebugError(ValueError):
    """research debug 无法执行。"""


class ResearchDebugService:
    """测试失败时的假设-验证式调试循环（AR-007）。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.goal_store = GoalStore(config)
        self.program_service = ProgramService(config)
        self.ar_store = AutoresearchStore(config)
        self.loop = AutoresearchLoop(config)

    def _collect_failure_context(self, issue_id: str, metric_command: str) -> str:
        sections: list[str] = []

        logs = self.ar_store.load_results(issue_id=issue_id)
        discard_logs = [row for row in logs if row.get("status") == "discard"]
        if discard_logs:
            last = discard_logs[-1]
            sections.append("### 最近 discard 迭代")
            sections.append(f"- exit_code: {last.get('exit_code')}")
            summary = last.get("error_summary") or last.get("stderr") or ""
            if summary:
                sections.append(f"- 摘要: {str(summary)[:2000]}")

        verify = run_metric_command(
            workspace=self.config.workspace_path(),
            command=metric_command,
            timeout_seconds=self.config.agents.testing.timeout_seconds,
        )
        if not verify["passed"]:
            sections.append("### 当前验证失败输出")
            sections.append(f"- command: `{metric_command}`")
            sections.append(f"- exit_code: {verify.get('exit_code')}")
            stderr = (verify.get("stderr") or "").strip()
            stdout = (verify.get("stdout") or "").strip()
            if stderr:
                sections.append(f"- stderr:\n```\n{stderr[-4000:]}\n```")
            if stdout:
                sections.append(f"- stdout:\n```\n{stdout[-4000:]}\n```")

        if not sections:
            raise ResearchDebugError(
                f"Issue {issue_id} 无可用失败上下文，请先运行 agent goal 或 agent research"
            )

        sections.insert(
            0,
            "请基于以下测试失败信息提出假设、最小修复并验证。每次只改 scope 内必要文件。",
        )
        return "\n".join(sections)

    def run_debug(
        self,
        issue_id: str,
        *,
        max_iterations: int | None = None,
    ) -> LoopResult:
        issue = self.goal_store.load_issue(issue_id)
        program, _ = self.program_service.from_issue(issue)
        failure_context = self._collect_failure_context(issue_id, program.metric_command)

        debug_iterations = max_iterations or DEFAULT_DEBUG_ITERATIONS
        program = program.model_copy(
            update={
                "goal": issue.description + "\n\n## Debug 模式\n" + failure_context,
                "max_iterations": max(
                    debug_iterations,
                    program.max_iterations,
                ),
            }
        )
        return self.loop.run_for_issue(issue, program, allow_done_rework=True)
