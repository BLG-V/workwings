from __future__ import annotations

import pytest

from mawp.autoresearch.loop import AutoresearchLoop
from mawp.autoresearch.program import ProgramService
from mawp.autoresearch.store import AutoresearchStore
from mawp.config.loader import AgentConfig
from mawp.goal.loop import GoalLoopService
from mawp.gstack.models import ReviewStatus
from mawp.gstack.pipeline import ReviewPipeline
from mawp.goal.approve import ApproveService
from mawp.goal.deps import assert_ready_for_goal
from mawp.goal.issues import IssuesService
from mawp.goal.models import IssueDocument, IssueStatus, PrdDocument, SpecDocument
from mawp.goal.prd import PrdService
from mawp.goal.ship import ShipService
from mawp.goal.spec import SpecService
from mawp.goal.store import GoalStore
from mawp.security.audit import AuditLogger, AuditResult

from mawp.llm.mock import MockLLMAdapter

from tests.e2e.conftest import (
    build_fail_then_pass_llm,
    build_secrets_probe_then_fix_llm,
    demo_marker_content,
    patch_mock_llm,
    setup_secrets_workspace,
    setup_verify_workspace,
)


def _configure_issue_for_goal(config: AgentConfig, issue_id: str, verify_cmd: str) -> None:
    store = GoalStore(config)
    issue = store.load_issue(issue_id)
    issue.verify_command = verify_cmd
    issue.scope_files = ["src/demo.py"]
    store.save_issue(issue)


def _run_goal(config: AgentConfig, issue_id: str):
    store = GoalStore(config)
    issue = store.load_issue(issue_id)
    assert_ready_for_goal(issue, store)
    program_service = ProgramService(config)
    program, _ = program_service.from_issue(issue)
    return AutoresearchLoop(config).run_for_issue(issue, program)


def _review_approve_ship(config: AgentConfig, issue_id: str):
    review = ReviewPipeline(config).run(issue_id, auto_fix=False)
    assert review.passed, review.blocking_findings
    ApproveService(config).approve(issue_id)
    return ShipService(config).ship(issue_id)


def test_e2e_01_full_six_step_workflow(e2e_config: AgentConfig) -> None:
    """E2E-01: prd → spec → issues → goal → review → approve → ship。"""
    config = e2e_config
    workspace = config.workspace_path()
    verify_cmd = setup_verify_workspace(workspace)

    GoalStore(config).init_layout()
    prd_doc, _ = PrdService(config).generate("为用户模块增加 demo 标记功能")
    SpecService(config).generate(prd_doc.slug)
    docs, _ = IssuesService(config).generate_from_slug(prd_doc.slug)
    assert docs
    issue_id = docs[0].id
    _configure_issue_for_goal(config, issue_id, verify_cmd)

    goal_result = _run_goal(config, issue_id)
    assert goal_result.success is True

    reloaded = GoalStore(config).load_issue(issue_id)
    assert reloaded.status == IssueStatus.DONE

    archive_dir, summary = _review_approve_ship(config, issue_id)
    assert archive_dir.is_dir()
    assert (archive_dir / "PR.md").is_file()
    assert (archive_dir / "COMMIT_MSG.txt").is_file()
    assert (archive_dir / "approve.json").is_file()
    assert issue_id in summary


def test_e2e_04_blocking_review_prevents_ship(e2e_config: AgentConfig) -> None:
    """E2E-04: review BLOCKED 时 ship 被拒绝。"""
    config = e2e_config
    setup_verify_workspace(config.workspace_path())

    store = GoalStore(config)
    store.save_issue(
        IssueDocument(
            id="GW-040",
            title="无法通过 QA",
            description="验证始终失败",
            status=IssueStatus.DONE,
            verify_command='python -c "import sys; sys.exit(1)"',
            scope_files=["src/demo.py"],
        )
    )

    result = ReviewPipeline(config).run("GW-040", auto_fix=False)
    assert result.status == ReviewStatus.BLOCKED
    assert result.passed is False

    reloaded = store.load_issue("GW-040")
    assert reloaded.status == IssueStatus.DONE

    with pytest.raises(PermissionError, match="agent review"):
        ShipService(config).ship("GW-040")


