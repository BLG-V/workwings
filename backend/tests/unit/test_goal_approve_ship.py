from __future__ import annotations

import pytest

from mawp.config.loader import AgentConfig
from mawp.goal.approve import ApproveError, ApproveService
from mawp.goal.delivery import generate_commit_message, generate_pr_body
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.ship import ShipService
from mawp.goal.store import GoalStore
from mawp.gstack.models import ReviewReport, ReviewStatus
from mawp.gstack.pipeline import ReviewPipeline


def _reviewed_issue_setup(tmp_path, issue_id: str = "GW-021") -> AgentConfig:
    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_KEY"},
        gstack={"auto_fix_blocking": False},
    )
    (tmp_path / "src").mkdir(exist_ok=True)
    verify = tmp_path / "verify.py"
    verify.write_text("raise SystemExit(0)\n", encoding="utf-8")

    goal_store = GoalStore(config)
    goal_store.save_issue(
        IssueDocument(
            id=issue_id,
            title="ship me",
            description="实现 demo 功能",
            status=IssueStatus.DONE,
            verify_command="python verify.py",
            scope_files=["src/demo.py"],
            prd_ref="feat",
            spec_ref="feat",
            acceptance_criteria=["demo 可用"],
        )
    )
    return config


def test_generate_commit_message_includes_issue_id() -> None:
    issue = IssueDocument(
        id="GW-001",
        title="邮箱验证码登录",
        description="实现验证码发送",
        scope_files=["src/auth/login.py"],
        verify_command="pytest -q",
    )
    msg = generate_commit_message(issue)
    assert "GW-001" in msg
    assert "feat(auth)" in msg
    assert "Refs: GW-001" in msg


def test_ship_requires_approve(tmp_path) -> None:
    config = _reviewed_issue_setup(tmp_path)
    ReviewPipeline(config).run("GW-021", auto_fix=False)

    with pytest.raises(ApproveError, match="agent approve"):
        ShipService(config).ship("GW-021")


def test_ship_after_approve(tmp_path) -> None:
    config = _reviewed_issue_setup(tmp_path)
    ReviewPipeline(config).run("GW-021", auto_fix=False)

    ApproveService(config).approve("GW-021")
    archive_dir, _ = ShipService(config).ship("GW-021")

    assert archive_dir.is_dir()
    assert (archive_dir / "GW-021.md").is_file()
    assert (archive_dir / "SHIP.md").is_file()
    assert (archive_dir / "PR.md").is_file()
    assert (archive_dir / "COMMIT_MSG.txt").is_file()
    assert (archive_dir / "approve.json").is_file()
    assert "GW-021" in (archive_dir / "COMMIT_MSG.txt").read_text(encoding="utf-8")


def test_approve_invalidated_after_issue_change(tmp_path) -> None:
    config = _reviewed_issue_setup(tmp_path)
    ReviewPipeline(config).run("GW-021", auto_fix=False)
    approve = ApproveService(config)
    approve.approve("GW-021")

    store = GoalStore(config)
    issue = store.load_issue("GW-021")
    issue.description = "变更后的描述"
    store.save_issue(issue)

    ok, reason = approve.is_valid("GW-021")
    assert ok is False
    assert "重新运行 agent approve" in reason


def test_generate_pr_body_includes_qa() -> None:
    issue = IssueDocument(
        id="GW-002",
        title="t",
        description="desc",
        acceptance_criteria=["标准1"],
    )
    qa = ReviewReport(
        review_id="R1",
        issue_id="GW-002",
        reviewer="qa",
        status=ReviewStatus.PASS,
        summary="QA 通过",
    )
    body = generate_pr_body(issue, review_report=None, qa_report=qa)
    assert "QA: **PASS**" in body
    assert "GW-002" in body
