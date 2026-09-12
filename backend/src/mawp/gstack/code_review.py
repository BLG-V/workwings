from __future__ import annotations

from mawp.agents.review_rules import ReviewContext, ReviewRulesAgent
from mawp.config.loader import AgentConfig
from mawp.gstack.context import collect_changed_files, issue_to_requirement_spec
from mawp.gstack.models import Finding, ReviewReport, ReviewStatus
from mawp.gstack.store import ReviewStore, new_review_id
from mawp.goal.models import IssueDocument


class CodeReviewService:
    """gstack /review：规则引擎代码审查。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.store = ReviewStore(config)
        self.rules = ReviewRulesAgent(config)

    def review_issue(
        self,
        issue: IssueDocument,
        *,
        test_report: dict | None = None,
    ) -> ReviewReport:
        files_changed = collect_changed_files(self.config, issue)
        coding_result = {
            "files_changed": files_changed,
            "changelog": issue.description,
        }

        ctx = ReviewContext(
            session_id=f"review-{issue.id}",
            workspace=self.config.workspace_path(),
            requirement_spec=issue_to_requirement_spec(issue),
            coding_result=coding_result,
            test_report=test_report or {},
        )
        result = self.rules.run(ctx)
        raw_issues = list((result.output or {}).get("issues") or [])

        findings = [
            Finding(
                severity=str(item.get("level") or "suggestion"),
                file=str(item.get("file") or "*"),
                line=int(item.get("line") or 0),
                message=str(item.get("message") or ""),
                category=str(item.get("category") or "general"),
                source="rules",
            )
            for item in raw_issues
        ]

        if issue.status.value not in ("done", "reviewed") and not files_changed:
            findings.append(
                Finding(
                    severity="blocking",
                    file="*",
                    message="Issue 尚未完成实现（status 非 done）且无检测到变更文件",
                    category="workflow",
                )
            )

        blocking = sum(1 for f in findings if f.severity == "blocking")
        status = ReviewStatus.PASS if blocking == 0 else ReviewStatus.BLOCKED
        report = ReviewReport(
            review_id=new_review_id(issue.id, "review"),
            issue_id=issue.id,
            reviewer="review",
            status=status,
            findings=findings,
            summary=str((result.output or {}).get("summary") or ""),
        )
        self.store.save(report)
        return report