def test_e2e_06_quick_track_bug_fix(e2e_config: AgentConfig) -> None:
    """E2E-06: --quick 快速通道跳过 prd/spec，仍须 review + approve。"""
    config = e2e_config
    verify_cmd = setup_verify_workspace(config.workspace_path())

    doc, _ = IssuesService(config).generate_quick(
        "修复 src/demo.py 的 agent-generated 标记缺失"
    )
    _configure_issue_for_goal(config, doc.id, verify_cmd)

    goal_result = _run_goal(config, doc.id)
    assert goal_result.success is True

    logs = AutoresearchStore(config).load_results(issue_id=doc.id)
    assert len(logs) >= 1
    assert logs[-1]["status"] == "keep"

    archive_dir, _ = _review_approve_ship(config, doc.id)
    assert (archive_dir / "SHIP.md").is_file()
    assert GoalStore(config).load_issue(doc.id).status == IssueStatus.DONE


def test_e2e_02_autoresearch_fail_then_pass(e2e_config: AgentConfig, monkeypatch) -> None:
    """E2E-02: autoresearch 先 discard 后 keep，results.jsonl 有完整记录。"""
    config = e2e_config
    workspace = config.workspace_path()
    verify_cmd = setup_verify_workspace(workspace)
    patch_mock_llm(monkeypatch, build_fail_then_pass_llm())

    store = GoalStore(config)
    store.save_issue(
        IssueDocument(
            id="GW-002",
            title="先失败后通过",
            description="第一轮 verify 失败，第二轮修复通过",
            status=IssueStatus.OPEN,
            verify_command=verify_cmd,
            scope_files=["src/demo.py"],
        )
    )

    goal_result = _run_goal(config, "GW-002")
    assert goal_result.success is True
    assert goal_result.passed_at == 2
    assert len(goal_result.records) == 2
    assert goal_result.records[0].status.value == "discard"
    assert goal_result.records[1].status.value == "keep"

    logs = AutoresearchStore(config).load_results(issue_id="GW-002")
    assert len(logs) == 2
    assert logs[0]["status"] == "discard"
    assert logs[1]["status"] == "keep"
    assert "agent-generated" in (workspace / "src" / "demo.py").read_text(encoding="utf-8")


def test_e2e_05_secrets_access_blocked_during_goal(
    e2e_config: AgentConfig,
    monkeypatch,
) -> None:
    """E2E-05: goal 阶段访问 secrets/.env 被拦截，scope 内修复仍可成功。"""
    config = e2e_config
    workspace = config.workspace_path()
    verify_cmd = setup_verify_workspace(workspace)
    setup_secrets_workspace(workspace)
    patch_mock_llm(monkeypatch, build_secrets_probe_then_fix_llm())

    store = GoalStore(config)
    store.save_issue(
        IssueDocument(
            id="GW-005",
            title="secrets 防护",
            description="不得读取 secrets，仅在 src/demo.py 修复",
            status=IssueStatus.OPEN,
            verify_command=verify_cmd,
            scope_files=["src/demo.py"],
        )
    )

    goal_result = _run_goal(config, "GW-005")
    assert goal_result.success is True
    assert (workspace / "secrets" / "key.txt").read_text(encoding="utf-8") == "SUPER_SECRET\n"
    assert not (workspace / "secrets" / "evil.py").exists()

    audit = AuditLogger.from_config(config)
    denied = [
        entry
        for entry in audit.read_all()
        if entry["result"] == AuditResult.DENIED.value
    ]
    denied_paths = {entry["resource_id"] for entry in denied}
    assert "secrets/key.txt" in denied_paths
    assert "secrets/evil.py" in denied_paths


