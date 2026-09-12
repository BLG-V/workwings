from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileSnapshot:
    path: Path
    existed: bool
    content: bytes | None = None


@dataclass
class WorkspaceSnapshot:
    files: dict[str, FileSnapshot] = field(default_factory=dict)

    @classmethod
    def capture(cls, workspace: Path, paths: list[str]) -> WorkspaceSnapshot:
        snap = cls()
        seen: set[str] = set()
        for rel in paths:
            if not rel or rel in seen:
                continue
            seen.add(rel)
            full = workspace / rel
            if full.is_file():
                snap.files[rel] = FileSnapshot(
                    path=full,
                    existed=True,
                    content=full.read_bytes(),
                )
            else:
                snap.files[rel] = FileSnapshot(path=full, existed=False)
        return snap

    def restore(self) -> None:
        for rel, snap in self.files.items():
            if snap.existed:
                if snap.content is not None:
                    snap.path.parent.mkdir(parents=True, exist_ok=True)
                    snap.path.write_bytes(snap.content)
            elif snap.path.exists():
                snap.path.unlink()

    def merge_paths(self, extra: list[str], workspace: Path) -> None:
        for rel in extra:
            if rel in self.files:
                continue
            full = workspace / rel
            if full.is_file():
                self.files[rel] = FileSnapshot(
                    path=full,
                    existed=True,
                    content=full.read_bytes(),
                )
            else:
                self.files[rel] = FileSnapshot(path=full, existed=False)


def run_metric_command(
    *,
    workspace: Path,
    command: str,
    timeout_seconds: int = 120,
) -> dict:
    from mawp.config.loader import AgentConfig
    from mawp.security.policy import PolicyEngine
    from mawp.tools.terminal_tools import run_terminal_cmd

    config = AgentConfig(workspace=str(workspace))
    policy = PolicyEngine(config)
    started = time.perf_counter()
    try:
        result = run_terminal_cmd(
            policy,
            command=command,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(exc),
            "duration_ms": duration_ms,
            "command": command,
        }

    duration_ms = int((time.perf_counter() - started) * 1000)
    exit_code = int(result.get("exit_code", 1))
    return {
        "passed": exit_code == 0,
        "exit_code": exit_code,
        "stdout": result.get("stdout") or "",
        "stderr": result.get("stderr") or "",
        "duration_ms": duration_ms,
        "command": command,
    }
