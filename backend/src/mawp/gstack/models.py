from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"


class Finding(BaseModel):
    severity: str  # blocking | suggestion | nit
    file: str = "*"
    line: int = 0
    message: str
    category: str = "general"
    source: str = "rules"

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ReviewReport(BaseModel):
    review_id: str
    issue_id: str
    reviewer: str  # plan-eng-review | review | qa
    status: ReviewStatus
    findings: list[Finding] = Field(default_factory=list)
    summary: str = ""

    @property
    def blocking_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "blocking")

    def to_markdown(self) -> str:
        lines = [
            f"# Review: {self.reviewer}",
            "",
            "## 元信息",
            f"- review_id: {self.review_id}",
            f"- issue_id: {self.issue_id}",
            f"- reviewer: {self.reviewer}",
            f"- status: {self.status.value}",
            f"- blocking_count: {self.blocking_count}",
            "",
            "## 摘要",
            self.summary or "—",
            "",
            "## Findings",
        ]
        if not self.findings:
            lines.append("- （无）")
        else:
            for finding in self.findings:
                loc = f"{finding.file}:{finding.line}" if finding.line else finding.file
                lines.append(
                    f"- [{finding.severity}] {loc} — {finding.message} "
                    f"({finding.category})"
                )
        return "\n".join(lines) + "\n"

    def to_yaml_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "issue_id": self.issue_id,
            "reviewer": self.reviewer,
            "status": self.status.value,
            "blocking_count": self.blocking_count,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
        }
