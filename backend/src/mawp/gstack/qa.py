from __future__ import annotations

from mawp.autoresearch.verifier import run_metric_command
from mawp.config.loader import AgentConfig
from mawp.gstack.models import Finding, ReviewReport, ReviewStatus
from mawp.gstack.store import ReviewStore, new_review_id
from mawp.goal.models import IssueDocument


class QAService:
    """gstack /qa：运行 Issue 验证命令。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.store = ReviewStore(config)

    def run_qa(self, issue: IssueDocument) -> ReviewReport:
        command = issue.verify_command or "pytest -q"
        verify = run_metric_command(
            workspace=self.config.workspace_path(),
            command=command,
            timeout_seconds=self.config.agents.testing.timeout_seconds,
        )

        findings: list[Finding] = []
        if not verify["passed"]:
            snippet = (verify.get("stderr") or verify.get("stdout") or "")[:500]
            findings.append(
                Finding(
                    severity="blocking",
                    file="*",
                    message=f"QA 验证失败 (exit {verify['exit_code']}): {snippet}",
                    category="qa",
                )
            )

        status = ReviewStatus.PASS if verify["passed"] else ReviewStatus.BLOCKED
        report = ReviewReport(
            review_id=new_review_id(issue.id, "qa"),
            issue_id=issue.id,
            reviewer="qa",
            status=status,
            findings=findings,
            summary=(
                f"QA 通过: {command}"
                if verify["passed"]
                else f"QA 失败: {command}"
            ),
        )
        self.store.save(report)
        return report
