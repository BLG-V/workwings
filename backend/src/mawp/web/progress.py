from __future__ import annotations

from mawp.autoresearch.store import AutoresearchStore
from mawp.config.loader import AgentConfig
from mawp.goal.approve import ApproveService
from mawp.goal.loop import GoalLoopService
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore
from mawp.gstack.models import ReviewStatus
from mawp.gstack.store import ReviewStore
from mawp.web.models import (
    IssueProgress,
    LoopCheckpoint,
    StepStatus,
    WorkflowDetail,
    WorkflowStep,
    WorkflowSummary,
)

STEP_LABELS = {
    "prd": "① 规划 PRD",
    "spec": "② 设计 SPEC",
    "issues": "③ 拆解 Issues",
    "goal": "④ 实现 Goal",
    "review": "⑤ 审查 Review",
    "ship": "⑥ 交付 Ship",
}


class WorkflowProgressService:
    """聚合 .goal / .autoresearch / .agent/reviews 进度。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.goal_store = GoalStore(config)
        self.review_store = ReviewStore(config)
        self.ar_store = AutoresearchStore(config)
        self.approve = ApproveService(config)
        self.loop_service = GoalLoopService(config)

    def list_workflows(self) -> list[WorkflowSummary]:
        summaries: list[WorkflowSummary] = []
        for slug in self._list_prd_slugs():
            try:
                detail = self.get_workflow(slug)
            except FileNotFoundError:
                continue
            summaries.append(self._to_summary(detail))
        return summaries

    def get_workflow(self, slug: str) -> WorkflowDetail:
        prd = self.goal_store.load_prd(slug)
        issues = [i for i in self.goal_store.list_issues() if i.prd_ref == slug]
        archived, archive_path = self._find_archive(slug)

        spec_exists = self.goal_store.spec_exists(slug)
        eng_status = self._eng_review_status(slug)

        steps = self._build_steps(
            slug=slug,
            spec_exists=spec_exists,
            issues=issues,
            archived=archived,
            eng_status=eng_status,
        )
        issue_progress = [self._issue_progress(issue) for issue in issues]
        loop_checkpoint = self._loop_checkpoint(slug)
        reviewed_count = sum(1 for i in issues if i.status == IssueStatus.REVIEWED)
        approved_count = sum(
            1 for i in issues if self.approve.is_valid(i.id)[0]
        )

        return WorkflowDetail(
            slug=slug,
            title=prd.title,
            description=prd.description,
            steps=steps,
            issues=issue_progress,
            eng_review_status=eng_status,
            archived=archived,
            archive_path=archive_path,
            loop_checkpoint=loop_checkpoint,
            approved_count=approved_count,
            reviewed_count=reviewed_count,
        )

    def get_issue(self, issue_id: str) -> dict:
        issue = self.goal_store.load_issue(issue_id)
        progress = self._issue_progress(issue)
        review = self.review_store.load(issue_id, "review")
        qa = self.review_store.load(issue_id, "qa")
        iterations = self.ar_store.load_results(issue_id=issue_id)
        state = self.ar_store.load_state()
        return {
            "issue": progress.model_dump(),
            "description": issue.description,
            "acceptance_criteria": issue.acceptance_criteria,
            "scope_files": issue.scope_files,
            "depends_on": issue.depends_on,
            "review": review.to_yaml_dict() if review else None,
            "qa": qa.to_yaml_dict() if qa else None,
            "iterations": iterations,
            "autoresearch_state": state if state.get("issue_id") == issue_id else {},
        }

    def list_all_issues(self) -> list[IssueProgress]:
        return [self._issue_progress(issue) for issue in self.goal_store.list_issues()]

    def _build_steps(
        self,
        *,
        slug: str,
        spec_exists: bool,
        issues: list[IssueDocument],
        archived: bool,
        eng_status: str | None,
    ) -> list[WorkflowStep]:
        prd_done = self.goal_store.prd_exists(slug)
        spec_done = spec_exists
        issues_done = len(issues) > 0

        goal_status, goal_detail = self._goal_step_status(issues)
        review_status, review_detail = self._review_step_status(issues)
        ship_status, ship_detail = self._ship_step_status(
            issues,
            archived=archived,
        )

        if archived:
            spec_status = StepStatus.DONE
            issues_status = StepStatus.DONE
        else:
            spec_status = self._spec_step_status(spec_exists, eng_status)
            issues_status = (
                StepStatus.DONE
                if issues_done
                else (StepStatus.IN_PROGRESS if spec_done else StepStatus.PENDING)
            )

        return [
            WorkflowStep(
                key="prd",
                label=STEP_LABELS["prd"],
                status=StepStatus.DONE if prd_done else StepStatus.PENDING,
                detail=slug,
            ),
            WorkflowStep(
                key="spec",
                label=STEP_LABELS["spec"],
                status=spec_status,
                detail=eng_status or ("已完成" if spec_done else "待生成"),
            ),
            WorkflowStep(
                key="issues",
                label=STEP_LABELS["issues"],
                status=issues_status,
                detail=f"{len(issues)} 张卡片",
            ),
            WorkflowStep(
                key="goal",
                label=STEP_LABELS["goal"],
                status=goal_status,
                detail=goal_detail,
            ),
            WorkflowStep(
                key="review",
                label=STEP_LABELS["review"],
                status=review_status,
                detail=review_detail,
            ),
            WorkflowStep(
                key="ship",
                label=STEP_LABELS["ship"],
                status=ship_status,
                detail=ship_detail,
            ),
        ]

    def _spec_step_status(
        self, spec_exists: bool, eng_status: str | None
    ) -> StepStatus:
        if not spec_exists:
            return StepStatus.PENDING
        if eng_status == "BLOCKED":
            return StepStatus.BLOCKED
        return StepStatus.DONE

    def _goal_step_status(
        self, issues: list[IssueDocument]
    ) -> tuple[StepStatus, str]:
        if not issues:
            return StepStatus.PENDING, "无 Issue"
        blocked = [i for i in issues if i.status == IssueStatus.BLOCKED]
        if blocked:
            return StepStatus.BLOCKED, f"{len(blocked)} 个 blocked"
        in_progress = [
            i
            for i in issues
            if i.status in (IssueStatus.OPEN, IssueStatus.IN_PROGRESS)
        ]
        done = [
            i
            for i in issues
            if i.status in (IssueStatus.DONE, IssueStatus.REVIEWED)
        ]
        if in_progress:
            return StepStatus.IN_PROGRESS, f"{len(done)}/{len(issues)} 完成"
        if len(done) == len(issues):
            return StepStatus.DONE, "全部完成"
        return StepStatus.PENDING, f"{len(done)}/{len(issues)} 完成"

    def _review_step_status(
        self, issues: list[IssueDocument]
    ) -> tuple[StepStatus, str]:
        if not issues:
            return StepStatus.PENDING, "—"
        reviewed = [i for i in issues if i.status == IssueStatus.REVIEWED]
        done_not_reviewed = [
            i for i in issues if i.status == IssueStatus.DONE
        ]
        if done_not_reviewed:
            return StepStatus.IN_PROGRESS, f"{len(reviewed)}/{len(issues)} 已审查"
        if len(reviewed) == len(issues):
            return StepStatus.DONE, "全部通过"
        if any(i.status == IssueStatus.BLOCKED for i in issues):
            return StepStatus.BLOCKED, "存在 blocked Issue"
        return StepStatus.PENDING, f"{len(reviewed)}/{len(issues)} 已审查"

    def _ship_step_status(
        self,
        issues: list[IssueDocument],
        *,
        archived: bool,
    ) -> tuple[StepStatus, str]:
        if archived:
            return StepStatus.DONE, "已归档"
        if not issues:
            return StepStatus.PENDING, "等待交付"

        reviewed = [i for i in issues if i.status == IssueStatus.REVIEWED]
        approved = [i for i in reviewed if self.approve.is_valid(i.id)[0]]

        if len(reviewed) == len(issues) and len(approved) == len(issues):
            return StepStatus.IN_PROGRESS, f"待 ship（{len(approved)} 已 approve）"
        if reviewed:
            return (
                StepStatus.IN_PROGRESS,
                f"review 完成 {len(reviewed)}/{len(issues)}，approve {len(approved)}/{len(reviewed)}",
            )
        if any(i.status == IssueStatus.DONE for i in issues):
            return StepStatus.PENDING, "等待 review + approve"
        return StepStatus.PENDING, "等待实现完成"

    def _issue_progress(self, issue: IssueDocument) -> IssueProgress:
        review = self.review_store.load(issue.id, "review")
        qa = self.review_store.load(issue.id, "qa")
        iterations = self.ar_store.load_results(issue_id=issue.id)
        blocking = 0
        if review:
            blocking += review.blocking_count
        if qa:
            blocking += qa.blocking_count
        last_status = iterations[-1].get("status") if iterations else None
        resume_ctx = self.ar_store.get_resume_context(issue.id)
        approved, _ = self.approve.is_valid(issue.id)
        return IssueProgress(
            id=issue.id,
            title=issue.title,
            status=issue.status.value,
            priority=issue.priority,
            verify_command=issue.verify_command,
            review_status=review.status.value if review else None,
            qa_status=qa.status.value if qa else None,
            iteration_count=len(iterations),
            last_iteration_status=last_status,
            blocking_count=blocking,
            resume_available=resume_ctx is not None,
            resume_from_iteration=(
                int(resume_ctx.get("next_iteration"))
                if resume_ctx and resume_ctx.get("next_iteration")
                else None
            ),
            approved=approved,
        )

    def _eng_review_status(self, slug: str) -> str | None:
        report = self.review_store.load(slug, "plan-eng-review")
        return report.status.value if report else None

    def _find_archive(self, slug: str) -> tuple[bool, str | None]:
        archive_dir = self.goal_store.paths.archive_dir
        if not archive_dir.is_dir():
            return False, None
        for path in sorted(archive_dir.iterdir(), reverse=True):
            if slug in path.name:
                return True, str(path)
        return False, None

    def _loop_checkpoint(self, slug: str) -> LoopCheckpoint | None:
        raw = self.loop_service.load_checkpoint(slug)
        if not raw:
            return None
        return LoopCheckpoint(
            slug=slug,
            completed=list(raw.get("completed") or []),
            last_completed=raw.get("last_completed"),
            updated_at=raw.get("updated_at"),
        )

    def _list_prd_slugs(self) -> list[str]:
        prd_dir = self.goal_store.paths.prd_dir
        if not prd_dir.is_dir():
            return []
        return sorted(p.stem for p in prd_dir.glob("*.md"))

    def _to_summary(self, detail: WorkflowDetail) -> WorkflowSummary:
        done_steps = sum(1 for s in detail.steps if s.status == StepStatus.DONE)
        total_steps = len(detail.steps)
        issue_done = sum(
            1
            for i in detail.issues
            if i.status in ("done", "reviewed")
        )
        return WorkflowSummary(
            slug=detail.slug,
            title=detail.title,
            current_step=detail.current_step,
            progress_percent=int(done_steps / total_steps * 100) if total_steps else 0,
            issue_total=len(detail.issues),
            issue_done=issue_done,
            archived=detail.archived,
        )
