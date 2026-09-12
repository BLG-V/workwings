from __future__ import annotations

import pytest

from mawp.config.loader import AgentConfig
from mawp.goal.issues import IssuesService
from mawp.goal.models import IssueStatus
from mawp.goal.prd import PrdService, _spec_to_prd
from mawp.goal.slug import make_slug
from mawp.goal.spec import SpecService, _heuristic_spec
from mawp.goal.store import GoalStore
from mawp.agents.requirement import RequirementSpec


def test_make_slug_from_chinese_description() -> None:
    slug = make_slug("为用户模块增加邮箱验证码登录")
    assert slug
    assert " " not in slug
    assert "email" in slug or "login" in slug or slug.startswith("feature-")


def test_make_slug_from_english() -> None:
    assert make_slug("Add email verification login") == "add-email-verification-login"


def test_goal_store_init_layout(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    store = GoalStore(config)
    base = store.init_layout()
    assert base.is_dir()
    assert (base / "prd").is_dir()
    assert (base / "spec").is_dir()
    assert (base / "issues").is_dir()


def test_prd_roundtrip(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path), llm={"provider": "mock"})
    store = GoalStore(config)
    spec = RequirementSpec(
        summary="邮箱验证码登录",
        goals=["提供验证码登录"],
        non_goals=["短信登录"],
        acceptance_criteria=["发送验证码", "验证码校验通过"],
        affected_modules=["auth"],
        related_files=["src/auth/login.py"],
        open_questions=[],
        tasks=[],
    )
    doc = _spec_to_prd("email-login", "为用户增加邮箱验证码登录", spec)
    assert doc.user_stories
    assert doc.functional_requirements
    assert doc.non_functional_requirements
    assert doc.non_goals
    path = store.save_prd(doc)
    assert path.is_file()

    loaded = store.load_prd("email-login")
    assert loaded.title == "邮箱验证码登录"
    assert "auth" in loaded.affected_modules
    assert len(loaded.acceptance_criteria) == 2


def test_prd_service_generate(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path), llm={"provider": "mock"})
    service = PrdService(config)
    doc, path = service.generate("实现用户 JWT 登录 API")
    assert doc.slug
    assert path.endswith(".md") or str(path).endswith(".md")
    assert store_prd_exists(config, doc.slug)


def store_prd_exists(config: AgentConfig, slug: str) -> bool:
    return GoalStore(config).prd_exists(slug)


def test_spec_heuristic_from_prd(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path), llm={"provider": "mock"})
    store = GoalStore(config)
    from mawp.goal.models import PrdDocument

    prd = PrdDocument(
        slug="email-login",
        title="邮箱登录",
        description="增加邮箱验证码登录",
        goals=["验证码登录"],
        acceptance_criteria=["发送验证码成功"],
        affected_modules=["auth"],
        related_files=["src/auth/login.py"],
    )
    store.save_prd(prd)

    service = SpecService(config)
    doc, path = service.generate("email-login")
    assert doc.slug == "email-login"
    assert doc.architecture
    assert len(doc.implementation_plan) >= 1
    assert path


def test_issues_from_spec_plan(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path), llm={"provider": "mock"})
    store = GoalStore(config)
    from mawp.goal.models import PrdDocument, SpecDocument

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
    docs, paths = service.generate_from_slug("feat")
    assert len(docs) == 2
    assert docs[0].id == "GW-001"
    assert docs[1].depends_on == ["GW-001"]
    assert all(paths)


def test_issues_quick_track(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    service = IssuesService(config)
    doc, path = service.generate_quick("修复 src/auth/login.py 的 JWT 过期问题")
    assert doc.id == "GW-001"
    assert doc.status == IssueStatus.OPEN
    assert "pytest" in doc.verify_command
    assert "src/auth/login.py" in doc.scope_files


def test_next_issue_id_increments(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path))
    store = GoalStore(config)
    assert store.next_issue_id() == "GW-001"

    from mawp.goal.models import IssueDocument

    store.save_issue(
        IssueDocument(
            id="GW-001",
            title="t1",
            description="d1",
        )
    )
    assert store.next_issue_id() == "GW-002"


def test_prd_duplicate_raises(tmp_path) -> None:
    config = AgentConfig(workspace=str(tmp_path), llm={"provider": "mock"})
    service = PrdService(config)
    service.generate("登录功能", slug="login")
    with pytest.raises(FileExistsError):
        service.generate("另一个登录", slug="login")
