from __future__ import annotations

import json

import pytest

from mawp.autoresearch.debug import ResearchDebugError, ResearchDebugService
from mawp.autoresearch.store import AutoresearchStore
from mawp.config.loader import AgentConfig
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore

from tests.e2e.conftest import setup_verify_workspace


def test_research_debug_requires_failure_context(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    GoalStore(config).save_issue(
        IssueDocument(
            id="GW-001",
            title="t",
            description="d",
            status=IssueStatus.OPEN,
            verify_command='python -c "import sys; sys.exit(0)"',
        )
    )

    with pytest.raises(ResearchDebugError, match="无可用失败上下文"):
        ResearchDebugService(config).run_debug("GW-001")


def test_research_debug_fixes_failing_verify(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_TEST_KEY"},
        autoresearch={"max_iterations": 3, "auto_commit_on_keep": False},
    )
    verify_cmd = setup_verify_workspace(config.workspace_path())

    store = GoalStore(config)
    store.save_issue(
        IssueDocument(
            id="GW-002",
            title="debug me",
            description="修复 demo 标记",
            status=IssueStatus.DONE,
            verify_command=verify_cmd,
            scope_files=["src/demo.py"],
        )
    )

    ar_store = AutoresearchStore(config)
    ar_store.ensure_layout()
    ar_store.append_result(
        {
            "iteration": 1,
            "issue_id": "GW-002",
            "status": "discard",
            "exit_code": 1,
            "error_summary": "missing agent-generated marker",
        }
    )

    result = ResearchDebugService(config).run_debug("GW-002")
    assert result.success is True
    text = (config.workspace_path() / "src" / "demo.py").read_text(encoding="utf-8")
    assert "agent-generated" in text


def test_research_debug_uses_current_verify_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_TEST_KEY"},
        autoresearch={"max_iterations": 3, "auto_commit_on_keep": False},
    )
    verify_cmd = setup_verify_workspace(config.workspace_path())

    GoalStore(config).save_issue(
        IssueDocument(
            id="GW-003",
            title="debug verify",
            description="修复",
            status=IssueStatus.OPEN,
            verify_command=verify_cmd,
            scope_files=["src/demo.py"],
        )
    )

    result = ResearchDebugService(config).run_debug("GW-003")
    assert result.success is True
