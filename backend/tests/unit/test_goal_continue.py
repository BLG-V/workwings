from __future__ import annotations

import pytest

from mawp.config.loader import AgentConfig
from mawp.goal.issues import IssuesService
from mawp.goal.models import IssueDocument, IssueStatus, PrdDocument, SpecDocument
from mawp.goal.store import GoalStore

from tests.e2e.conftest import setup_verify_workspace


def test_generate_continue_appends_new_step(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path), llm={"provider": "mock"})
    store = GoalStore(config)
    store.save_prd(
        PrdDocument(
            slug="feat",
            title="功能 A",
            description="实现功能 A",
            acceptance_criteria=["标准1", "标准2"],
        )
    )
    store.save_spec(
        SpecDocument(
            slug="feat",
            title="功能 A",
            prd_ref="feat",
            implementation_plan=["步骤一", "步骤二"],
        )
    )

    service = IssuesService(config)
    first, _ = service.generate_from_slug("feat")
    assert len(first) == 2
    assert first[0].id == "GW-001"
    assert first[1].id == "GW-002"
    assert first[1].depends_on == ["GW-001"]

    for doc in first:
        issue = store.load_issue(doc.id)
        issue.status = IssueStatus.DONE
        store.save_issue(issue)

    spec = store.load_spec("feat")
    spec.implementation_plan.append("步骤三")
    store.save_spec(spec)

    appended, _ = service.generate_continue("feat")
    assert len(appended) == 1
    assert appended[0].id == "GW-003"
    assert appended[0].title == "步骤三"
    assert appended[0].depends_on == ["GW-002"]

    again, _ = service.generate_continue("feat")
    assert again == []


def test_generate_continue_preserves_existing_ids(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    store = GoalStore(config)
    store.save_prd(
        PrdDocument(
            slug="feat",
            title="t",
            description="d",
            acceptance_criteria=["a"],
        )
    )
    store.save_spec(
        SpecDocument(
            slug="feat",
            title="t",
            prd_ref="feat",
            implementation_plan=["步骤一"],
        )
    )

    service = IssuesService(config)
    service.generate_from_slug("feat")
    spec = store.load_spec("feat")
    spec.implementation_plan.append("步骤二")
    store.save_spec(spec)

    appended, _ = service.generate_continue("feat")
    assert len(appended) == 1
    assert appended[0].id == "GW-002"
    assert store.load_issue("GW-001").title == "步骤一"
