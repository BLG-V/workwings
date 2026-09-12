from __future__ import annotations

import json
from pathlib import Path

import pytest

from mawp.autoresearch.git_ops import GitOps
from mawp.autoresearch.loop import AutoresearchLoop
from mawp.autoresearch.models import ProgramConfig
from mawp.autoresearch.program import ProgramService
from mawp.autoresearch.store import AutoresearchStore, parse_program
from mawp.autoresearch.verifier import WorkspaceSnapshot, run_metric_command
from mawp.config.loader import AgentConfig
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore
from mawp.goal.deps import DependencyNotReadyError


def test_parse_program_roundtrip() -> None:
    program = ProgramConfig(
        issue_id="GW-001",
        goal="实现登录",
        metric_command="pytest tests/test_auth.py -q",
        scope_files=["src/auth/login.py"],
        max_iterations=10,
        token_budget=100000,
    )
    text = program.to_markdown()
    loaded = parse_program(text)
    assert loaded.issue_id == "GW-001"
    assert loaded.metric_command == "pytest tests/test_auth.py -q"
    assert "src/auth/login.py" in loaded.scope_files
    assert loaded.max_iterations == 10


def test_valid_scope_files_filters_placeholders() -> None:
    from mawp.autoresearch.utils import valid_scope_files

    assert valid_scope_files(["src/a.py", "（实现时确定）", ""]) == ["src/a.py"]


def test_program_service_from_issue(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    goal_store = GoalStore(config)
    issue = IssueDocument(
        id="GW-001",
        title="测试 Issue",
        description="实现某功能",
        verify_command="pytest -q",
        scope_files=["src/foo.py"],
        acceptance_criteria=["功能可用"],
    )
    goal_store.save_issue(issue)

    service = ProgramService(config)
    program, path = service.from_issue(issue)
    assert Path(path).is_file()
    assert program.issue_id == "GW-001"
    assert service.load().metric_command == "pytest -q"


def test_workspace_snapshot_restore(tmp_path) -> None:
    target = tmp_path / "src" / "foo.py"
    target.parent.mkdir(parents=True)
    target.write_text("original\n", encoding="utf-8")

    snap = WorkspaceSnapshot.capture(tmp_path, ["src/foo.py"])
    target.write_text("modified\n", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "modified\n"

    snap.restore()
    assert target.read_text(encoding="utf-8") == "original\n"


def test_run_metric_command_pass_and_fail(tmp_path) -> None:
    ok = run_metric_command(workspace=tmp_path, command="python -c \"import sys; sys.exit(0)\"")
    assert ok["passed"] is True
    assert ok["exit_code"] == 0

    bad = run_metric_command(workspace=tmp_path, command="python -c \"import sys; sys.exit(1)\"")
    assert bad["passed"] is False
    assert bad["exit_code"] == 1


def test_autoresearch_loop_success_without_git(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_TEST_KEY"},
        autoresearch={"max_iterations": 3, "auto_commit_on_keep": False},
    )
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "demo.py"
    target.write_text("# demo\n", encoding="utf-8")

    script = tmp_path / "verify.py"
    script.write_text(
        "from pathlib import Path\n"
        "p = Path('src/demo.py')\n"
        "text = p.read_text(encoding='utf-8')\n"
        "raise SystemExit(0 if 'agent-generated' in text else 1)\n",
        encoding="utf-8",
    )

    goal_store = GoalStore(config)
    issue = IssueDocument(
        id="GW-001",
        title="添加标记",
        description="在 demo.py 添加 agent-generated 标记",
        verify_command="python verify.py",
        scope_files=["src/demo.py"],
        acceptance_criteria=["文件含 agent-generated"],
    )
    goal_store.save_issue(issue)

    program = ProgramConfig(
        issue_id="GW-001",
        goal=issue.description,
        metric_command="python verify.py",
        scope_files=["src/demo.py"],
        max_iterations=3,
    )

    loop = AutoresearchLoop(config)
    result = loop.run_for_issue(issue, program)

    assert result.success is True
    assert result.passed_at == 1
    assert "agent-generated" in target.read_text(encoding="utf-8")

    reloaded = goal_store.load_issue("GW-001")
    assert reloaded.status == IssueStatus.DONE

    ar_store = AutoresearchStore(config)
    logs = ar_store.load_results(issue_id="GW-001")
    assert len(logs) >= 1
    assert logs[-1]["status"] == "keep"
    assert "diff_summary" in logs[-1]


def test_summarize_diff() -> None:
    from mawp.autoresearch.reports import summarize_diff

    assert summarize_diff([]) == "无文件变更"
    assert "1 file" in summarize_diff(["src/a.py"])
    assert "2 files" in summarize_diff(["src/a.py", "src/b.py"])


def test_autoresearch_loop_blocked_after_max_iterations(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = AgentConfig(
        workspace=str(tmp_path),
        llm={"provider": "openai", "api_key_env": "NONEXISTENT_TEST_KEY"},
        autoresearch={"max_iterations": 1, "auto_commit_on_keep": False},
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "demo.py").write_text("# demo\n", encoding="utf-8")

    goal_store = GoalStore(config)
    issue = IssueDocument(
        id="GW-002",
        title="不可能任务",
        description="不会成功的修改",
        verify_command="python -c \"import sys; sys.exit(1)\"",
        scope_files=["src/demo.py"],
    )
    goal_store.save_issue(issue)

    program = ProgramConfig(
        issue_id="GW-002",
        goal=issue.description,
        metric_command=issue.verify_command,
        scope_files=["src/demo.py"],
        max_iterations=1,
    )

    loop = AutoresearchLoop(config)
    result = loop.run_for_issue(issue, program)

    assert result.success is False
    assert "最大迭代" in result.blocked_reason
    assert result.blocked_report_path
    report = Path(result.blocked_report_path)
    assert report.is_file()
    content = report.read_text(encoding="utf-8")
    assert "GW-002" in content
    assert "迭代记录" in content

    reloaded = goal_store.load_issue("GW-002")
    assert reloaded.status == IssueStatus.BLOCKED


def test_autoresearch_loop_blocked_by_dependency(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    goal_store = GoalStore(config)
    goal_store.save_issue(
        IssueDocument(
            id="GW-001",
            title="first",
            description="d",
            status=IssueStatus.OPEN,
        )
    )
    goal_store.save_issue(
        IssueDocument(
            id="GW-002",
            title="second",
            description="d",
            depends_on=["GW-001"],
            verify_command="pytest -q",
        )
    )

    program = ProgramConfig(
        issue_id="GW-002",
        goal="second",
        metric_command="pytest -q",
        max_iterations=1,
    )
    loop = AutoresearchLoop(config)
    issue = goal_store.load_issue("GW-002")

    with pytest.raises(DependencyNotReadyError):
        loop.run_for_issue(issue, program)


def test_git_ops_init_repo(tmp_path) -> None:
    git = GitOps(tmp_path)
    assert git.is_repo() is False

    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    assert git.is_repo() is True

    readme = tmp_path / "README.md"
    readme.write_text("init\n", encoding="utf-8")
    git.add_all()
    initial_sha = git.commit("init")
    assert initial_sha
    assert git.get_head() == initial_sha

    test_file = tmp_path / "a.txt"
    test_file.write_text("hi", encoding="utf-8")
    git.add_all()
    sha = git.commit("add a")
    assert sha
    assert git.get_head() == sha

    test_file.write_text("changed", encoding="utf-8")
    assert git.has_changes()
    git.reset_hard(sha)
    assert test_file.read_text(encoding="utf-8") == "hi"
