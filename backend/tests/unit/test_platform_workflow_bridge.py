"""编排页内核桥接：validate Deliver YAML。"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mawp.api.platform import DELIVER_WORKFLOW, create_platform_app
from mawp.config.loader import load_config


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_validate_deliver_workflow_ok(tmp_path) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    src = _backend_root() / DELIVER_WORKFLOW
    dest = tmp_path / DELIVER_WORKFLOW
    dest.parent.mkdir(parents=True)
    shutil.copy(src, dest)

    base = load_config()
    config = base.model_copy(update={"workspace": str(tmp_path)})
    client = TestClient(create_platform_app(config))
    res = client.post(
        "/api/platform/workflows/validate",
        json={"path": DELIVER_WORKFLOW},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["workflow_id"]
    assert body["errors"] == []


def test_validate_missing_path_404(tmp_path) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    base = load_config()
    config = base.model_copy(update={"workspace": str(tmp_path)})
    client = TestClient(create_platform_app(config))
    res = client.post(
        "/api/platform/workflows/validate",
        json={"path": "apps/demo-code-agent/workflows/deliver.yaml"},
    )
    assert res.status_code == 404


def test_list_runs_includes_observe(tmp_path) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from mawp.storage.store import RunRecord, RunStore

    store = RunStore(tmp_path)
    run = RunRecord(
        run_id="obs1",
        workflow_id="demo",
        status="WAITING_USER",
        error="SyntaxError: invalid syntax",
        created_at="2026-08-18T11:00:00+00:00",
        updated_at="2026-08-18T11:00:05+00:00",
    )
    store.save_run(run)
    store.append_event(
        "obs1",
        {"type": "heal_attempt", "reason": "test_failed", "error_category": "syntax_error"},
    )
    store.append_event(
        "obs1",
        {
            "type": "agent_usage",
            "agent": "coding",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "cost_cny": 0.002,
                "model": "deepseek-v4-flash",
            },
        },
    )

    base = load_config()
    config = base.model_copy(update={"workspace": str(tmp_path)})
    client = TestClient(create_platform_app(config))
    res = client.get("/api/platform/runs?limit=10")
    assert res.status_code == 200
    rows = res.json()["runs"]
    assert rows
    obs = rows[0]["observe"]
    assert obs["waiting_user"] is True
    assert obs["heal_attempts"] == 1
    assert obs["error_category"] == "syntax_error"
    assert obs["usage"]["total_tokens"] == 120
    assert obs["usage"]["cost_cny"] == 0.002
