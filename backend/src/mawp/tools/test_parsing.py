from __future__ import annotations

import re
from typing import Any

_FAILED_LINE = re.compile(
    r"^(?P<name>\S+::\S+)\s+FAILED",
)
_ASSERTION_ERROR = re.compile(
    r"^E\s+assert .+",
)


def parse_pytest_output(stdout: str, stderr: str = "") -> dict[str, Any]:
    text = f"{stdout}\n{stderr}"
    passed = 0
    failed = 0
    skipped = 0
    failures: list[dict[str, str]] = []

    summary_match = re.search(
        r"(\d+)\s+failed(?:,\s+(\d+)\s+passed)?(?:,\s+(\d+)\s+skipped)?|"
        r"(\d+)\s+passed(?:,\s+(\d+)\s+failed)?(?:,\s+(\d+)\s+skipped)?",
        text,
    )
    if summary_match:
        groups = summary_match.groups()
        if groups[0] is not None:
            failed = int(groups[0])
            passed = int(groups[1] or 0)
            skipped = int(groups[2] or 0)
        else:
            passed = int(groups[3] or 0)
            failed = int(groups[4] or 0)
            skipped = int(groups[5] or 0)

    current: dict[str, str] | None = None
    for line in stdout.splitlines():
        stripped = line.strip()
        failed_match = _FAILED_LINE.match(stripped)
        if failed_match:
            current = {
                "name": failed_match.group("name"),
                "detail": "",
            }
            failures.append(current)
            continue

        if stripped.endswith(" FAILED") or " FAILED " in stripped:
            name = stripped.replace(" FAILED", "").strip()
            current = {"name": name, "detail": ""}
            failures.append(current)
            continue

        if stripped.startswith("E   ") and current is not None:
            current["detail"] = (current.get("detail", "") + stripped + "\n").strip()
        elif _ASSERTION_ERROR.match(stripped) and current is not None:
            current["detail"] = (current.get("detail", "") + stripped + "\n").strip()

    if failed and not failures:
        for line in stdout.splitlines():
            if "AssertionError" in line or "assert" in line:
                failures.append({"name": "unknown", "detail": line.strip()})
                break

    summary_failed = re.search(
        r"^FAILED\s+(?P<name>\S+?)(?:\s+-\s+(?P<detail>.+))?$",
        text,
        re.MULTILINE,
    )
    if summary_failed and not any(
        f.get("name") == summary_failed.group("name") for f in failures
    ):
        failures.insert(
            0,
            {
                "name": summary_failed.group("name"),
                "detail": summary_failed.group("detail") or "",
            },
        )

    return {
        "passed_count": passed,
        "failed_count": failed,
        "skipped_count": skipped,
        "failures": failures[:20],
    }


def summarize_test_failures(
    failures: list[dict[str, str]],
    stderr: str = "",
) -> str:
    """将失败用例整理为可供 Coding Agent 阅读的摘要。"""
    if not failures:
        if stderr.strip():
            return f"测试 stderr: {stderr.strip()[:500]}"
        return "测试失败，但未解析到具体用例"

    lines: list[str] = []
    for index, failure in enumerate(failures[:5], start=1):
        name = failure.get("name") or "unknown"
        detail = (failure.get("detail") or "").strip()
        entry = f"{index}. {name}"
        if detail:
            entry += f"\n   {detail[:400]}"
        lines.append(entry)
    return "\n".join(lines)


def parse_jest_output(stdout: str, stderr: str = "") -> dict[str, Any]:
    text = f"{stdout}\n{stderr}"
    passed = failed = skipped = 0
    failures: list[dict[str, str]] = []

    tests_match = re.search(
        r"Tests:\s+(?:(\d+) failed, )?(?:(\d+) skipped, )?(?:(\d+) passed)",
        text,
    )
    if tests_match:
        failed = int(tests_match.group(1) or 0)
        skipped = int(tests_match.group(2) or 0)
        passed = int(tests_match.group(3) or 0)

    for line in stdout.splitlines():
        if "● " in line:
            failures.append({"name": line.strip(), "detail": ""})

    return {
        "passed_count": passed,
        "failed_count": failed,
        "skipped_count": skipped,
        "failures": failures[:20],
    }
