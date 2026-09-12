from __future__ import annotations

import subprocess
from pathlib import Path

from mawp.autoresearch.store import AutoresearchStore
from mawp.autoresearch.utils import valid_scope_files
from mawp.config.loader import AgentConfig
from mawp.goal.models import IssueDocument


def collect_changed_files(config: AgentConfig, issue: IssueDocument) -> list[str]:
    """推断 Issue 相关变更文件。"""
    files: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        path = path.replace("\\", "/")
        if path and path not in seen:
            seen.add(path)
            files.append(path)

    for path in valid_scope_files(issue.scope_files):
        add(path)

    workspace = config.workspace_path()
    ar_store = AutoresearchStore(config)
    for row in reversed(ar_store.load_results(issue_id=issue.id)):
        if row.get("status") == "keep":
            for path in row.get("files_changed") or []:
                add(str(path))
            break

    if _git_available(workspace):
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in (result.stdout or "").splitlines():
                add(line.strip())

    return files


def issue_to_requirement_spec(issue: IssueDocument) -> dict:
    return {
        "summary": issue.title,
        "acceptance_criteria": issue.acceptance_criteria,
        "related_files": valid_scope_files(issue.scope_files),
        "open_questions": [],
    }


def _git_available(workspace: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
