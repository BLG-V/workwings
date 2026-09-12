from __future__ import annotations

from pathlib import Path

from mawp.config.loader import AgentConfig


class GoalPaths:
    """`.goal/` 目录路径助手。"""

    def __init__(self, config: AgentConfig):
        self.base = config.workspace_path() / config.goal_workflow.base_path

    @property
    def prd_dir(self) -> Path:
        return self.base / "prd"

    @property
    def spec_dir(self) -> Path:
        return self.base / "spec"

    @property
    def issues_dir(self) -> Path:
        return self.base / "issues"

    @property
    def archive_dir(self) -> Path:
        return self.base / "archive"

    def prd_path(self, slug: str) -> Path:
        return self.prd_dir / f"{slug}.md"

    def spec_path(self, slug: str) -> Path:
        return self.spec_dir / f"{slug}.md"

    def issue_path(self, issue_id: str) -> Path:
        return self.issues_dir / f"{issue_id}.md"

    def ensure_layout(self) -> None:
        for directory in (
            self.prd_dir,
            self.spec_dir,
            self.issues_dir,
            self.archive_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
