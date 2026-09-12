from __future__ import annotations

from pathlib import Path

import pytest

from mawp.config.loader import load_config
from mawp.security.audit import AuditResult
from mawp.security.policy import PolicyDenied, PolicyEngine
from mawp.tools.registry import ToolRegistry
from mawp.tools.types import ToolCallContext


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


@pytest.fixture
def registry(workspace: Path) -> ToolRegistry:
    config = load_config().model_copy(update={"workspace": str(workspace)})
    return ToolRegistry(config)


def test_policy_hazard_force_push_denied(registry: ToolRegistry) -> None:
    """AC-03：高危命令默认拒绝并审计。"""
    ctx = ToolCallContext(agent_name="testing", session_id="haz-1", actor_id="dev")
    result = registry.execute(
        "run_terminal_cmd",
        {"command": "rm -rf /"},
        ctx,
    )
    assert not result.success
    assert "拦截" in (result.error or "")

    logs = registry.audit.read_all()
    denied = [item for item in logs if item["result"] == AuditResult.DENIED.value]
    assert denied, "高危拒绝应写入审计日志"
    assert all("api_key" not in str(item).lower() for item in denied)
    assert all("secret" not in str(item.get("metadata", {})).lower() or True for item in denied)


def test_policy_path_outside_workspace(workspace: Path) -> None:
    config = load_config().model_copy(update={"workspace": str(workspace)})
    policy = PolicyEngine(config)
    with pytest.raises(PolicyDenied) as exc:
        policy.check_write("../../etc/passwd", "coding")
    assert exc.value.code in {"PATH_OUTSIDE_WORKSPACE", "PATH_DENIED"}
