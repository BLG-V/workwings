from __future__ import annotations

import pytest

from mawp.config.loader import AgentConfig
from mawp.gstack.eng_review import EngReviewService
from mawp.gstack.models import ReviewStatus
from mawp.gstack.pipeline import ReviewPipeline
from mawp.gstack.qa import QAService
from mawp.gstack.store import ReviewStore
from mawp.goal.models import IssueDocument, IssueStatus, SpecDocument
from mawp.goal.approve import ApproveService
from mawp.goal.ship import ShipService
from mawp.goal.store import GoalStore


def test_eng_review_passes_complete_spec(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    service = EngReviewService(config)
    spec = SpecDocument(
        slug="feat",
        title="功能",
        prd_ref="feat",
        architecture="分层架构",
        testing_strategy="pytest 单元测试",
        implementation_plan=["步骤1", "步骤2"],
        security="JWT 鉴权",
    )
    report = service.review_spec(spec)
    assert report.status == ReviewStatus.PASS
    assert report.blocking_count == 0


def test_eng_review_blocks_empty_spec(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    service = EngReviewService(config)
    spec = SpecDocument(slug="feat", title="功能", prd_ref="feat")
    report = service.review_spec(spec)
    assert report.status == ReviewStatus.BLOCKED
    assert report.blocking_count >= 2


def test_qa_pass_and_fail(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    script = tmp_path / "ok.py"
    script.write_text("print('ok')\n", encoding="utf-8")

    issue_ok = IssueDocument(
        id="GW-001",
        title="ok",
        description="d",
        verify_command='python ok.py',
    )
    issue_bad = IssueDocument(
        id="GW-002",
        title="bad",
        description="d",
        verify_command='python -c "import sys; sys.exit(1)"',
    )

    qa = QAService(config)
    assert qa.run_qa(issue_ok).status == ReviewStatus.PASS
    assert qa.run_qa(issue_bad).status == ReviewStatus.BLOCKED


def test_review_pipeline_marks_reviewed(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_KEY"},
        gstack={"auto_fix_blocking": False},
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "demo.py").write_text("# ok\n", encoding="utf-8")

    verify = tmp_path / "verify.py"
    verify.write_text(
        "from pathlib import Path\n"
        "raise SystemExit(0 if Path('src/demo.py').is_file() else 1)\n",
        encoding="utf-8",
    )

    goal_store = GoalStore(config)
    issue = IssueDocument(
        id="GW-010",
        title="demo",
        description="demo task",
        status=IssueStatus.DONE,
        verify_command="python verify.py",
        scope_files=["src/demo.py"],
    )
    goal_store.save_issue(issue)

    result = ReviewPipeline(config).run("GW-010", auto_fix=False)
    assert result.qa_report.status == ReviewStatus.PASS
    assert result.review_report.status == ReviewStatus.PASS
    assert result.passed is True

    reloaded = goal_store.load_issue("GW-010")
    assert reloaded.status == IssueStatus.REVIEWED


def test_ship_requires_review(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    goal_store = GoalStore(config)
    issue = IssueDocument(
        id="GW-020",
        title="t",
        description="d",
        status=IssueStatus.DONE,
        verify_command="python -c \"pass\"",
    )
    goal_store.save_issue(issue)

    with pytest.raises(PermissionError, match="agent review"):
        ShipService(config).ship("GW-020")


def test_ship_after_review(tmp_path) -> None:
    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_KEY"},
        gstack={"auto_fix_blocking": False},
    )
    (tmp_path / "src").mkdir()
    verify = tmp_path / "verify.py"
    verify.write_text("raise SystemExit(0)\n", encoding="utf-8")

    goal_store = GoalStore(config)
    issue = IssueDocument(
        id="GW-021",
        title="ship me",
        description="d",
        status=IssueStatus.DONE,
        verify_command="python verify.py",
        scope_files=["src/demo.py"],
        prd_ref="feat",
    )
    goal_store.save_issue(issue)

    pipeline = ReviewPipeline(config)
    result = pipeline.run("GW-021", auto_fix=False)
    assert result.passed

    ApproveService(config).approve("GW-021")
    archive_dir, _ = ShipService(config).ship("GW-021")
    assert archive_dir.is_dir()
    assert (archive_dir / "GW-021.md").is_file()
    assert (archive_dir / "SHIP.md").is_file()


def test_review_pipeline_rejects_open_issue(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    goal_store = GoalStore(config)
    goal_store.save_issue(
        IssueDocument(
            id="GW-030",
            title="open",
            description="d",
            status=IssueStatus.OPEN,
            verify_command="python -c \"pass\"",
        )
    )
    from mawp.goal.transitions import InvalidTransitionError

    with pytest.raises(InvalidTransitionError):
        ReviewPipeline(config).run("GW-030", auto_fix=False)


def test_review_store_persists_yaml(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    from mawp.gstack.models import Finding, ReviewReport

    store = ReviewStore(config)
    report = ReviewReport(
        review_id="REV-1",
        issue_id="GW-099",
        reviewer="qa",
        status=ReviewStatus.PASS,
        findings=[],
        summary="ok",
    )
    path = store.save(report)
    assert path.is_file()
    loaded = store.load("GW-099", "qa")
    assert loaded is not None
    assert loaded.status == ReviewStatus.PASS
