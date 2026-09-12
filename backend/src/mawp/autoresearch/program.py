from __future__ import annotations

from mawp.autoresearch.models import ProgramConfig
from mawp.autoresearch.store import AutoresearchStore
from mawp.config.loader import AgentConfig
from mawp.autoresearch.utils import valid_scope_files
from mawp.goal.store import GoalStore


class ProgramService:
    """从 Issue 生成 autoresearch program.md。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.goal_store = GoalStore(config)
        self.ar_store = AutoresearchStore(config)

    def from_issue(self, issue: IssueDocument) -> tuple[ProgramConfig, str]:
        program = ProgramConfig(
            issue_id=issue.id,
            goal=f"{issue.title}\n\n{issue.description}",
            metric_command=issue.verify_command or "pytest -q",
            scope_files=valid_scope_files(list(issue.scope_files)),
            max_iterations=self.config.autoresearch.max_iterations,
            token_budget=self.config.autoresearch.token_budget,
        )
        path = self.ar_store.save_program(program)
        return program, str(path)

    def plan_for_issue_id(self, issue_id: str) -> tuple[ProgramConfig, str]:
        issue = self.goal_store.load_issue(issue_id)
        return self.from_issue(issue)

    def load(self) -> ProgramConfig:
        return self.ar_store.load_program()
