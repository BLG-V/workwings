from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from mawp.config.loader import AgentConfig
from mawp.gstack.pipeline import ReviewPipeline
from mawp.gstack.store import ReviewStore
from mawp.goal.approve import ApproveService
from mawp.goal.delivery import (
    count_autoresearch_iterations,
    generate_commit_message,
    generate_pr_body,
    generate_ship_summary,
)
from mawp.goal.models import IssueStatus
from mawp.goal.store import GoalStore
from mawp.goal.transitions import transition_after_ship


class ShipService:
    """Goal Workflow ⑥ 交付：归档 Issue 与审查 artifacts。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.goal_store = GoalStore(config)
        self.pipeline = ReviewPipeline(config)
        self.approve = ApproveService(config)
        self.review_store = ReviewStore(config)

    def ship(self, issue_id: str) -> tuple[Path, str]:
        ok, reason = self.pipeline.can_ship(issue_id)
        if not ok:
            raise PermissionError(reason)

        self.approve.assert_valid(issue_id)

        issue = self.goal_store.load_issue(issue_id)
        slug = _resolve_slug(issue)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        archive_name = f"{ts}-{slug}-{issue_id.lower()}"
        archive_dir = (
            self.config.workspace_path()
            / self.config.goal_workflow.base_path
            / "archive"
            / archive_name
        )
        archive_dir.mkdir(parents=True, exist_ok=True)

        review_report = self.review_store.load(issue_id, "review")
        qa_report = self.review_store.load(issue_id, "qa")
        iterations = count_autoresearch_iterations(self.config, issue_id)

        _copy_issue(self.goal_store, issue_id, archive_dir)
        _copy_reviews(self.config, issue_id, slug, archive_dir)
        _copy_autoresearch_artifacts(self.config, issue_id, archive_dir)
        _copy_goal_docs(self.goal_store, issue, archive_dir)
        _copy_approve_record(self.approve, issue_id, archive_dir)

        (archive_dir / "COMMIT_MSG.txt").write_text(
            generate_commit_message(issue),
            encoding="utf-8",
        )
        (archive_dir / "PR.md").write_text(
            generate_pr_body(
                issue,
                review_report=review_report,
                qa_report=qa_report,
            ),
            encoding="utf-8",
        )

        summary = generate_ship_summary(
            issue,
            archive_dir.name,
            review_report=review_report,
            qa_report=qa_report,
            iterations=iterations or None,
        )
        (archive_dir / "SHIP.md").write_text(summary, encoding="utf-8")

        issue.status = transition_after_ship(issue)
        self.goal_store.save_issue(issue)

        return archive_dir, summary


def _resolve_slug(issue) -> str:
    for ref in (issue.prd_ref, issue.spec_ref, issue.id):
        if ref and ref not in {"—", "-"}:
            return ref
    return issue.id.lower()


def _copy_issue(goal_store: GoalStore, issue_id: str, archive_dir: Path) -> None:
    issue_path = goal_store.paths.issue_path(issue_id)
    if issue_path.is_file():
        shutil.copy2(issue_path, archive_dir / issue_path.name)


def _copy_reviews(config: AgentConfig, issue_id: str, slug: str, archive_dir: Path) -> None:
    workspace = config.workspace_path()
    reviews_base = workspace / ".mawp" / "reviews"
    for key in (issue_id, slug):
        if key in {"—", "-"}:
            continue
        src = reviews_base / key
        if src.is_dir():
            dest = archive_dir / "reviews" if key == issue_id else archive_dir / f"reviews-{key}"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)


def _copy_autoresearch_artifacts(
    config: AgentConfig,
    issue_id: str,
    archive_dir: Path,
) -> None:
    workspace = config.workspace_path()
    ar_base = workspace / ".autoresearch"

    program = ar_base / "program.md"
    if program.is_file():
        shutil.copy2(program, archive_dir / "program.md")

    results_rel = config.autoresearch.results_path
    results = (
        workspace / results_rel
        if not Path(results_rel).is_absolute()
        else Path(results_rel)
    )
    if results.is_file():
        shutil.copy2(results, archive_dir / "results.jsonl")

    from mawp.autoresearch.reports import blocked_report_path

    blocked = blocked_report_path(config, issue_id)
    if blocked.is_file():
        shutil.copy2(blocked, archive_dir / blocked.name)


def _copy_goal_docs(goal_store: GoalStore, issue, archive_dir: Path) -> None:
    docs_dir = archive_dir / "goal-docs"
    docs_dir.mkdir(exist_ok=True)
    for ref, label in ((issue.prd_ref, "prd"), (issue.spec_ref, "spec")):
        if not ref or ref in {"—", "-"}:
            continue
        if label == "prd":
            path = goal_store.paths.prd_path(ref)
        else:
            path = goal_store.paths.spec_path(ref)
        if path.is_file():
            shutil.copy2(path, docs_dir / f"{label}-{ref}.md")


def _copy_approve_record(approve: ApproveService, issue_id: str, archive_dir: Path) -> None:
    record = approve.load(issue_id)
    if record is None:
        return
    import json

    (archive_dir / "approve.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
