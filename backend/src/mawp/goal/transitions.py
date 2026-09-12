from __future__ import annotations

from mawp.goal.models import IssueDocument, IssueStatus

# 允许的状态迁移（action → 目标状态前置条件）
_REVIEWABLE = frozenset({IssueStatus.DONE})
_SHIPPABLE = frozenset({IssueStatus.REVIEWED})


class InvalidTransitionError(ValueError):
    """Issue 状态不符合当前操作。"""

    def __init__(self, issue_id: str, action: str, current: IssueStatus, expected: str):
        self.issue_id = issue_id
        self.action = action
        self.current = current
        super().__init__(
            f"Issue {issue_id} 当前状态为 {current.value}，"
            f"不可执行 {action}（需要: {expected}）"
        )


def assert_can_review(issue: IssueDocument) -> None:
    if issue.status not in _REVIEWABLE:
        raise InvalidTransitionError(
            issue.id,
            "review",
            issue.status,
            "done（须先通过 agent goal 完成实现）",
        )


def assert_can_ship(issue: IssueDocument) -> None:
    if issue.status not in _SHIPPABLE:
        raise InvalidTransitionError(
            issue.id,
            "ship",
            issue.status,
            "reviewed（须先通过 agent review）",
        )


def transition_after_goal_success(issue: IssueDocument) -> IssueStatus:
    return IssueStatus.DONE


def transition_after_goal_blocked(issue: IssueDocument) -> IssueStatus:
    return IssueStatus.BLOCKED


def transition_after_review_pass(issue: IssueDocument) -> IssueStatus:
    return IssueStatus.REVIEWED


def transition_after_ship(issue: IssueDocument) -> IssueStatus:
    return IssueStatus.DONE
