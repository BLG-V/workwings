from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from mawp.autoresearch.loop import AutoresearchLoop
from mawp.autoresearch.program import ProgramService
from mawp.config.loader import AgentConfig
from mawp.goal.deps import validate_dag
from mawp.goal.issues import _issues_for_slug
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore


@dataclass
class GoalLoopResult:
    slug: str
    completed: list[str] = field(default_factory=list)
    failed_issue_id: str | None = None
    blocked_reason: str | None = None
    reviewed: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed_issue_id is None


class GoalLoopService:
    """按依赖顺序批量 goal 实现同一 slug 下的 Issue（GW-035）。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.goal_store = GoalStore(config)
        self.program_service = ProgramService(config)
        self.loop = AutoresearchLoop(config)
        self.checkpoint_dir = config.workspace_path() / ".mawp" / "loop"

    def checkpoint_path(self, slug: str) -> Path:
        return self.checkpoint_dir / f"{slug}.json"

    def list_ordered_issues(self, slug: str) -> list[IssueDocument]:
        issues = _issues_for_slug(self.goal_store, slug)
        if not issues:
            raise FileNotFoundError(f"未找到 slug={slug} 的 Issue")
        return validate_dag(issues)

    def load_checkpoint(self, slug: str) -> dict:
        path = self.checkpoint_path(slug)
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_checkpoint(self, slug: str, *, completed: list[str]) -> None:
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "slug": slug,
            "completed": completed,
            "last_completed": completed[-1] if completed else None,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.checkpoint_path(slug).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear_checkpoint(self, slug: str) -> None:
        path = self.checkpoint_path(slug)
        if path.is_file():
            path.unlink()

    def run(
        self,
        slug: str,
        *,
        resume: bool = True,
        run_review: bool = False,
    ) -> GoalLoopResult:
        ordered = self.list_ordered_issues(slug)
        checkpoint = self.load_checkpoint(slug) if resume else {}
        completed = list(checkpoint.get("completed") or [])
        completed_set = set(completed)
        reviewed: list[str] = []

        from mawp.gstack.pipeline import ReviewPipeline

        review_pipeline = ReviewPipeline(self.config) if run_review else None

        for issue in ordered:
            if issue.id in completed_set:
                continue

            issue = self.goal_store.load_issue(issue.id)
            if issue.status in (IssueStatus.DONE, IssueStatus.REVIEWED):
                completed.append(issue.id)
                completed_set.add(issue.id)
                self.save_checkpoint(slug, completed=completed)
                if run_review and issue.status == IssueStatus.REVIEWED:
                    reviewed.append(issue.id)
                continue

            if issue.status == IssueStatus.BLOCKED:
                return GoalLoopResult(
                    slug=slug,
                    completed=completed,
                    failed_issue_id=issue.id,
                    blocked_reason="Issue 已处于 blocked 状态",
                    reviewed=reviewed,
                )

            program, _ = self.program_service.from_issue(issue)
            if self.loop.can_resume(issue.id):
                result = self.loop.resume_for_issue(issue.id, program)
            else:
                result = self.loop.run_for_issue(issue, program)
            if not result.success:
                self.save_checkpoint(slug, completed=completed)
                return GoalLoopResult(
                    slug=slug,
                    completed=completed,
                    failed_issue_id=issue.id,
                    blocked_reason=result.blocked_reason,
                    reviewed=reviewed,
                )

            completed.append(issue.id)
            completed_set.add(issue.id)
            self.save_checkpoint(slug, completed=completed)

            if run_review and review_pipeline is not None:
                review_result = review_pipeline.run(issue.id, auto_fix=False)
                if not review_result.passed:
                    return GoalLoopResult(
                        slug=slug,
                        completed=completed,
                        failed_issue_id=issue.id,
                        blocked_reason="review 未通过",
                        reviewed=reviewed,
                    )
                reviewed.append(issue.id)

        self.clear_checkpoint(slug)
        return GoalLoopResult(
            slug=slug,
            completed=completed,
            reviewed=reviewed,
        )
