from __future__ import annotations

import json
from pathlib import Path

from mawp.security.policy import PolicyEngine
from mawp.tools.terminal_tools import run_terminal_cmd
from mawp.tools.test_parsing import parse_jest_output, parse_pytest_output, summarize_test_failures


def _detect_test_command(workspace: Path) -> str | None:
    if (workspace / "pytest.ini").exists() or (workspace / "pyproject.toml").exists():
        pyproject = workspace / "pyproject.toml"
        if pyproject.exists() and "pytest" in pyproject.read_text(encoding="utf-8", errors="ignore"):
            return "python -m pytest -q"
        if (workspace / "tests").is_dir():
            return "python -m pytest -q"

    pkg = workspace / "package.json"
    if pkg.exists():
        data = json.loads(pkg.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
        if "test" in scripts:
            return "npm test"
        if (workspace / "node_modules" / ".bin" / "jest").exists():
            return "npx jest --passWithNoTests"

    return None


def run_tests(
    policy: PolicyEngine,
    *,
    scope: str = "all",
    timeout_seconds: int = 120,
) -> dict:
    command = _detect_test_command(policy.workspace)
    if command is None:
        return {
            "framework": None,
            "command": None,
            "passed": False,
            "skipped": True,
            "message": "未检测到支持的测试框架（pytest / jest）",
        }

    if scope == "changed":
        # Phase 1: 增量测试与全量相同，Phase 2 再细化
        pass

    result = run_terminal_cmd(
        policy,
        command=command,
        timeout_seconds=timeout_seconds,
    )

    framework = "pytest" if "pytest" in command else "jest"
    passed = result["exit_code"] == 0
    parser = parse_pytest_output if framework == "pytest" else parse_jest_output
    stats = parser(result["stdout"], result["stderr"])

    return {
        "framework": framework,
        "command": command,
        "passed": passed,
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "duration_hint_ms": None,
        "passed_count": stats["passed_count"],
        "failed_count": stats["failed_count"],
        "skipped_count": stats["skipped_count"],
        "failures": stats["failures"],
        "suggestion": _suggest_fix(stats["failures"], result["stderr"]),
        "failure_summary": summarize_test_failures(
            stats["failures"],
            result["stderr"],
        ),
    }


def _suggest_fix(failures: list[dict[str, str]], stderr: str) -> str:
    summary = summarize_test_failures(failures, stderr)
    if failures:
        first = failures[0].get("name", "unknown")
        return f"优先修复失败用例 {first}。{summary}"
    if stderr.strip():
        return f"检查 stderr 中的编译/导入错误: {stderr.strip()[:200]}"
    return summary
