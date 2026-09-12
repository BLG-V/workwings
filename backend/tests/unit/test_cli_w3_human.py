"""C · W3 CLI：approve/reject/input/status 与等待提示（不改引擎）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mawp.cli.display import duration_label, next_step_commands
from mawp.cli.main import app
from mawp.storage.store import RunRecord

BRANCH = Path("examples/branch-human/workflow.yaml")
runner = CliRunner()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    example = Path("mawp.config.yaml.example")
    cfg = tmp_path / "mawp.config.yaml"
    text = example.read_text(encoding="utf-8")
    text = text.replace('workspace: "."', f'workspace: "{tmp_path.as_posix()}"')
    cfg.write_text(text, encoding="utf-8")
    return tmp_path


def _invoke(workspace: Path, *args: str):
    cfg = workspace / "mawp.config.yaml"
    return runner.invoke(app, ["--config", str(cfg), *args])


def test_next_step_commands_include_run_id() -> None:
    cmds = next_step_commands("abc123", ["approve", "input"])
    assert cmds[0] == "platform approve abc123"
    assert 'platform input abc123 --text "..."' in cmds


def test_duration_label_basic() -> None:
    record = RunRecord(
        run_id="r1",
        workflow_id="w",
        status="DONE",
        created_at="2026-08-13T10:00:00+00:00",
        updated_at="2026-08-13T10:00:02+00:00",
    )
    assert duration_label(record) == "2.0 s"


def test_uc06_pause_approve_done(workspace: Path) -> None:
    assert BRANCH.is_file()
    result = _invoke(workspace, "validate", str(BRANCH))
    assert result.exit_code == 0, result.output

    result = _invoke(workspace, "run", str(BRANCH))
    assert result.exit_code == 0, result.output
    assert "WAITING_USER" in result.output
    assert "platform approve" in result.output
    assert "run_id" in result.output.lower() or "run_id" in result.output

    # 从输出中抠 run_id：waiting panel / 摘要里都会出现 12 位 hex
    import re

    match = re.search(r"platform approve ([0-9a-f]{12})", result.output)
    assert match, result.output
    run_id = match.group(1)

    status = _invoke(workspace, "status", run_id)
    assert status.exit_code == 0, status.output
    assert "WAITING_USER" in status.output
    assert "下一步" in status.output or "platform approve" in status.output

    approve = _invoke(workspace, "approve", run_id)
    assert approve.exit_code == 0, approve.output
    assert "DONE" in approve.output

    done = _invoke(workspace, "status", run_id)
    assert done.exit_code == 0, done.output
    assert "DONE" in done.output


def test_reject_and_input_exit_codes(workspace: Path) -> None:
    result = _invoke(workspace, "run", str(BRANCH))
    assert result.exit_code == 0
    import re

    match = re.search(r"platform approve ([0-9a-f]{12})", result.output)
    assert match
    run_id = match.group(1)

    # 非 WAITING 时再 approve 应失败
    _invoke(workspace, "approve", run_id)
    bad = _invoke(workspace, "approve", run_id)
    assert bad.exit_code != 0

    # 新 run → reject
    result = _invoke(workspace, "run", str(BRANCH))
    run_id = re.search(r"platform approve ([0-9a-f]{12})", result.output).group(1)
    rejected = _invoke(workspace, "reject", run_id)
    assert rejected.exit_code == 0
    assert "DONE" in rejected.output

    # 新 run → input
    result = _invoke(workspace, "run", str(BRANCH))
    run_id = re.search(r"platform approve ([0-9a-f]{12})", result.output).group(1)
    inputted = _invoke(workspace, "input", run_id, "--text", "改期")
    assert inputted.exit_code == 0
    assert "DONE" in inputted.output


def test_low_risk_direct_done(workspace: Path) -> None:
    result = _invoke(workspace, "run", str(BRANCH), "--params", "risk=low")
    assert result.exit_code == 0, result.output
    assert "DONE" in result.output
    assert "WAITING_USER" not in result.output
