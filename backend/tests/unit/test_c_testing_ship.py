"""C · Testing + Ship Agent 单测（UC-07）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mawp.cli.main import app
from mawp.config.loader import load_config
from mawp.core.engine import WorkflowEngine
from mawp.runtime.agents import AgentRunContext, MockAgentRunner
from mawp.runtime.ship_agent import run_ship_agent
from mawp.runtime.testing_agent import run_testing_agent

DELIVER = Path("examples/deliver/workflow.yaml")
runner = CliRunner()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    example = Path("mawp.config.yaml.example")
    cfg = tmp_path / "mawp.config.yaml"
    text = example.read_text(encoding="utf-8")
    text = text.replace('workspace: "."', f'workspace: "{tmp_path.as_posix()}"')
    text = text.replace('provider: "openai"', 'provider: "mock"')
    cfg.write_text(text, encoding="utf-8")
    return tmp_path


def _ctx(**kwargs) -> AgentRunContext:
    base = {
        "run_id": "r1",
        "params": {},
        "nodes_outputs": {},
        "node_id": "testing",
    }
    base.update(kwargs)
    return AgentRunContext(**base)  # type: ignore[arg-type]


def test_testing_runs_metric_command(tmp_path: Path) -> None:
    ctx = _ctx(params={}, node_id="testing")
    out = run_testing_agent(
        {"metric_command": 'python -c "import sys; sys.exit(0)"'},
        ctx,
        workspace=tmp_path,
    )
    assert out["passed"] is True
    assert out["status"] == "pass"
    assert "PASS" in out["log_summary"]
    assert out["metric_command"]


def test_testing_metric_fail_log_summary(tmp_path: Path) -> None:
    out = run_testing_agent(
        {"metric_command": 'python -c "import sys; sys.exit(2)"'},
        _ctx(),
        workspace=tmp_path,
    )
    assert out["passed"] is False
    assert out["status"] == "fail"
    assert out["failures"]
    assert "FAIL" in out["log_summary"]


def test_testing_mock_pass_on_attempt_compat(tmp_path: Path) -> None:
    """无 metric_command 时保持 A 骨架演示逻辑。"""
    ctx = _ctx(params={"pass_on_attempt": 2}, node_id="testing")
    first = run_testing_agent({}, ctx, workspace=tmp_path)
    assert first["passed"] is False
    ctx2 = _ctx(
        params={"pass_on_attempt": 2},
        node_id="testing",
        nodes_outputs={"testing": first},
    )
    second = run_testing_agent({}, ctx2, workspace=tmp_path)
    assert second["attempt"] == 2
    assert second["passed"] is True


def test_ship_generates_notes_no_autopush(tmp_path: Path) -> None:
    ctx = _ctx(
        run_id="shiprun1",
        params={"goal": "UC-07"},
        node_id="ship",
        nodes_outputs={
            "testing": {
                "passed": True,
                "status": "pass",
                "log_summary": "ok",
                "attempt": 1,
            },
            "review": {"status": "pass", "blocking_count": 0},
            "coding": {"changed_files": ["src/app.py"]},
        },
    )
    out = run_ship_agent({"delivery_notes": "ready"}, ctx, workspace=tmp_path)
    assert out["status"] == "ok"
    assert out["auto_push"] is False
    assert out["auto_merge"] is False
    assert "禁止自动 push/merge" in out["delivery_notes"] or "人工" in out["delivery_notes"]
    assert (tmp_path / ".mawp" / "deliveries" / "shiprun1.md").is_file()


def test_deliver_uc07_approve_then_ship_done(workspace: Path) -> None:
    assert DELIVER.is_file()
    cfg = workspace / "mawp.config.yaml"
    result = runner.invoke(
        app,
        [
            "--config",
            str(cfg),
            "deliver",
            str(DELIVER),
            "--params",
            "review_status=blocking",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "WAITING_USER" in result.output
    assert "Agent" in result.output or "testing" in result.output.lower()
    assert "platform approve" in result.output

    import re

    match = re.search(r"platform approve ([0-9a-f]{12})", result.output)
    assert match, result.output
    run_id = match.group(1)

    approve = runner.invoke(app, ["--config", str(cfg), "approve", run_id])
    assert approve.exit_code == 0, approve.output
    assert "DONE" in approve.output

    # engine 侧确认 ship 产物
    config = load_config(cfg)
    engine = WorkflowEngine(config)
    record = engine.store.load_run(run_id)
    assert record is not None
    assert record.status == "DONE"
    ship = record.node_outputs["ship"]
    assert ship["auto_push"] is False
    assert ship["auto_merge"] is False
    assert ship.get("delivery_notes")


def test_mock_runner_wires_testing_ship(tmp_path: Path) -> None:
    runner_impl = MockAgentRunner(tmp_path)
    ctx = _ctx(params={"pass_on_attempt": 1})
    testing = runner_impl.run("testing", {}, ctx)
    assert testing.success
    assert testing.output["passed"] is True

    ship_ctx = _ctx(
        run_id="r2",
        node_id="ship",
        params={"goal": "g"},
        nodes_outputs={"testing": testing.output},
    )
    ship = runner_impl.run("ship", {}, ship_ctx)
    assert ship.success
    assert ship.output["auto_push"] is False
