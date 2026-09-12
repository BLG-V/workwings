from __future__ import annotations

import pytest

from mawp.config.loader import AgentConfig
from mawp.goal.models import IssueDocument, IssueStatus, PrdDocument, SpecDocument
from mawp.goal.store import GoalStore
from mawp.autoresearch.store import AutoresearchStore
from mawp.goal.loop import GoalLoopService
from mawp.gstack.eng_review import EngReviewService
from mawp.gstack.models import ReviewStatus
from mawp.web.models import StepStatus
from mawp.web.progress import WorkflowProgressService


def _seed_workflow(tmp_path) -> str:
    config = AgentConfig(workspace=str(tmp_path))
    store = GoalStore(config)
    slug = "email-login"
    store.save_prd(
        PrdDocument(
            slug=slug,
            title="邮箱登录",
            description="增加邮箱验证码登录",
            acceptance_criteria=["发送验证码"],
        )
    )
    store.save_spec(
        SpecDocument(
            slug=slug,
            title="邮箱登录",
            prd_ref=slug,
            architecture="auth 模块",
            testing_strategy="pytest",
            implementation_plan=["实现", "测试"],
        )
    )
    EngReviewService(config).review_spec(
        store.load_spec(slug),
        issue_id=slug,
    )
    store.save_issue(
        IssueDocument(
            id="GW-001",
            title="实现验证码",
            description="d",
            status=IssueStatus.DONE,
            prd_ref=slug,
            spec_ref=slug,
            verify_command="pytest -q",
        )
    )
    store.save_issue(
        IssueDocument(
            id="GW-002",
            title="补充测试",
            description="d",
            status=IssueStatus.OPEN,
            prd_ref=slug,
            spec_ref=slug,
            verify_command="pytest -q",
            depends_on=["GW-001"],
        )
    )
    return slug


def test_list_workflows(tmp_path) -> None:
    slug = _seed_workflow(tmp_path)
    service = WorkflowProgressService(AgentConfig(workspace=str(tmp_path)))
    workflows = service.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].slug == slug
    assert workflows[0].issue_total == 2


def test_workflow_detail_steps(tmp_path) -> None:
    slug = _seed_workflow(tmp_path)
    service = WorkflowProgressService(AgentConfig(workspace=str(tmp_path)))
    detail = service.get_workflow(slug)
    assert detail.title == "邮箱登录"
    assert len(detail.steps) == 6
    assert detail.steps[0].status == StepStatus.DONE  # prd
    assert detail.steps[1].status == StepStatus.DONE  # spec
    assert detail.eng_review_status == ReviewStatus.PASS.value
    assert detail.steps[3].status == StepStatus.IN_PROGRESS  # goal (GW-002 open)
    assert detail.reviewed_count == 0
    assert detail.approved_count == 0


def test_workflow_loop_checkpoint(tmp_path) -> None:
    slug = _seed_workflow(tmp_path)
    config = AgentConfig(workspace=str(tmp_path))
    GoalLoopService(config).save_checkpoint(slug, completed=["GW-001"])

    detail = WorkflowProgressService(config).get_workflow(slug)
    assert detail.loop_checkpoint is not None
    assert detail.loop_checkpoint.completed == ["GW-001"]


def test_issue_progress_resume_flag(tmp_path) -> None:
    slug = _seed_workflow(tmp_path)
    config = AgentConfig(workspace=str(tmp_path))
    AutoresearchStore(config).save_running_checkpoint(
        issue_id="GW-002",
        next_iteration=3,
        total_tokens=0,
        feedback={},
        iterations_completed=2,
    )

    service = WorkflowProgressService(config)
    issues = {i.id: i for i in service.get_workflow(slug).issues}
    assert issues["GW-002"].resume_available is True
    assert issues["GW-002"].resume_from_iteration == 3


def test_get_issue_detail(tmp_path) -> None:
    _seed_workflow(tmp_path)
    service = WorkflowProgressService(AgentConfig(workspace=str(tmp_path)))
    data = service.get_issue("GW-001")
    assert data["issue"]["id"] == "GW-001"
    assert data["issue"]["status"] == "done"


@pytest.fixture
def web_client(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from mawp.api.app import create_app

    _seed_workflow(tmp_path)
    config = AgentConfig(workspace=str(tmp_path))
    app = create_app(config)
    return TestClient(app)


def test_api_health(web_client) -> None:
    res = web_client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_workflows(web_client) -> None:
    res = web_client.get("/api/workflows")
    assert res.status_code == 200
    data = res.json()
    assert len(data["workflows"]) == 1
    assert data["workflows"][0]["slug"] == "email-login"


def test_api_workflow_detail(web_client) -> None:
    res = web_client.get("/api/workflows/email-login")
    assert res.status_code == 200
    data = res.json()
    assert data["slug"] == "email-login"
    assert len(data["steps"]) == 6
    assert len(data["issues"]) == 2
    assert "loop_checkpoint" in data
    assert "reviewed_count" in data


def test_api_index_html(web_client) -> None:
    res = web_client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
