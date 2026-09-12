from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IssueStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    REVIEWED = "reviewed"


class PrdDocument(BaseModel):
    slug: str
    title: str
    description: str
    goals: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    user_stories: list[str] = Field(default_factory=list)
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    affected_modules: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    body: str = ""

    def to_markdown(self) -> str:
        from mawp.goal.templates import render_prd

        return render_prd(self)


class SpecDocument(BaseModel):
    slug: str
    title: str
    prd_ref: str
    architecture: str = ""
    api_contracts: str = ""
    data_model: str = ""
    error_handling: str = ""
    security: str = ""
    testing_strategy: str = ""
    implementation_plan: list[str] = Field(default_factory=list)
    body: str = ""

    def to_markdown(self) -> str:
        from mawp.goal.templates import render_spec

        return render_spec(self)


class IssueDocument(BaseModel):
    id: str
    title: str
    description: str
    status: IssueStatus = IssueStatus.OPEN
    priority: str = "P0"
    depends_on: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    verify_command: str = ""
    scope_files: list[str] = Field(default_factory=list)
    prd_ref: str = ""
    spec_ref: str = ""
    body: str = ""

    def to_markdown(self) -> str:
        from mawp.goal.templates import render_issue

        return render_issue(self)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
