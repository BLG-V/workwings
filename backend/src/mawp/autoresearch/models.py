from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IterationStatus(str, Enum):
    KEEP = "keep"
    DISCARD = "discard"


class ProgramConfig(BaseModel):
    issue_id: str
    goal: str
    metric_command: str
    scope_files: list[str] = Field(default_factory=list)
    deny_files: list[str] = Field(default_factory=list)
    max_iterations: int = 25
    token_budget: int = 500_000

    def to_markdown(self) -> str:
        from mawp.autoresearch.templates import render_program

        return render_program(self)


class IterationRecord(BaseModel):
    iteration: int
    issue_id: str
    status: IterationStatus
    metric_command: str
    exit_code: int
    passed: bool
    duration_ms: int
    commit_sha: str = ""
    error_summary: str = ""
    tokens_used: int = 0
    files_changed: list[str] = Field(default_factory=list)
    diff_summary: str = ""

    def to_jsonl_line(self) -> str:
        import json

        return json.dumps(self.model_dump(), ensure_ascii=False)


class LoopResult(BaseModel):
    success: bool
    issue_id: str
    iterations: int
    passed_at: int | None = None
    commit_sha: str = ""
    blocked_reason: str = ""
    blocked_report_path: str = ""
    records: list[IterationRecord] = Field(default_factory=list)
    coding_output: dict[str, Any] = Field(default_factory=dict)
