from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from mawp.config.loader import AgentConfig
from mawp.gstack.models import ReviewReport


class ReviewStore:
    """`.agent/reviews/<issue-id>/` 审查报告存储。"""

    def __init__(self, config: AgentConfig):
        self.base = config.workspace_path() / ".mawp" / "reviews"

    def issue_dir(self, issue_id: str) -> Path:
        return self.base / issue_id

    def save(self, report: ReviewReport) -> Path:
        directory = self.issue_dir(report.issue_id)
        directory.mkdir(parents=True, exist_ok=True)
        name = report.reviewer.replace("/", "-")
        md_path = directory / f"{name}.md"
        md_path.write_text(report.to_markdown(), encoding="utf-8")
        yaml_path = directory / f"{name}.yaml"
        yaml_path.write_text(
            yaml.safe_dump(report.to_yaml_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return md_path

    def load(self, issue_id: str, reviewer: str) -> ReviewReport | None:
        yaml_path = self.issue_dir(issue_id) / f"{reviewer}.yaml"
        if yaml_path.is_file():
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            return _report_from_dict(data)
        md_path = self.issue_dir(issue_id) / f"{reviewer}.md"
        if not md_path.is_file():
            return None
        return None

    def list_reports(self, issue_id: str) -> list[str]:
        directory = self.issue_dir(issue_id)
        if not directory.is_dir():
            return []
        return sorted(p.stem for p in directory.glob("*.yaml"))

    def latest_status(self, issue_id: str) -> str | None:
        """返回最近一次 review+qa 综合状态摘要。"""
        review = self.load(issue_id, "review")
        qa = self.load(issue_id, "qa")
        if review is None and qa is None:
            return None
        if (review and review.status.value == "BLOCKED") or (
            qa and qa.status.value == "BLOCKED"
        ):
            return "BLOCKED"
        if review and qa:
            return "PASS"
        return "PARTIAL"


def new_review_id(issue_id: str, reviewer: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    slug = reviewer.replace("/", "-")
    return f"REV-{issue_id}-{slug}-{ts}"


def _report_from_dict(data: dict) -> ReviewReport:
    from mawp.gstack.models import Finding, ReviewStatus

    findings = [Finding(**item) for item in data.get("findings") or []]
    return ReviewReport(
        review_id=data["review_id"],
        issue_id=data["issue_id"],
        reviewer=data["reviewer"],
        status=ReviewStatus(data["status"]),
        findings=findings,
        summary=data.get("summary") or "",
    )
