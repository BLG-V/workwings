from __future__ import annotations

from pathlib import Path

from mawp.config.loader import load_config
from mawp.core.engine import WorkflowEngine
from mawp.tools.registry import ToolRegistry
from mawp.tools.types import ToolCallContext


def test_echo_tool(tmp_path: Path) -> None:
    config = load_config().model_copy(update={"workspace": str(tmp_path)})
    registry = ToolRegistry(config)
    result = registry.execute(
        "echo",
        {"text": "hello"},
        ToolCallContext(agent_name="workflow"),
    )
    assert result.success
    assert result.data["text"] == "hello"


def test_hello_engine_done(tmp_path: Path) -> None:
    config = load_config().model_copy(update={"workspace": str(tmp_path)})
    config.llm = config.llm.model_copy(update={"provider": "mock"})
    engine = WorkflowEngine(config)
    record = engine.run(Path("examples/hello-workflow/workflow.yaml"))
    assert record.status == "DONE"
    assert record.node_outputs["echo1"]["text"] == "hello world"
    assert (tmp_path / ".mawp" / "runs" / f"{record.run_id}.json").is_file()
    events = engine.store.read_events(record.run_id)
    types = [e["type"] for e in events]
    assert "run_start" in types
    assert "run_end" in types
