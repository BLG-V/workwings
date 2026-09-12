from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mawp.config.loader import AgentConfig, AgentTestingConfig
from mawp.security.policy import PolicyEngine
from mawp.tools.lint_tools import (
    aggregate_testing_passed,
    build_static_check_report,
    detect_linter_command,
    detect_typecheck_command,
    parse_lint_output,
    run_linter,
    run_typecheck,
    summarize_static_issues,
)


def test_detect_ruff_command(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 88\n",
        encoding="utf-8",
    )
    command, framework = detect_linter_command(tmp_path)
    assert framework == "ruff"
    assert command == "python -m ruff check ."


def test_detect_mypy_command(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.mypy]\npython_version = '3.11'\n",
        encoding="utf-8",
    )
    command, framework = detect_typecheck_command(tmp_path)
    assert framework == "mypy"
    assert command == "python -m mypy ."


def test_run_linter_skipped_without_config(tmp_path: Path) -> None:
    policy = PolicyEngine(AgentConfig(workspace=str(tmp_path)))
    report = run_linter(policy)
    assert report["skipped"] is True
    assert report["passed"] is True


def test_run_typecheck_skipped_without_config(tmp_path: Path) -> None:
    policy = PolicyEngine(AgentConfig(workspace=str(tmp_path)))
    report = run_typecheck(policy)
    assert report["skipped"] is True
    assert report["passed"] is True


def test_parse_lint_output_extracts_issue() -> None:
    stdout = "src/app.py:12:5: F401 unused import\n"
    parsed = parse_lint_output(stdout)
    assert parsed["issue_count"] == 1
    assert parsed["issues"][0]["file"] == "src/app.py"


def test_aggregate_testing_passed_blocks_on_typecheck() -> None:
    config = AgentTestingConfig()
    test_report = {"passed": True, "skipped": False}
    lint_report = {"passed": True, "skipped": True}
    typecheck_report = {
        "passed": False,
        "skipped": False,
        "framework": "mypy",
        "suggestion": "src/app.py:10: error: Incompatible return value",
    }
    assert aggregate_testing_passed(test_report, lint_report, typecheck_report, config) is False


def test_summarize_static_issues() -> None:
    report = build_static_check_report(
        {
            "passed": False,
            "skipped": False,
            "framework": "mypy",
            "issues": [{"file": "src/a.py", "line": "3", "message": "type error"}],
        }
    )
    summary = summarize_static_issues(report)
    assert "src/a.py" in summary
