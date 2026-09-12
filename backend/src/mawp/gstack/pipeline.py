from __future__ import annotations

from dataclasses import dataclass, field

from mawp.autoresearch.loop import AutoresearchLoop
from mawp.autoresearch.models import ProgramConfig
from mawp.autoresearch.program import ProgramService
from mawp.config.loader import AgentConfig
from mawp.gstack.code_review import CodeReviewService
from mawp.gstack.models import Finding, ReviewReport, ReviewStatus
from mawp.gstack.qa import QAService
from mawp.gstack.store import ReviewStore
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore
from mawp.goal.transitions import assert_can_review, transition_after_review_pass


@dataclass
class ReviewPipelineResult:
    issue_id: str
    status: ReviewStatus
    review_report: ReviewReport
    qa_report: ReviewReport
    blocking_findings: list[Finding] = field(default_factory=list)
    fix_attempted: bool = False
    fix_success: bool = False

    @property
    def passed(self) -> bool:
        return self.status == ReviewStatus.PASS


class ReviewPipeline:
    """gstack 审查流水线：review → qa → [optional fix] → re-review。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.goal_store = GoalStore(config)
        self.review_store = ReviewStore(config)
        self.code_review = CodeReviewService(config)
        self.qa = QAService(config)

    def run(
        self,
        issue_id: str,
        *,
        auto_fix: bool | None = None,
    ) -> ReviewPipelineResult:
        issue = self.goal_store.load_issue(issue_id)
        assert_can_review(issue)

        qa_report = self.qa.run_qa(issue)
        review_report = self.code_review.review_issue(
            issue,
            test_report={
                "passed": qa_report.status == ReviewStatus.PASS,
                "skipped": False,
            },
        )

        blocking = [
            f
            for f in [*review_report.findings, *qa_report.findings]
            if f.severity == "blocking"
        ]
        status = ReviewStatus.PASS if not blocking else ReviewStatus.BLOCKED

        should_fix = (
            auto_fix
            if auto_fix is not None
            else self.config.gstack.auto_fix_blocking
        )
        fix_attempted = False
        fix_success = False

        if status == ReviewStatus.BLOCKED and should_fix and blocking:
            fix_attempted = True
            fix_success = self._auto_fix(issue, blocking)
            if fix_success:
                issue = self.goal_store.load_issue(issue_id)
                qa_report = self.qa.run_qa(issue)
                review_report = self.code_review.review_issue(
                    issue,
                    test_report={
                        "passed": qa_report.status == ReviewStatus.PASS,
                        "skipped": False,
                    },
                )
                blocking = [
                    f
                    for f in [*review_report.findings, *qa_report.findings]
                    if f.severity == "blocking"
                ]
                status = ReviewStatus.PASS if not blocking else ReviewStatus.BLOCKED

        if status == ReviewStatus.PASS:
            issue.status = transition_after_review_pass(issue)
            self.goal_store.save_issue(issue)

        return ReviewPipelineResult(
            issue_id=issue_id,
            status=status,
            review_report=review_report,
            qa_report=qa_report,
            blocking_findings=blocking,
            fix_attempted=fix_attempted,
            fix_success=fix_success,
        )

    def _auto_fix(self, issue: IssueDocument, blocking: list[Finding]) -> bool:
        program_service = ProgramService(self.config)
        program, _ = program_service.from_issue(issue)
        feedback = "\n".join(
            f"- [{f.severity}] {f.file}: {f.message}" for f in blocking[:10]
        )
        program = program.model_copy(
            update={
                "goal": issue.description + f"\n\n修复以下 blocking 问题:\n{feedback}",
                "max_iterations": min(5, program.max_iterations),
            }
        )
        loop = AutoresearchLoop(self.config)
        result = loop.run_for_issue(issue, program, allow_done_rework=True)
        return result.success

    def can_ship(self, issue_id: str) -> tuple[bool, str]:
        issue = self.goal_store.load_issue(issue_id)
        if issue.status != IssueStatus.REVIEWED:
            return False, f"Issue 状态为 {issue.status.value}，须先通过 agent review"
        review = self.review_store.load(issue_id, "review")
        qa = self.review_store.load(issue_id, "qa")
        if review is None or qa is None:
            return False, "缺少 review 或 qa 报告，请运行 agent review"
        if review.status != ReviewStatus.PASS or qa.status != ReviewStatus.PASS:
            return False, "审查未通过 (BLOCKED)"
        return True, "ok"
