from __future__ import annotations

import time
from typing import Any

from mawp.agents.coding import CodingAgent, CodingAgentContext
from mawp.agents.requirement import RequirementSpec
from mawp.autoresearch.git_ops import GitOps
from mawp.autoresearch.models import IterationRecord, IterationStatus, LoopResult, ProgramConfig
from mawp.autoresearch.reports import summarize_diff, write_blocked_report
from mawp.autoresearch.store import AutoresearchStore
from mawp.autoresearch.verifier import WorkspaceSnapshot, run_metric_command
from mawp.config.loader import AgentConfig
from mawp.autoresearch.utils import valid_scope_files
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.deps import assert_ready_for_goal
from mawp.goal.store import GoalStore
from mawp.goal.transitions import (
    transition_after_goal_blocked,
    transition_after_goal_success,
)
from mawp.llm.factory import create_llm_adapter
from mawp.rag.service import RAGService
from mawp.tools.registry import ToolRegistry


class ResumeNotAvailableError(ValueError):
    """无可恢复的 autoresearch checkpoint。"""


class AutoresearchLoop:
    """modify → verify → keep/discard 自主迭代循环。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.workspace = config.workspace_path()
        self.store = AutoresearchStore(config)
        self.goal_store = GoalStore(config)
        self.tools = ToolRegistry(config)
        self.git = GitOps(self.workspace)

    def can_resume(self, issue_id: str) -> bool:
        return self.store.get_resume_context(issue_id) is not None

    def resume_for_issue(
        self,
        issue_id: str,
        program: ProgramConfig | None = None,
    ) -> LoopResult:
        if not self.can_resume(issue_id):
            raise ResumeNotAvailableError(
                f"Issue {issue_id} 无可恢复 checkpoint，请先运行 agent research 或 agent goal"
            )
        issue = self.goal_store.load_issue(issue_id)
        if program is None:
            from mawp.autoresearch.program import ProgramService

            program, _ = ProgramService(self.config).from_issue(issue)
        return self.run_for_issue(issue, program, resume=True)

    def run_for_issue(
        self,
        issue: IssueDocument,
        program: ProgramConfig,
        *,
        allow_done_rework: bool = False,
        resume: bool = False,
    ) -> LoopResult:
        self.store.ensure_layout()

        records: list[IterationRecord] = []
        total_tokens = 0
        last_coding_output: dict[str, Any] = {}
        feedback: dict[str, Any] = {}
        start_iteration = 1

        if resume:
            ctx = self.store.get_resume_context(issue.id)
            if ctx is None:
                raise ResumeNotAvailableError(
                    f"Issue {issue.id} 无可恢复 checkpoint"
                )
            start_iteration = int(ctx.get("next_iteration") or 1)
            total_tokens = int(ctx.get("total_tokens") or 0)
            feedback = dict(ctx.get("feedback") or {})
            issue = self.goal_store.load_issue(issue.id)
            records = _records_from_jsonl(
                self.store.load_results(issue_id=issue.id)
            )
            issue.status = IssueStatus.IN_PROGRESS
            self.goal_store.save_issue(issue)
        else:
            assert_ready_for_goal(
                issue,
                self.goal_store,
                allow_done_rework=allow_done_rework,
            )
            issue.status = IssueStatus.IN_PROGRESS
            self.goal_store.save_issue(issue)

        scope = valid_scope_files(program.scope_files)
        deny = list(program.deny_files)

        baseline_git = self.git.snapshot()

        llm = create_llm_adapter(self.config)
        coding_agent = CodingAgent(self.config, self.tools, llm=llm)

        for iteration in range(start_iteration, program.max_iterations + 1):
            if total_tokens >= program.token_budget:
                return self._blocked(
                    issue,
                    program,
                    records,
                    f"已达 token 预算上限 ({program.token_budget})",
                )

            iter_git_head = baseline_git.head_sha if baseline_git.available else ""
            snapshot = WorkspaceSnapshot.capture(
                self.workspace,
                valid_scope_files(program.scope_files),
            )

            requirement_spec = _issue_to_requirement_spec(issue)
            rag_chunks = _load_rag_chunks(self.config, issue.description)

            ctx = CodingAgentContext(
                session_id=f"ar-{issue.id}",
                user_description=_build_task_prompt(issue, program, feedback),
                workspace=self.workspace,
                requirement_spec=requirement_spec,
                design_summary={
                    "scope_files": program.scope_files,
                    "acceptance_criteria": issue.acceptance_criteria,
                    "verify_command": program.metric_command,
                },
                retry_feedback=feedback,
                rag_chunks=rag_chunks,
                scope_files=scope,
                deny_files=deny if deny else None,
            )

            coding_result = coding_agent.run(ctx)
            total_tokens += coding_result.tokens_used
            if not coding_result.success:
                record = self._record_discard(
                    issue_id=issue.id,
                    iteration=iteration,
                    program=program,
                    verify={"passed": False, "exit_code": -1, "stderr": coding_result.error or ""},
                    tokens=coding_result.tokens_used,
                    error_summary=coding_result.error or "编码失败",
                )
                records.append(record)
                self.store.append_result(record.model_dump())
                self._discard(baseline_git, snapshot, iter_git_head)
                feedback = {
                    "kind": "coding_error",
                    "message": coding_result.error or "编码 Agent 失败",
                }
                self._save_running_checkpoint(
                    issue.id, iteration, total_tokens, feedback
                )
                continue

            last_coding_output = coding_result.output or {}
            changed_files = list(last_coding_output.get("files_changed") or [])
            for path in changed_files:
                snapshot.merge_paths([path], self.workspace)

            verify = run_metric_command(
                workspace=self.workspace,
                command=program.metric_command,
                timeout_seconds=self.config.agents.testing.timeout_seconds,
            )

            if verify["passed"]:
                commit_sha = self._keep(
                    baseline_git,
                    issue.id,
                    iteration,
                    changed_files,
                )
                record = IterationRecord(
                    iteration=iteration,
                    issue_id=issue.id,
                    status=IterationStatus.KEEP,
                    metric_command=program.metric_command,
                    exit_code=verify["exit_code"],
                    passed=True,
                    duration_ms=verify["duration_ms"],
                    commit_sha=commit_sha,
                    tokens_used=coding_result.tokens_used,
                    files_changed=changed_files,
                    diff_summary=summarize_diff(changed_files),
                )
                records.append(record)
                self.store.append_result(record.model_dump())
                issue.status = transition_after_goal_success(issue)
                self.goal_store.save_issue(issue)
                self.store.save_state(
                    {
                        "issue_id": issue.id,
                        "status": "done",
                        "passed_at": iteration,
                        "commit_sha": commit_sha,
                    }
                )
                return LoopResult(
                    success=True,
                    issue_id=issue.id,
                    iterations=iteration,
                    passed_at=iteration,
                    commit_sha=commit_sha,
                    records=records,
                    coding_output=last_coding_output,
                )

            record = self._record_discard(
                issue_id=issue.id,
                iteration=iteration,
                program=program,
                verify=verify,
                tokens=coding_result.tokens_used,
                error_summary=_summarize_verify_failure(verify),
                files_changed=changed_files,
            )
            records.append(record)
            self.store.append_result(record.model_dump())
            self._discard(baseline_git, snapshot, iter_git_head)
            feedback = {
                "kind": "test_failure",
                "exit_code": verify["exit_code"],
                "stdout": (verify.get("stdout") or "")[-4000:],
                "stderr": (verify.get("stderr") or "")[-4000:],
                "command": program.metric_command,
            }
            self._save_running_checkpoint(
                issue.id, iteration, total_tokens, feedback
            )

        return self._blocked(
            issue,
            program,
            records,
            f"已达最大迭代次数 ({program.max_iterations})",
            coding_output=last_coding_output,
        )

    def _keep(
        self,
        baseline_git,
        issue_id: str,
        iteration: int,
        changed_files: list[str],
    ) -> str:
        if baseline_git.available and self.config.autoresearch.auto_commit_on_keep:
            if self.git.has_changes():
                self.git.add_all()
                return self.git.commit(
                    f"autoresearch: {issue_id} iter {iteration} PASS"
                )
            return self.git.get_head()
        return ""

    def _discard(
        self,
        baseline_git,
        snapshot: WorkspaceSnapshot,
        iter_git_head: str,
    ) -> None:
        if baseline_git.available and iter_git_head:
            self.git.reset_hard(iter_git_head)
        else:
            snapshot.restore()

    def _save_running_checkpoint(
        self,
        issue_id: str,
        iteration: int,
        total_tokens: int,
        feedback: dict[str, Any],
    ) -> None:
        self.store.save_running_checkpoint(
            issue_id=issue_id,
            next_iteration=iteration + 1,
            total_tokens=total_tokens,
            feedback=feedback,
            iterations_completed=iteration,
        )

    def _record_discard(
        self,
        *,
        issue_id: str,
        iteration: int,
        program: ProgramConfig,
        verify: dict,
        tokens: int,
        error_summary: str,
        files_changed: list[str] | None = None,
    ) -> IterationRecord:
        changed = files_changed or []
        return IterationRecord(
            iteration=iteration,
            issue_id=issue_id,
            status=IterationStatus.DISCARD,
            metric_command=program.metric_command,
            exit_code=int(verify.get("exit_code", 1)),
            passed=False,
            duration_ms=int(verify.get("duration_ms", 0)),
            error_summary=error_summary,
            tokens_used=tokens,
            files_changed=changed,
            diff_summary=summarize_diff(changed),
        )

    def _blocked(
        self,
        issue: IssueDocument,
        program: ProgramConfig,
        records: list[IterationRecord],
        reason: str,
        *,
        coding_output: dict | None = None,
    ) -> LoopResult:
        issue.status = transition_after_goal_blocked(issue)
        self.goal_store.save_issue(issue)
        report_path = write_blocked_report(
            self.config,
            issue,
            program,
            reason=reason,
            records=records,
        )
        self.store.save_state(
            {
                "issue_id": issue.id,
                "status": "blocked",
                "reason": reason,
                "iterations": len(records),
                "blocked_report": str(report_path),
            }
        )
        return LoopResult(
            success=False,
            issue_id=issue.id,
            iterations=len(records),
            blocked_reason=reason,
            blocked_report_path=str(report_path),
            records=records,
            coding_output=coding_output or {},
        )


def _records_from_jsonl(rows: list[dict]) -> list[IterationRecord]:
    records: list[IterationRecord] = []
    for row in rows:
        status = row.get("status", "discard")
        records.append(
            IterationRecord(
                iteration=int(row.get("iteration") or 0),
                issue_id=str(row.get("issue_id") or ""),
                status=IterationStatus(status),
                metric_command=str(row.get("metric_command") or ""),
                exit_code=int(row.get("exit_code") or 1),
                passed=bool(row.get("passed")),
                duration_ms=int(row.get("duration_ms") or 0),
                commit_sha=str(row.get("commit_sha") or ""),
                error_summary=str(row.get("error_summary") or ""),
                tokens_used=int(row.get("tokens_used") or 0),
                files_changed=list(row.get("files_changed") or []),
                diff_summary=str(row.get("diff_summary") or ""),
            )
        )
    return records


def _issue_to_requirement_spec(issue: IssueDocument) -> dict:
    spec = RequirementSpec(
        summary=issue.title,
        goals=[issue.description],
        acceptance_criteria=issue.acceptance_criteria
        or ["实现 Issue 描述的功能", "验证命令通过"],
        related_files=issue.scope_files,
        open_questions=[],
        tasks=[],
    )
    return spec.model_dump()


def _build_task_prompt(
    issue: IssueDocument,
    program: ProgramConfig,
    feedback: dict,
) -> str:
    parts = [
        f"实现 Issue {issue.id}: {issue.title}",
        issue.description,
        f"验证命令必须通过: {program.metric_command}",
    ]
    if program.scope_files:
        parts.append("允许修改的文件: " + ", ".join(program.scope_files))
    if feedback:
        parts.append("上一轮失败反馈: " + str(feedback.get("stderr") or feedback.get("message") or feedback))
    return "\n\n".join(parts)


def _summarize_verify_failure(verify: dict) -> str:
    stderr = (verify.get("stderr") or "").strip()
    stdout = (verify.get("stdout") or "").strip()
    snippet = stderr or stdout
    if len(snippet) > 500:
        snippet = snippet[:500] + "..."
    return snippet or f"验证失败 exit_code={verify.get('exit_code')}"


def _load_rag_chunks(config: AgentConfig, query: str) -> list[dict]:
    try:
        rag = RAGService(config)
        if rag.is_indexed():
            return [chunk.to_dict() for chunk in rag.retrieve_chunks(query)]
    except Exception:
        pass
    return []
