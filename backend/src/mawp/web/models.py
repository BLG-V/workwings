from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class WorkflowStep(BaseModel):
    key: str
    label: str
    status: StepStatus
    detail: str = ""


class IssueProgress(BaseModel):
    id: str
    title: str
    status: str
    priority: str = "P0"
    verify_command: str = ""
    review_status: str | None = None
    qa_status: str | None = None
    iteration_count: int = 0
    last_iteration_status: str | None = None
    blocking_count: int = 0
    resume_available: bool = False
    resume_from_iteration: int | None = None
    approved: bool = False


class LoopCheckpoint(BaseModel):
    slug: str
    completed: list[str] = Field(default_factory=list)
    last_completed: str | None = None
    updated_at: str | None = None


class WorkflowSummary(BaseModel):
    slug: str
    title: str
    current_step: str
    progress_percent: int
    issue_total: int
    issue_done: int
    archived: bool = False


class WorkflowDetail(BaseModel):
    slug: str
    title: str
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    issues: list[IssueProgress] = Field(default_factory=list)
    eng_review_status: str | None = None
    archived: bool = False
    archive_path: str | None = None
    loop_checkpoint: LoopCheckpoint | None = None
    approved_count: int = 0
    reviewed_count: int = 0

    @property
    def current_step(self) -> str:
        for step in self.steps:
            if step.status in (StepStatus.IN_PROGRESS, StepStatus.BLOCKED, StepStatus.PENDING):
                return step.key
        return "ship"
