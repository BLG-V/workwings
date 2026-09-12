from __future__ import annotations

import pytest

from mawp.autoresearch.loop import AutoresearchLoop, ResumeNotAvailableError
from mawp.autoresearch.program import ProgramService
from mawp.autoresearch.store import AutoresearchStore
from mawp.config.loader import AgentConfig
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore
from mawp.llm.mock import MockLLMAdapter

from tests.e2e.conftest import (
    build_fail_then_pass_llm,
    demo_marker_content,
    patch_mock_llm,
    setup_verify_workspace,
)


def test_can_resume_after_discard_checkpoint(tmp_path, monkeypatch) -> None:
    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "mock"},
        autoresearch={"max_iterations": 5, "auto_commit_on_keep": False},
    )
    verify_cmd = setup_verify_workspace(config.workspace_path())
    store = GoalStore(config)
    store.save_issue(
        IssueDocument(
            id="GW-070",
            title="resume test",
            description="d",
            status=IssueStatus.OPEN,
            verify_command=verify_cmd,
            scope_files=["src/demo.py"],
        )
    )

    loop = AutoresearchLoop(config)
    program, _ = ProgramService(config).from_issue(store.load_issue("GW-070"))
    patch_mock_llm(monkeypatch, MockLLMAdapter([MockLLMAdapter.json_response({
        "change_plan": [],
        "files_changed": [],
        "changelog": "noop",
    })]))

    original_save = loop._save_running_checkpoint

    def interrupt_after_first(*args, **kwargs):
        original_save(*args, **kwargs)
        raise InterruptedError("simulated interrupt")

    monkeypatch.setattr(loop, "_save_running_checkpoint", interrupt_after_first)

    issue = store.load_issue("GW-070")
    with pytest.raises(InterruptedError):
        loop.run_for_issue(issue, program)

    assert loop.can_resume("GW-070")
    ctx = AutoresearchStore(config).get_resume_context("GW-070")
    assert ctx is not None
    assert ctx["next_iteration"] == 2


def test_resume_continues_from_next_iteration(tmp_path, monkeypatch) -> None:
    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "mock"},
        autoresearch={"max_iterations": 5, "auto_commit_on_keep": False},
    )
    verify_cmd = setup_verify_workspace(config.workspace_path())
    store = GoalStore(config)
    store.save_issue(
        IssueDocument(
            id="GW-071",
            title="resume pass",
            description="d",
            status=IssueStatus.IN_PROGRESS,
            verify_command=verify_cmd,
            scope_files=["src/demo.py"],
        )
    )

    ar_store = AutoresearchStore(config)
    ar_store.ensure_layout()
    ar_store.append_result(
        {
            "iteration": 1,
            "issue_id": "GW-071",
            "status": "discard",
            "metric_command": verify_cmd,
            "exit_code": 1,
            "passed": False,
            "duration_ms": 1,
            "error_summary": "fail",
        }
    )
    ar_store.save_running_checkpoint(
        issue_id="GW-071",
        next_iteration=2,
        total_tokens=10,
        feedback={"kind": "test_failure", "message": "missing marker"},
        iterations_completed=1,
    )

    patch_mock_llm(
        monkeypatch,
        MockLLMAdapter(
            [
                MockLLMAdapter.tool_call_response(
                    "c1",
                    "write_file",
                    {"path": "src/demo.py", "content": demo_marker_content()},
                ),
                MockLLMAdapter.json_response(
                    {
                        "change_plan": [],
                        "files_changed": ["src/demo.py"],
                        "changelog": "fixed",
                    }
                ),
            ]
        ),
    )

    loop = AutoresearchLoop(config)
    result = loop.resume_for_issue("GW-071")
    assert result.success is True
    assert result.passed_at == 2
    logs = ar_store.load_results(issue_id="GW-071")
    assert len(logs) == 2
    assert logs[0]["status"] == "discard"
    assert logs[1]["status"] == "keep"


def test_resume_not_available_without_checkpoint(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    GoalStore(config).save_issue(
        IssueDocument(
            id="GW-072",
            title="t",
            description="d",
            verify_command="pytest -q",
        )
    )
    with pytest.raises(ResumeNotAvailableError):
        AutoresearchLoop(config).resume_for_issue("GW-072")
