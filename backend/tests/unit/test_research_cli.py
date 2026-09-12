from __future__ import annotations

import pytest
from typer.testing import CliRunner

from mawp.autoresearch.fix import ResearchFixError, ResearchFixService
from mawp.config.loader import AgentConfig
from mawp.gstack.models import Finding, ReviewReport, ReviewStatus
from mawp.gstack.store import ReviewStore
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore


def test_research_fix_requires_blocking(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    GoalStore(config).save_issue(
        IssueDocument(
            id="GW-001",
            title="t",
            description="d",
            status=IssueStatus.DONE,
            verify_command="pytest -q",
        )
    )

    with pytest.raises(ResearchFixError, match="blocking"):
        ResearchFixService(config).run_fix("GW-001")


def test_research_fix_runs_with_blocking_findings(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_TEST_KEY"},
        autoresearch={"max_iterations": 2, "auto_commit_on_keep": False},
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "demo.py").write_text("# demo\n", encoding="utf-8")
    (tmp_path / "verify.py").write_text(
        "from pathlib import Path\n"
        "text = Path('src/demo.py').read_text(encoding='utf-8')\n"
        "raise SystemExit(0 if 'agent-generated' in text else 1)\n",
        encoding="utf-8",
    )

    store = GoalStore(config)
    store.save_issue(
        IssueDocument(
            id="GW-002",
            title="fix blocking",
            description="修复 blocking 问题",
            status=IssueStatus.DONE,
            verify_command="python verify.py",
            scope_files=["src/demo.py"],
        )
    )

    review_store = ReviewStore(config)
    review_store.save(
        ReviewReport(
            review_id="R1",
            issue_id="GW-002",
            reviewer="review",
            status=ReviewStatus.BLOCKED,
            findings=[
                Finding(
                    severity="blocking",
                    file="src/demo.py",
                    message="缺少 agent-generated 标记",
                    category="quality",
                )
            ],
            summary="blocking",
        )
    )

    result = ResearchFixService(config).run_fix("GW-002")
    assert result.success is True
    assert "agent-generated" in (tmp_path / "src" / "demo.py").read_text(encoding="utf-8")


def test_cli_research_help_lists_fix(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mawp.config.yaml").write_text(
        "workspace: .\nllm:\n  provider: mock\n",
        encoding="utf-8",
    )

    from mawp.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["research", "--help"])
    assert result.exit_code == 0
    assert "fix" in result.stdout
    assert "debug" in result.stdout
    assert "resume" in result.stdout
    assert "run" in result.stdout
