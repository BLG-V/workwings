from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from mawp.security.policy import PolicyEngine

MAX_OUTPUT_BYTES = 256 * 1024


def _rel_path(policy: PolicyEngine, path: Path) -> str:
    return path.relative_to(policy.workspace).as_posix()


def run_terminal_cmd(
    policy: PolicyEngine,
    *,
    command: str,
    cwd: str | None = None,
    timeout_seconds: int = 120,
) -> dict:
    policy.check_command(command)

    work_dir = policy.workspace
    if cwd:
        work_dir = policy.check_read(cwd)
        if not work_dir.is_dir():
            raise NotADirectoryError(f"不是目录: {work_dir}")

    if sys.platform == "win32":
        proc = subprocess.run(
            command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )
    else:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    truncated = False
    if len(stdout.encode("utf-8")) > MAX_OUTPUT_BYTES:
        stdout = stdout[:MAX_OUTPUT_BYTES] + "\n...[truncated]"
        truncated = True
    if len(stderr.encode("utf-8")) > MAX_OUTPUT_BYTES:
        stderr = stderr[:MAX_OUTPUT_BYTES] + "\n...[truncated]"
        truncated = True

    return {
        "command": command,
        "cwd": _rel_path(policy, work_dir),
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": truncated,
    }