def test_e2e_03_continue_appends_incremental_issues(e2e_config: AgentConfig) -> None:
    """E2E-03: 多轮 issues --continue 增量追加新 Issue，依赖链正确。"""
    config = e2e_config
    store = GoalStore(config)

    store.save_prd(
        PrdDocument(
            slug="feat",
            title="迭代功能",
            description="支持增量拆解",
            acceptance_criteria=["步骤一", "步骤二"],
        )
    )
    store.save_spec(
        SpecDocument(
            slug="feat",
            title="迭代功能",
            prd_ref="feat",
            implementation_plan=["步骤一", "步骤二"],
        )
    )

    service = IssuesService(config)
    initial, _ = service.generate_from_slug("feat")
    assert [doc.id for doc in initial] == ["GW-001", "GW-002"]

    for doc in initial:
        issue = store.load_issue(doc.id)
        issue.status = IssueStatus.DONE
        store.save_issue(issue)

    spec = store.load_spec("feat")
    spec.implementation_plan.append("步骤三")
    store.save_spec(spec)

    appended, paths = service.generate_continue("feat")
    assert len(appended) == 1
    assert appended[0].id == "GW-003"
    assert appended[0].depends_on == ["GW-002"]
    assert paths

    assert service.generate_continue("feat")[0] == []


def test_e2e_07_autoresearch_resume_from_checkpoint(
    e2e_config: AgentConfig,
    monkeypatch,
) -> None:
    """E2E-07: autoresearch 中断后可从 iteration N 恢复。"""
    config = e2e_config
    verify_cmd = setup_verify_workspace(config.workspace_path())
    store = GoalStore(config)
    store.save_issue(
        IssueDocument(
            id="GW-070",
            title="中断恢复",
            description="第 1 轮 discard，恢复后通过",
            status=IssueStatus.OPEN,
            verify_command=verify_cmd,
            scope_files=["src/demo.py"],
        )
    )

    loop = AutoresearchLoop(config)
    program, _ = ProgramService(config).from_issue(store.load_issue("GW-070"))
    patch_mock_llm(
        monkeypatch,
        MockLLMAdapter(
            [
                MockLLMAdapter.json_response(
                    {
                        "change_plan": [],
                        "files_changed": [],
                        "changelog": "第 1 轮无变更",
                    }
                )
            ]
        ),
    )

    original_save = loop._save_running_checkpoint

    def interrupt_after_first(*args, **kwargs):
        original_save(*args, **kwargs)
        raise InterruptedError("simulated interrupt")

    monkeypatch.setattr(loop, "_save_running_checkpoint", interrupt_after_first)

    with pytest.raises(InterruptedError):
        loop.run_for_issue(store.load_issue("GW-070"), program)

    assert loop.can_resume("GW-070")
    patch_mock_llm(monkeypatch, build_fail_then_pass_llm())
    # build_fail_then_pass has discard+json then success - but we need only success on iter 2
    patch_mock_llm(
        monkeypatch,
        MockLLMAdapter(
            [
                MockLLMAdapter.tool_call_response(
                    "c1",
                    "write_file",
                    {"path": "src/demo.py", "content": demo_marker_content()},
                ),
                MockLLMAdapter.json_response(
                    {
                        "change_plan": [],
                        "files_changed": ["src/demo.py"],
                        "changelog": "恢复后修复",
                    }
                ),
            ]
        ),
    )

    result = loop.resume_for_issue("GW-070")
    assert result.success is True
    assert result.passed_at == 2


def test_e2e_08_batch_loop_multiple_issues(e2e_config: AgentConfig, monkeypatch) -> None:
    """E2E-08: agent loop 按依赖顺序批量完成多个 Issue。"""
    config = e2e_config
    verify_cmd = setup_verify_workspace(config.workspace_path())
    store = GoalStore(config)

    for idx, dep in enumerate([[], ["GW-001"], ["GW-002"]], start=1):
        store.save_issue(
            IssueDocument(
                id=f"GW-00{idx}",
                title=f"步骤 {idx}",
                description=f"实现步骤 {idx}",
                status=IssueStatus.OPEN,
                verify_command=verify_cmd,
                scope_files=["src/demo.py"],
                depends_on=dep,
                prd_ref="batch-feat",
                spec_ref="batch-feat",
            )
        )

    from mawp.goal.loop import GoalLoopService

    result = GoalLoopService(config).run("batch-feat", resume=False)
    assert result.success is True
    assert result.completed == ["GW-001", "GW-002", "GW-003"]

    for issue_id in result.completed:
        assert store.load_issue(issue_id).status == IssueStatus.DONE
