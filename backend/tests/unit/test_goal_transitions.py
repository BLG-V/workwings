from __future__ import annotations

import pytest

from mawp.config.loader import AgentConfig
from mawp.goal.models import IssueDocument, IssueStatus
from mawp.goal.transitions import (
    InvalidTransitionError,
    assert_can_review,
    assert_can_ship,
)


def test_assert_can_review_requires_done() -> None:
    issue = IssueDocument(
        id="GW-001",
        title="t",
        description="d",
        status=IssueStatus.OPEN,
    )
    with pytest.raises(InvalidTransitionError, match="review"):
        assert_can_review(issue)


def test_assert_can_review_allows_done() -> None:
    issue = IssueDocument(
        id="GW-001",
        title="t",
        description="d",
        status=IssueStatus.DONE,
    )
    assert_can_review(issue)


def test_assert_can_ship_requires_reviewed() -> None:
    issue = IssueDocument(
        id="GW-001",
        title="t",
        description="d",
        status=IssueStatus.DONE,
    )
    with pytest.raises(InvalidTransitionError, match="ship"):
        assert_can_ship(issue)
