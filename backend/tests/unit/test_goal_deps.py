from __future__ import annotations

import pytest

from mawp.config.loader import AgentConfig
from mawp.goal.deps import (
    DependencyCycleError,
    DependencyNotReadyError,
    IssueNotRunnableError,
    assert_dependencies_met,
    assert_issue_runnable,
    assert_ready_for_goal,
    validate_dag,
)
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore


def _issue(
    issue_id: str,
    *,
    depends_on: list[str] | None = None,
    status: IssueStatus = IssueStatus.OPEN,
) -> IssueDocument:
    return IssueDocument(
        id=issue_id,
        title=issue_id,
        description="desc",
        status=status,
        depends_on=depends_on or [],
    )


def test_validate_dag_topological_order() -> None:
    issues = [
        _issue("GW-001"),
        _issue("GW-002", depends_on=["GW-001"]),
        _issue("GW-003", depends_on=["GW-002"]),
    ]
    ordered = validate_dag(issues)
    assert [i.id for i in ordered] == ["GW-001", "GW-002", "GW-003"]


def test_validate_dag_detects_cycle() -> None:
    issues = [
        _issue("GW-001", depends_on=["GW-002"]),
        _issue("GW-002", depends_on=["GW-001"]),
    ]
    with pytest.raises(DependencyCycleError):
        validate_dag(issues)


def test_validate_dag_unknown_dependency() -> None:
    issues = [_issue("GW-001", depends_on=["GW-999"])]
    with pytest.raises(ValueError, match="未知 Issue"):
        validate_dag(issues)


def test_assert_dependencies_met(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    store = GoalStore(config)
    store.save_issue(_issue("GW-001", status=IssueStatus.DONE))
    store.save_issue(_issue("GW-002", depends_on=["GW-001"]))

    assert_dependencies_met(store.load_issue("GW-002"), store)


def test_assert_dependencies_not_ready(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    store = GoalStore(config)
    store.save_issue(_issue("GW-001", status=IssueStatus.OPEN))
    store.save_issue(_issue("GW-002", depends_on=["GW-001"]))

    with pytest.raises(DependencyNotReadyError) as exc:
        assert_dependencies_met(store.load_issue("GW-002"), store)
    assert exc.value.pending == ["GW-001"]


def test_assert_issue_not_runnable_when_reviewed() -> None:
    with pytest.raises(IssueNotRunnableError):
        assert_issue_runnable(_issue("GW-001", status=IssueStatus.REVIEWED))


def test_assert_ready_for_goal(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    store = GoalStore(config)
    store.save_issue(_issue("GW-001", status=IssueStatus.DONE))
    issue = _issue("GW-002", depends_on=["GW-001"])
    store.save_issue(issue)

    assert_ready_for_goal(store.load_issue("GW-002"), store)
