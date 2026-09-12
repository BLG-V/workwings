from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mawp.config.loader import AgentConfig, AgentTestingConfig
from mawp.security.policy import PolicyEngine
from mawp.tools.terminal_tools import run_terminal_cmd

_ISSUE_LINE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+)(?::(?P<col>\d+))?:\s*(?P<message>.+)$"
)


def _read_project_text(workspace: Path, name: str) -> str:
    path = workspace / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _detect_ruff_command(workspace: Path) -> str | None:
    pyproject = _read_project_text(workspace, "pyproject.toml")
    if "[tool.ruff" in pyproject or (workspace / "ruff.toml").is_file():
        return "python -m ruff check ."
    return None


def _detect_flake8_command(workspace: Path) -> str | None:
    if (workspace / ".flake8").is_file() or (workspace / "setup.cfg").is_file():
        return "python -m flake8 ."
    return None


def _detect_eslint_command(workspace: Path) -> str | None:
    pkg = workspace / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    scripts = data.get("scripts") or {}
    if "lint" in scripts:
        return "npm run lint"
    if (workspace / "eslint.config.js").is_file() or (
        workspace / ".eslintrc.json"
    ).is_file():
        return "npx eslint ."
    return None


def detect_linter_command(workspace: Path) -> tuple[str | None, str | None]:
    """返回 (command, framework)。"""
    for detector, framework in (
        (_detect_ruff_command, "ruff"),
        (_detect_flake8_command, "flake8"),
        (_detect_eslint_command, "eslint"),
    ):
        command = detector(workspace)
        if command:
            return command, framework
    return None, None


def _detect_mypy_command(workspace: Path) -> str | None:
    pyproject = _read_project_text(workspace, "pyproject.toml")
    if "[tool.mypy" in pyproject or (workspace / "mypy.ini").is_file():
        return "python -m mypy ."
    return None


def _detect_tsc_command(workspace: Path) -> str | None:
    pkg = workspace / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    scripts = data.get("scripts") or {}
    if "typecheck" in scripts:
        return "npm run typecheck"
    if (workspace / "tsconfig.json").is_file():
        return "npx tsc --noEmit"
    return None


def detect_typecheck_command(workspace: Path) -> tuple[str | None, str | None]:
    for detector, framework in (
        (_detect_mypy_command, "mypy"),
        (_detect_tsc_command, "tsc"),
    ):
        command = detector(workspace)
        if command:
            return command, framework
    return None, None


def _resolve_targets(workspace: Path, changed_files: list[str] | None) -> str:
    if not changed_files:
        return "."
    existing = [
        path.replace("\\", "/")
        for path in changed_files
        if (workspace / path.replace("\\", "/")).exists()
    ]
    if not existing:
        return "."
    return " ".join(f'"{path}"' for path in existing)


def _append_scope(command: str, targets: str) -> str:
    if targets == ".":
        return command
    if command.endswith(" ."):
        return command[:-2] + f" {targets}"
    return f"{command} {targets}"


def parse_lint_output(stdout: str, stderr: str = "") -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    for line in f"{stdout}\n{stderr}".splitlines():
        match = _ISSUE_LINE.match(line.strip())
        if match:
            issues.append(
                {
                    "file": match.group("file"),
                    "line": match.group("line"),
                    "message": match.group("message"),
                }
            )
    return {"issues": issues[:30], "issue_count": len(issues)}


def summarize_static_issues(report: dict[str, Any]) -> str:
    if report.get("skipped"):
        return ""
    issues = report.get("issues") or []
    if issues:
        first = issues[0]
        return (
            f"{report.get('framework', 'static')}: "
            f"{first.get('file')}:{first.get('line')} {first.get('message')}"
        )
    if not report.get("passed"):
        stderr = (report.get("stderr") or "").strip()
        stdout = (report.get("stdout") or "").strip()
        snippet = stderr or stdout
        return snippet[:400] if snippet else f"{report.get('framework')} 检查未通过"
    return ""


def _build_check_report(
    *,
    framework: str | None,
    command: str | None,
    result: dict[str, Any] | None,
    skipped: bool,
    message: str = "",
) -> dict[str, Any]:
    if skipped:
        return {
            "framework": framework,
            "command": command,
            "passed": True,
            "skipped": True,
            "message": message or "未检测到对应静态检查配置",
            "issues": [],
            "issue_count": 0,
        }

    assert result is not None
    parsed = parse_lint_output(result.get("stdout") or "", result.get("stderr") or "")
    passed = int(result.get("exit_code") or 1) == 0
    report = {
        "framework": framework,
        "command": command,
        "passed": passed,
        "skipped": False,
        "exit_code": result.get("exit_code"),
        "stdout": result.get("stdout") or "",
        "stderr": result.get("stderr") or "",
        "issues": parsed["issues"],
        "issue_count": parsed["issue_count"],
        "message": message,
    }
    report["suggestion"] = summarize_static_issues(report)
    return report


def run_linter(
    policy: PolicyEngine,
    *,
    scope: str = "all",
    changed_files: list[str] | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    workspace = policy.workspace
    command, framework = detect_linter_command(workspace)
    if command is None:
        return _build_check_report(
            framework=None,
            command=None,
            result=None,
            skipped=True,
            message="未检测到支持的 Linter（ruff / flake8 / eslint）",
        )

    targets = _resolve_targets(
        workspace,
        changed_files if scope == "changed" else None,
    )
    command = _append_scope(command, targets)
    result = run_terminal_cmd(
        policy,
        command=command,
        timeout_seconds=timeout_seconds,
    )
    return _build_check_report(
        framework=framework,
        command=command,
        result=result,
        skipped=False,
    )


def run_typecheck(
    policy: PolicyEngine,
    *,
    scope: str = "all",
    changed_files: list[str] | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    workspace = policy.workspace
    command, framework = detect_typecheck_command(workspace)
    if command is None:
        return _build_check_report(
            framework=None,
            command=None,
            result=None,
            skipped=True,
            message="未检测到支持的类型检查（mypy / tsc）",
        )

    targets = _resolve_targets(
        workspace,
        changed_files if scope == "changed" else None,
    )
    command = _append_scope(command, targets)
    result = run_terminal_cmd(
        policy,
        command=command,
        timeout_seconds=timeout_seconds,
    )
    return _build_check_report(
        framework=framework,
        command=command,
        result=result,
        skipped=False,
    )


def build_static_check_report(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "passed": bool(raw.get("passed")),
        "skipped": bool(raw.get("skipped")),
        "framework": raw.get("framework"),
        "command": raw.get("command"),
        "exit_code": raw.get("exit_code"),
        "stdout": raw.get("stdout") or "",
        "stderr": raw.get("stderr") or "",
        "issues": raw.get("issues") or [],
        "issue_count": raw.get("issue_count", 0),
        "suggestion": raw.get("suggestion") or raw.get("message") or "",
        "message": raw.get("message") or "",
    }


def _check_passed(report: dict[str, Any], *, block: bool) -> bool:
    if not block:
        return True
    if report.get("skipped"):
        return True
    return bool(report.get("passed"))


def aggregate_testing_passed(
    test_report: dict[str, Any],
    lint_report: dict[str, Any],
    typecheck_report: dict[str, Any],
    config: AgentTestingConfig,
) -> bool:
    if not _check_passed(test_report, block=True):
        return False
    if not _check_passed(
        lint_report,
        block=config.run_linter and config.block_on_lint_errors,
    ):
        return False
    if not _check_passed(
        typecheck_report,
        block=config.run_typecheck and config.block_on_type_errors,
    ):
        return False
    return True
