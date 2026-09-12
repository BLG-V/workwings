from __future__ import annotations

from mawp.config.loader import AgentConfig
from mawp.gstack.models import Finding, ReviewReport, ReviewStatus
from mawp.gstack.store import ReviewStore, new_review_id
from mawp.goal.models import SpecDocument


class EngReviewService:
    """gstack plan-eng-review：审查 SPEC 技术方案。"""

    PLACEHOLDER = ("（待补充）", "（无 API 变更或待补充）")

    def __init__(self, config: AgentConfig):
        self.config = config
        self.store = ReviewStore(config)

    def review_spec(self, spec: SpecDocument, *, issue_id: str = "") -> ReviewReport:
        findings: list[Finding] = []
        issue_ref = issue_id or spec.slug

        if not spec.architecture or spec.architecture in self.PLACEHOLDER:
            findings.append(
                Finding(
                    severity="blocking",
                    file=f".goal/spec/{spec.slug}.md",
                    message="架构设计未填写",
                    category="plan",
                )
            )

        if not spec.testing_strategy or spec.testing_strategy in self.PLACEHOLDER:
            findings.append(
                Finding(
                    severity="blocking",
                    file=f".goal/spec/{spec.slug}.md",
                    message="测试策略未填写",
                    category="plan",
                )
            )

        if not spec.implementation_plan:
            findings.append(
                Finding(
                    severity="blocking",
                    file=f".goal/spec/{spec.slug}.md",
                    message="实施计划为空，无法拆解 Issue",
                    category="plan",
                )
            )

        if len(spec.implementation_plan) > 8:
            findings.append(
                Finding(
                    severity="suggestion",
                    file=f".goal/spec/{spec.slug}.md",
                    message=f"实施步骤过多 ({len(spec.implementation_plan)})，建议削减范围",
                    category="scope",
                )
            )

        if not spec.security or spec.security in self.PLACEHOLDER:
            findings.append(
                Finding(
                    severity="suggestion",
                    file=f".goal/spec/{spec.slug}.md",
                    message="安全策略未明确",
                    category="security",
                )
            )

        blocking = sum(1 for f in findings if f.severity == "blocking")
        status = ReviewStatus.PASS if blocking == 0 else ReviewStatus.BLOCKED
        report = ReviewReport(
            review_id=new_review_id(issue_ref, "plan-eng-review"),
            issue_id=issue_ref,
            reviewer="plan-eng-review",
            status=status,
            findings=findings,
            summary=(
                "工程审查通过，可拆解 Issue"
                if status == ReviewStatus.PASS
                else f"工程审查 blocked：{blocking} 项必须修复"
            ),
        )
        self.store.save(report)
        return report
