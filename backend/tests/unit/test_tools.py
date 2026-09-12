from __future__ import annotations

from pathlib import Path

import pytest

from mawp.config.loader import load_config
from mawp.security.audit import AuditLogger, AuditResult
from mawp.security.policy import PolicyDenied, PolicyEngine
from mawp.tools.registry import ToolRegistry
from mawp.tools.types import ToolCallContext


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=bad\n", encoding="utf-8")
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "key.txt").write_text("key", encoding="utf-8")
    return tmp_path


@pytest.fixture
def registry(workspace: Path) -> ToolRegistry:
    config = load_config().model_copy(update={"workspace": str(workspace)})
    return ToolRegistry(config)


def test_read_file_success(registry: ToolRegistry) -> None:
    ctx = ToolCallContext(agent_name="requirement", session_id="s1")
    result = registry.execute("read_file", {"path": "src/app.py"}, ctx)
    assert result.success
    assert "hello" in result.data["content"]


def test_e2e_05_env_access_denied(registry: ToolRegistry) -> None:
    """E2E-05: 访问 .env 被拦截并审计。"""
    ctx = ToolCallContext(agent_name="requirement", session_id="s1", actor_id="dev-1")
    result = registry.execute("read_file", {"path": ".env"}, ctx)

    assert not result.success
    assert "禁止访问" in (result.error or "")

    logs = registry.audit.read_all()
    denied = [l for l in logs if l["result"] == AuditResult.DENIED.value]
    assert len(denied) >= 1
    assert denied[-1]["action"] == "tool.read_file"


def test_secrets_directory_denied(registry: ToolRegistry) -> None:
    ctx = ToolCallContext(agent_name="coding", session_id="s1")
    result = registry.execute(
        "read_file", {"path": "secrets/key.txt"}, ctx
    )
    assert not result.success


def test_requirement_cannot_write(registry: ToolRegistry) -> None:
    ctx = ToolCallContext(agent_name="requirement", session_id="s1")
    result = registry.execute(
        "write_file",
        {"path": "src/new.py", "content": "x = 1\n"},
        ctx,
    )
    assert not result.success
    assert "不可调用" in (result.error or "") or "无写权限" in (result.error or "")


def test_coding_write_and_edit(registry: ToolRegistry, workspace: Path) -> None:
    ctx = ToolCallContext(agent_name="coding", session_id="s1")

    write_result = registry.execute(
        "write_file",
        {"path": "src/new.py", "content": "value = 1\n"},
        ctx,
    )
    assert write_result.success
    assert (workspace / "src" / "new.py").is_file()

    edit_result = registry.execute(
        "edit_file",
        {"path": "src/new.py", "old_string": "1", "new_string": "2"},
        ctx,
    )
    assert edit_result.success
    assert "2" in (workspace / "src" / "new.py").read_text(encoding="utf-8")


def test_edit_file_handles_crlf_line_endings(
    registry: ToolRegistry, workspace: Path
) -> None:
    ctx = ToolCallContext(agent_name="coding", session_id="s1")
    target = workspace / "src" / "crlf.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    result = registry.execute(
        "edit_file",
        {
            "path": "src/crlf.py",
            "old_string": "    return a - b\n",
            "new_string": "    return a + b\n",
        },
        ctx,
    )
    assert result.success
    assert "return a + b" in target.read_text(encoding="utf-8")


def test_grep_finds_content(registry: ToolRegistry) -> None:
    ctx = ToolCallContext(agent_name="review", session_id="s1")
    result = registry.execute(
        "grep", {"pattern": "hello", "path": "src"}, ctx
    )
    assert result.success
    assert len(result.data["matches"]) >= 1


def test_blocked_command(registry: ToolRegistry) -> None:
    ctx = ToolCallContext(agent_name="testing", session_id="s1")
    result = registry.execute(
        "run_terminal_cmd",
        {"command": "git push --force origin main"},
        ctx,
    )
    assert not result.success
    assert "拦截" in (result.error or "")


def test_path_outside_workspace(registry: ToolRegistry) -> None:
    policy = registry.policy
    with pytest.raises(PolicyDenied):
        policy.check_read("../../etc/passwd")


def test_list_dir(registry: ToolRegistry) -> None:
    ctx = ToolCallContext(agent_name="requirement", session_id="s1")
    result = registry.execute("list_dir", {"path": "src"}, ctx)
    assert result.success
    paths = [e["path"] for e in result.data["entries"]]
    assert "src/app.py" in paths


def test_schemas_for_agent(registry: ToolRegistry) -> None:
    schemas = registry.schemas_for_agent("coding")
    names = {s["function"]["name"] for s in schemas}
    assert "write_file" in names
    assert "run_tests" not in names


def test_audit_logger(workspace: Path) -> None:
    config = load_config().model_copy(update={"workspace": str(workspace)})
    audit = AuditLogger.from_config(config)
    audit.log(
        actor_id="dev",
        action="tool.read_file",
        resource_type="tool",
        resource_id=".env",
        result=AuditResult.DENIED,
        metadata={"reason": "test"},
    )
    entries = audit.read_all()
    assert len(entries) == 1
    assert entries[0]["result"] == "DENIED"


def test_scope_blocks_out_of_scope_write(registry: ToolRegistry, workspace: Path) -> None:
    ctx = ToolCallContext(
        agent_name="coding",
        session_id="s1",
        scope_files=["src/auth/login.py"],
    )
    result = registry.execute(
        "write_file",
        {"path": "src/other.py", "content": "x = 1\n"},
        ctx,
    )
    assert not result.success
    assert "scope" in (result.error or "").lower() or "超出" in (result.error or "")


def test_scope_allows_tests_when_empty_scope(registry: ToolRegistry, workspace: Path) -> None:
    (workspace / "tests").mkdir(exist_ok=True)
    ctx = ToolCallContext(
        agent_name="coding",
        session_id="s1",
        scope_files=[],
    )
    result = registry.execute(
        "write_file",
        {"path": "tests/test_demo.py", "content": "def test_ok():\n    assert True\n"},
        ctx,
    )
    assert result.success
    assert (workspace / "tests" / "test_demo.py").is_file()
