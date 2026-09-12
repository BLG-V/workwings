from __future__ import annotations

import pytest

from mawp.config.loader import AgentConfig
from mawp.goal.loop import GoalLoopService
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore

from tests.e2e.conftest import setup_verify_workspace


def _save_pair(config: AgentConfig, verify_cmd: str) -> tuple[str, str]:
    store = GoalStore(config)
    store.save_issue(
        IssueDocument(
            id="GW-001",
            title="first",
            description="第一步",
            status=IssueStatus.OPEN,
            verify_command=verify_cmd,
            scope_files=["src/demo.py"],
            prd_ref="feat",
            spec_ref="feat",
        )
    )
    store.save_issue(
        IssueDocument(
            id="GW-002",
            title="second",
            description="第二步",
            status=IssueStatus.OPEN,
            verify_command=verify_cmd,
            scope_files=["src/demo.py"],
            depends_on=["GW-001"],
            prd_ref="feat",
            spec_ref="feat",
        )
    )
    return "GW-001", "GW-002"


def test_goal_loop_runs_in_dependency_order(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_TEST_KEY"},
        autoresearch={"max_iterations": 3, "auto_commit_on_keep": False},
    )
    verify_cmd = setup_verify_workspace(config.workspace_path())
    _save_pair(config, verify_cmd)

    service = GoalLoopService(config)
    result = service.run("feat", resume=False)
    assert result.success is True
    assert result.completed == ["GW-001", "GW-002"]
    assert not service.checkpoint_path("feat").exists()


def test_goal_loop_resumes_from_checkpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_TEST_KEY"},
        autoresearch={"max_iterations": 3, "auto_commit_on_keep": False},
    )
    verify_cmd = setup_verify_workspace(config.workspace_path())
    _save_pair(config, verify_cmd)

    service = GoalLoopService(config)
    store = GoalStore(config)

    issue1 = store.load_issue("GW-001")
    issue1.status = IssueStatus.DONE
    store.save_issue(issue1)
    service.save_checkpoint("feat", completed=["GW-001"])

    result = service.run("feat", resume=True)
    assert result.success is True
    assert result.completed == ["GW-001", "GW-002"]


def test_goal_loop_stops_on_blocked_issue(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    verify_cmd = setup_verify_workspace(config.workspace_path())
    _save_pair(config, verify_cmd)

    store = GoalStore(config)
    blocked = store.load_issue("GW-001")
    blocked.status = IssueStatus.BLOCKED
    store.save_issue(blocked)

    result = GoalLoopService(config).run("feat", resume=False)
    assert result.success is False
    assert result.failed_issue_id == "GW-001"
