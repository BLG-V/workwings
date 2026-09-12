from __future__ import annotations

import json
import re
from pathlib import Path

from mawp.autoresearch.models import ProgramConfig
from mawp.config.loader import AgentConfig


class AutoresearchPaths:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.base = config.workspace_path() / ".autoresearch"

    @property
    def program_path(self) -> Path:
        return self.base / "program.md"

    @property
    def state_path(self) -> Path:
        return self.base / "state.json"

    def ensure_layout(self) -> Path:
        self.base.mkdir(parents=True, exist_ok=True)
        return self.base


class AutoresearchStore:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.paths = AutoresearchPaths(config)
        results_rel = config.autoresearch.results_path
        if results_rel.startswith(".autoresearch"):
            self.results_file = config.workspace_path() / results_rel
        else:
            self.results_file = self.paths.base / "results.jsonl"

    def ensure_layout(self) -> Path:
        self.paths.ensure_layout()
        return self.paths.base

    def save_program(self, program: ProgramConfig) -> Path:
        self.ensure_layout()
        path = self.paths.program_path
        path.write_text(program.to_markdown(), encoding="utf-8")
        return path

    def load_program(self) -> ProgramConfig:
        path = self.paths.program_path
        if not path.is_file():
            raise FileNotFoundError(f"program.md 不存在: {path}")
        return parse_program(path.read_text(encoding="utf-8"))

    def append_result(self, record: dict) -> None:
        self.ensure_layout()
        with self.results_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_results(self, *, issue_id: str | None = None) -> list[dict]:
        if not self.results_file.is_file():
            return []
        rows: list[dict] = []
        for line in self.results_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if issue_id is None or row.get("issue_id") == issue_id:
                rows.append(row)
        return rows

    def save_state(self, state: dict) -> None:
        self.ensure_layout()
        self.paths.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_state(self) -> dict:
        if not self.paths.state_path.is_file():
            return {}
        return json.loads(self.paths.state_path.read_text(encoding="utf-8"))

    def save_running_checkpoint(
        self,
        *,
        issue_id: str,
        next_iteration: int,
        total_tokens: int,
        feedback: dict,
        iterations_completed: int,
    ) -> None:
        self.save_state(
            {
                "issue_id": issue_id,
                "status": "running",
                "next_iteration": next_iteration,
                "total_tokens": total_tokens,
                "feedback": feedback,
                "iterations_completed": iterations_completed,
            }
        )

    def get_resume_context(self, issue_id: str) -> dict | None:
        state = self.load_state()
        if state.get("issue_id") != issue_id:
            return None
        if state.get("status") != "running":
            return None
        return state

    def clear_running_checkpoint(self) -> None:
        state = self.load_state()
        if state.get("status") == "running":
            self.paths.state_path.unlink(missing_ok=True)


def parse_program(text: str) -> ProgramConfig:
    goal_match = re.search(r"^## Goal\s*\n(.+?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    goal = goal_match.group(1).strip() if goal_match else ""

    metric_match = re.search(
        r"## Metric.*?\n```bash\s*\n(.*?)\n```",
        text,
        flags=re.DOTALL,
    )
    metric_command = metric_match.group(1).strip() if metric_match else "pytest -q"

    scope_section = re.search(
        r"## Scope.*?\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    scope_files: list[str] = []
    if scope_section:
        for line in scope_section.group(1).splitlines():
            line = line.strip()
            if line.startswith("- ") and "（" not in line[:6]:
                scope_files.append(line[2:].strip())

    issue_match = re.search(r"- ID:\s*(\S+)", text)
    issue_id = issue_match.group(1).strip() if issue_match else "GW-000"

    max_iter = 25
    max_match = re.search(r"max_iterations:\s*(\d+)", text)
    if max_match:
        max_iter = int(max_match.group(1))

    budget = 500_000
    budget_match = re.search(r"token_budget:\s*(\d+)", text)
    if budget_match:
        budget = int(budget_match.group(1))

    return ProgramConfig(
        issue_id=issue_id,
        goal=goal,
        metric_command=metric_command,
        scope_files=scope_files,
        max_iterations=max_iter,
        token_budget=budget,
    )
