from __future__ import annotations

from mawp.autoresearch.loop import AutoresearchLoop
from mawp.autoresearch.models import LoopResult
from mawp.autoresearch.program import ProgramService
from mawp.config.loader import AgentConfig
from mawp.gstack.models import Finding
from mawp.gstack.store import ReviewStore
from mawp.goal.store import GoalStore


class ResearchFixError(ValueError):
    """research fix 无法执行。"""


class ResearchFixService:
    """针对 gstack blocking 审查意见运行 autoresearch 修复循环（AR-006）。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.goal_store = GoalStore(config)
        self.review_store = ReviewStore(config)
        self.program_service = ProgramService(config)
        self.loop = AutoresearchLoop(config)

    def collect_blocking(self, issue_id: str) -> list[Finding]:
        blocking: list[Finding] = []
        for reviewer in ("review", "qa"):
            report = self.review_store.load(issue_id, reviewer)
            if report is None:
                continue
            blocking.extend(
                finding
                for finding in report.findings
                if finding.severity == "blocking"
            )
        return blocking

    def run_fix(self, issue_id: str) -> LoopResult:
        issue = self.goal_store.load_issue(issue_id)
        blocking = self.collect_blocking(issue_id)
        if not blocking:
            raise ResearchFixError(
                f"Issue {issue_id} 无 blocking 审查项，请先运行 agent review"
            )

        program, _ = self.program_service.from_issue(issue)
        feedback = "\n".join(
            f"- [{finding.severity}] {finding.file}: {finding.message}"
            for finding in blocking[:10]
        )
        program = program.model_copy(
            update={
                "goal": issue.description + f"\n\n修复以下 blocking 问题:\n{feedback}",
                "max_iterations": min(5, program.max_iterations),
            }
        )
        return self.loop.run_for_issue(issue, program, allow_done_rework=True)
