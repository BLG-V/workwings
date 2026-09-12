from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitState:
    available: bool
    head_sha: str = ""


class GitOps:
    def __init__(self, workspace: Path):
        self.workspace = workspace

    def is_repo(self) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def get_head(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return ""
        return (result.stdout or "").strip()

    def has_changes(self) -> bool:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
        )
        return bool((result.stdout or "").strip())

    def reset_hard(self, ref: str = "HEAD") -> bool:
        result = subprocess.run(
            ["git", "reset", "--hard", ref],
            cwd=self.workspace,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def add_all(self) -> bool:
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def commit(self, message: str) -> str:
        result = subprocess.run(
            ["git", "commit", "-m", message, "--no-verify"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return ""
        return self.get_head()

    def snapshot(self) -> GitState:
        if not self.is_repo():
            return GitState(available=False)
        return GitState(available=True, head_sha=self.get_head())
