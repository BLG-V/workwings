# A 侧对齐结论（王振同）— 冻结后供 D/C 同步
#
# 基于 docs/w3-ad-yaml-align.md 四个问题的拍板：
# 1. when: default 字面量 — 接受（validate 强制恰好一条）
# 2. reject — 沿 human 唯一出边继续（样例 after_human）；写入 outputs.decision=reject
# 3. platform run 停在 WAITING_USER — exit code 0（合法暂停）
# 4. validate — condition 出边必须含且仅含一条 when: default
#
# 实现分支：feat/a-w3-condition-human
# 接口依据：docs/interfaces/w1-api-onepager.md §5

from __future__ import annotations

from pathlib import Path

import pytest

from mawp.config.loader import load_config
from mawp.core.engine import IllegalStateError, WorkflowEngine
from mawp.core.loader import load_workflow
from mawp.core.validate import validate_workflow


BRANCH = Path("examples/branch-human/workflow.yaml")


@pytest.fixture
def engine(tmp_path: Path) -> WorkflowEngine:
    config = load_config().model_copy(update={"workspace": str(tmp_path)})
    return WorkflowEngine(config)


def test_branch_human_validate_ok() -> None:
    wf = load_workflow(BRANCH)
    assert validate_workflow(wf) == []


def test_p0_high_risk_pauses_then_approve(engine: WorkflowEngine) -> None:
    run = engine.run(BRANCH)
    assert run.status == "WAITING_USER"
    assert run.current_node_id == "approve_deploy"
    assert run.checkpoint is not None
    assert "risk=high" in (run.checkpoint.get("reason") or "")
    assert (engine.store.checkpoints_dir / f"{run.run_id}.json").is_file()

    run = engine.resume(run.run_id, "approve")
    assert run.status == "DONE"
    assert run.node_outputs["approve_deploy"]["decision"] == "approve"
    assert "human decision=approve" in (
        run.node_outputs.get("after_human") or {}
    ).get("text", "")


def test_p0_low_risk_auto_ok(engine: WorkflowEngine) -> None:
    run = engine.run(BRANCH, params_override={"risk": "low"})
    assert run.status == "DONE"
    assert "auto_ok" in run.node_outputs
    assert "approve_deploy" not in run.node_outputs


def test_p0_reject_continues_with_decision(engine: WorkflowEngine) -> None:
    run = engine.run(BRANCH)
    run = engine.resume(run.run_id, "reject")
    assert run.status == "DONE"
    assert run.node_outputs["approve_deploy"]["decision"] == "reject"


def test_p0_input_writes_outputs(engine: WorkflowEngine) -> None:
    run = engine.run(BRANCH)
    run = engine.resume(run.run_id, "input", data={"text": "改期明天"})
    assert run.status == "DONE"
    assert run.node_outputs["approve_deploy"]["decision"] == "input"
    assert run.node_outputs["approve_deploy"]["input"] == "改期明天"


def test_p0_duplicate_resume_illegal(engine: WorkflowEngine) -> None:
    run = engine.run(BRANCH)
    run = engine.resume(run.run_id, "approve")
    with pytest.raises(IllegalStateError):
        engine.resume(run.run_id, "approve")
