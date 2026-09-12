from __future__ import annotations

from collections import deque

from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.store import GoalStore

_READY_DEPENDENCY_STATUSES = frozenset({IssueStatus.DONE, IssueStatus.REVIEWED})
_RUNNABLE_STATUSES = frozenset(
    {IssueStatus.OPEN, IssueStatus.BLOCKED, IssueStatus.IN_PROGRESS}
)


class DependencyCycleError(ValueError):
    """Issue 依赖图存在环。"""

    def __init__(self, involved: list[str]):
        self.involved = involved
        super().__init__(f"Issue 依赖存在环: {' → '.join(involved)}")


class DependencyNotReadyError(ValueError):
    """前置 Issue 尚未完成。"""

    def __init__(self, issue_id: str, pending: list[str]):
        self.issue_id = issue_id
        self.pending = pending
        super().__init__(
            f"Issue {issue_id} 依赖未满足，须先完成: {', '.join(pending)}"
        )


class IssueNotRunnableError(ValueError):
    """Issue 当前状态不可进入 goal 实现。"""

    def __init__(self, issue_id: str, status: IssueStatus):
        self.issue_id = issue_id
        self.status = status
        super().__init__(
            f"Issue {issue_id} 状态为 {status.value}，不可执行 goal "
            f"（允许: open / blocked / in_progress）"
        )


def validate_dag(issues: list[IssueDocument]) -> list[IssueDocument]:
    """校验依赖无环，返回拓扑排序后的 Issue 列表。"""
    if not issues:
        return []

    ids = {issue.id for issue in issues}
    for issue in issues:
        for dep in issue.depends_on:
            if dep not in ids:
                raise ValueError(
                    f"Issue {issue.id} 依赖未知 Issue {dep}（不在本次拆解批次内）"
                )

    indegree: dict[str, int] = {issue.id: 0 for issue in issues}
    adjacency: dict[str, list[str]] = {issue.id: [] for issue in issues}
    by_id = {issue.id: issue for issue in issues}

    for issue in issues:
        for dep in issue.depends_on:
            adjacency[dep].append(issue.id)
            indegree[issue.id] += 1

    queue: deque[str] = deque(
        issue_id for issue_id, degree in indegree.items() if degree == 0
    )
    ordered_ids: list[str] = []

    while queue:
        node = queue.popleft()
        ordered_ids.append(node)
        for neighbor in adjacency[node]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered_ids) != len(issues):
        remaining = [issue_id for issue_id, deg in indegree.items() if deg > 0]
        raise DependencyCycleError(remaining)

    return [by_id[issue_id] for issue_id in ordered_ids]


def assert_issue_runnable(
    issue: IssueDocument,
    *,
    allow_done_rework: bool = False,
) -> None:
    allowed = set(_RUNNABLE_STATUSES)
    if allow_done_rework:
        allowed.add(IssueStatus.DONE)
    if issue.status not in allowed:
        raise IssueNotRunnableError(issue.id, issue.status)


def assert_dependencies_met(issue: IssueDocument, store: GoalStore) -> None:
    pending: list[str] = []
    for dep_id in issue.depends_on:
        try:
            dep = store.load_issue(dep_id)
        except FileNotFoundError as exc:
            raise ValueError(
                f"Issue {issue.id} 依赖 {dep_id} 不存在"
            ) from exc
        if dep.status not in _READY_DEPENDENCY_STATUSES:
            pending.append(dep_id)
    if pending:
        raise DependencyNotReadyError(issue.id, pending)


def assert_ready_for_goal(
    issue: IssueDocument,
    store: GoalStore,
    *,
    allow_done_rework: bool = False,
) -> None:
    """goal 启动前门禁：状态合法且依赖已满足。"""
    assert_issue_runnable(issue, allow_done_rework=allow_done_rework)
    if not allow_done_rework:
        assert_dependencies_met(issue, store)
