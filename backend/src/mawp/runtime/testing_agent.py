"""Testing Agent（C）：执行 metric_command，产出 pass/fail + 日志摘要。

outputs 键名与 docs/w4-ad-deliver-yaml-align.md 冻结契约对齐。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mawp.autoresearch.verifier import run_metric_command
from mawp.runtime.agents import AgentRunContext


def _resolve_attempt(input_data: dict[str, Any], ctx: AgentRunContext) -> int:
    if "attempt" in input_data and input_data.get("attempt") is not None:
        return int(input_data["attempt"])
    prev = ctx.nodes_outputs.get(ctx.node_id) or {}
    return int(prev.get("attempt") or 0) + 1


def _log_summary(*, passed: bool, command: str, verify: dict[str, Any], attempt: int) -> str:
    exit_code = verify.get("exit_code")
    duration = verify.get("duration_ms", 0)
    stdout = (verify.get("stdout") or "").strip()
    stderr = (verify.get("stderr") or "").strip()
    tail = stdout or stderr
    if len(tail) > 240:
        tail = tail[:240] + "..."
    status = "PASS" if passed else "FAIL"
    base = f"[{status}] attempt={attempt} exit={exit_code} {duration}ms cmd=`{command}`"
    return f"{base} | {tail}" if tail else base


def _failures_from_verify(verify: dict[str, Any], attempt: int) -> list[str]:
    failures: list[str] = []
    stderr = (verify.get("stderr") or "").strip()
    stdout = (verify.get("stdout") or "").strip()
    if stderr:
        failures.append(stderr.splitlines()[-1][:200])
    elif stdout:
        # pytest -q 失败时常把摘要打在 stdout
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line and ("FAILED" in line or "Error" in line or "fail" in line.lower()):
                failures.append(line[:200])
                break
    if not failures:
        failures.append(
            f"metric_command failed on attempt={attempt} exit={verify.get('exit_code')}"
        )
    return failures


def run_testing_agent(
    input_data: dict[str, Any],
    ctx: AgentRunContext,
    *,
    workspace: Path,
) -> dict[str, Any]:
    """执行 Testing Agent。

    优先跑 ``metric_command``（input / params）；若未提供则回退到
    ``pass_on_attempt`` / ``force_test_status`` 演示逻辑（兼容 A 骨架单测）。
    """
    attempt = _resolve_attempt(input_data, ctx)
    metric = (
        input_data.get("metric_command")
        or ctx.params.get("metric_command")
        or input_data.get("verify_command")
        or ctx.params.get("verify_command")
    )
    force = ctx.params.get("force_test_status")

    if metric and force not in ("pass", "fail"):
        command = str(metric).strip()
        timeout = int(
            input_data.get("timeout_seconds")
            or ctx.params.get("timeout_seconds")
            or 120
        )
        verify = run_metric_command(
            workspace=workspace,
            command=command,
            timeout_seconds=timeout,
        )
        passed = bool(verify.get("passed"))
        return {
            "passed": passed,
            "status": "pass" if passed else "fail",
            "failures": [] if passed else _failures_from_verify(verify, attempt),
            "log_summary": _log_summary(
                passed=passed, command=command, verify=verify, attempt=attempt
            ),
            "attempt": attempt,
            "metric_command": command,
            "exit_code": verify.get("exit_code"),
            "duration_ms": verify.get("duration_ms"),
        }

    # —— 演示 / 回环骨架（无真实命令时）——
    pass_on = int(ctx.params.get("pass_on_attempt") or 1)
    if force in ("pass", "fail"):
        passed = force == "pass"
    else:
        passed = attempt >= pass_on
    failures = [] if passed else [f"mock failure on attempt={attempt}"]
    return {
        "passed": passed,
        "status": "pass" if passed else "fail",
        "failures": failures,
        "log_summary": (
            "all checks green" if passed else f"failed at attempt {attempt}"
        ),
        "attempt": attempt,
    }
