from __future__ import annotations

from pathlib import Path

from mawp.core.loader import load_workflow, parse_workflow_dict
from mawp.core.template import render_value
from mawp.core.validate import validate_workflow


def test_hello_workflow_validates() -> None:
    src = Path("examples/hello-workflow/workflow.yaml")
    wf = load_workflow(src)
    assert validate_workflow(wf) == []


def test_missing_entry_fails(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(
        "id: x\nname: x\nversion: '1'\nentry: nope\n"
        "nodes:\n  - id: start\n    type: start\n  - id: end\n    type: end\n"
        "edges:\n  - from: start\n    to: end\n",
        encoding="utf-8",
    )
    wf = load_workflow(p)
    errors = validate_workflow(wf)
    assert any("entry" in e.lower() or "nope" in e for e in errors)


def test_cycle_rejected() -> None:
    wf = parse_workflow_dict(
        {
            "id": "c",
            "name": "c",
            "version": "1",
            "entry": "a",
            "nodes": [
                {"id": "a", "type": "start"},
                {"id": "b", "type": "tool", "tool": "echo", "input": {"text": "x"}},
                {"id": "end", "type": "end"},
            ],
            "edges": [
                {"from": "a", "to": "b"},
                {"from": "b", "to": "a"},
                {"from": "b", "to": "end"},
            ],
        }
    )
    errors = validate_workflow(wf)
    assert any("环" in e for e in errors)


def test_render_params() -> None:
    assert (
        render_value("hello ${params.name}", params={"name": "world"}, nodes_outputs={})
        == "hello world"
    )
