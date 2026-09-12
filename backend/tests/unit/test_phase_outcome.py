"""阶段结果：完成 / 部分完成 / 失败，以及占位验收、重试分类。"""

from __future__ import annotations

from pathlib import Path

from mawp.advanced import (
    AdvancedProject,
    AdvancedProjectStore,
    generate_phase_by_id,
    generate_phase_generic_increment,
    ready_pending_phases,
)
from mawp.advanced.phase_outcome import (
    detect_placeholder_output,
    is_retryable_failure,
    phase_subtasks,
    resolve_phase_outcome,
    run_deliver_with_retry,
    validate_phase_against_spec,
)


def test_mall_phase_splits_into_subtasks() -> None:
    tasks = phase_subtasks(
        {"id": "p4", "title": "商城/团购最小闭环", "goal": "商品列表、下单占位、团长端入口"}
    )
    assert len(tasks) >= 3
    titles = " ".join(str(t.get("title") or "") for t in tasks)
    assert "商品" in titles
    assert "下单" in titles
    assert "团长" in titles


def test_timeout_is_retryable_402_is_not() -> None:
    assert is_retryable_failure(TimeoutError("The read operation timed out")) is True
    assert is_retryable_failure(ConnectionResetError("连接被重置")) is True
    assert (
        is_retryable_failure(
            RuntimeError('OpenAI API 错误 (402): {"error":{"message":"Insufficient Balance"}}')
        )
        is False
    )


def test_phase_retry_attempts_is_one() -> None:
    from mawp import advanced as adv

    assert adv.PHASE_RETRY_ATTEMPTS == 1


def test_deliver_poll_default_is_twelve_minutes() -> None:
    import os
    from mawp.advanced import DEFAULT_DELIVER_POLL_SECONDS

    assert DEFAULT_DELIVER_POLL_SECONDS == 720
    # env 可覆盖
    assert int(os.environ.get("MAWP_DELIVER_POLL_SECONDS", str(DEFAULT_DELIVER_POLL_SECONDS))) >= 60


def test_retry_transient_then_succeed() -> None:
    n = {"c": 0}

    def fn():
        n["c"] += 1
        if n["c"] < 3:
            raise TimeoutError("timed out")
        return {"written": ["apps/api/main.py"]}

    result, attempts, err = run_deliver_with_retry(fn, max_attempts=3, sleep=lambda _d: None)
    assert err is None
    assert result == {"written": ["apps/api/main.py"]}
    assert attempts == 3


def test_retry_skips_402() -> None:
    n = {"c": 0}

    def fn():
        n["c"] += 1
        raise RuntimeError("OpenAI API 错误 (402): Insufficient Balance")

    result, attempts, err = run_deliver_with_retry(fn, max_attempts=3, sleep=lambda _d: None)
    assert result is None
    assert attempts == 1
    assert "402" in str(err)


def test_mall_template_is_not_placeholder(tmp_path: Path) -> None:
    from mawp.advanced import generate_phase_mall

    ws = tmp_path / "ws"
    (ws / "apps" / "api").mkdir(parents=True)
    (ws / "apps" / "web").mkdir(parents=True)
    project = AdvancedProject(
        id="t",
        title="邻智云",
        source_filename="s.md",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        workspace=str(ws),
    )
    phase = {
        "id": "p4",
        "title": "商城/团购最小闭环",
        "goal": "商品列表、下单占位、团长端入口",
        "deliverables": ["商品 API", "下单页"],
    }
    written = generate_phase_mall(ws, project)
    assert detect_placeholder_output(ws, written) is False
    assert validate_phase_against_spec(ws, phase, written) == []


def test_generic_items_module_is_placeholder(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "apps" / "api").mkdir(parents=True)
    (ws / "apps" / "web").mkdir(parents=True)
    project = AdvancedProject(
        id="t",
        title="邻智云",
        source_filename="s.md",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        workspace=str(ws),
    )
    phase = {
        "id": "p4",
        "title": "商城/团购最小闭环",
        "goal": "商品列表、下单占位、团长端入口",
        "deliverables": ["商品 API", "下单页"],
    }
    written = generate_phase_generic_increment(ws, project, phase)
    assert detect_placeholder_output(ws, written) is True
    missing = validate_phase_against_spec(ws, phase, written)
    assert missing  # 通用 /items 对不上商品/下单/团长


def test_template_fallback_never_marked_done() -> None:
    outcome = resolve_phase_outcome(
        via="template_fallback:The read operation timed out",
        written=["apps/api/module_p4.py", "apps/web/p4.html"],
        testing={"passed": True},
        placeholder=True,
        spec_gaps=["商品 API"],
    )
    assert outcome["status"] == "partial"
    assert outcome["degraded"] is True


def test_deliver_success_without_gaps_is_done() -> None:
    outcome = resolve_phase_outcome(
        via="deliver",
        written=["apps/api/routers/mall.py", "apps/web/p4.html"],
        testing={"passed": True},
        placeholder=False,
        spec_gaps=[],
    )
    assert outcome["status"] == "done"
    assert outcome["degraded"] is False


def test_nothing_written_is_failed() -> None:
    outcome = resolve_phase_outcome(
        via="template_fallback:OpenAI API 错误 (402)",
        written=[],
        testing=None,
        placeholder=False,
        spec_gaps=["商品 API"],
    )
    assert outcome["status"] == "failed"


def test_partial_dependency_does_not_unlock_next() -> None:
    phases = [
        {"id": "p1", "status": "done", "depends_on": []},
        {"id": "p2", "status": "partial", "depends_on": ["p1"]},
        {"id": "p4", "status": "pending", "depends_on": ["p2"]},
    ]
    ready = ready_pending_phases(phases)
    assert [p["id"] for p in ready] == []


def _store_project(tmp_path: Path) -> tuple[AdvancedProjectStore, str, Path]:
    store = AdvancedProjectStore(tmp_path / "advanced")
    ws = tmp_path / "workspaces" / "ap-demo"
    (ws / "docs").mkdir(parents=True)
    (ws / "apps" / "api").mkdir(parents=True)
    (ws / "apps" / "web").mkdir(parents=True)
    (ws / "apps" / "api" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef h():\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    project = AdvancedProject(
        id="ap-demo",
        title="邻智云",
        source_filename="s.md",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        workspace=str(ws),
        phases=[
            {
                "id": "p4",
                "title": "商城/团购最小闭环",
                "goal": "商品列表、下单占位、团长端入口",
                "deliverables": ["商品 API", "下单页"],
                "depends_on": [],
                "status": "pending",
            }
        ],
        current_phase_id="p4",
        status="ready",
    )
    store.save(project)
    return store, "ap-demo", ws


def test_timeout_marks_partial_not_done(tmp_path: Path, monkeypatch) -> None:
    import mawp.advanced as adv

    store, pid, _ws = _store_project(tmp_path)

    def boom(*_a, **_k):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(adv, "run_phase_via_deliver", boom)
    monkeypatch.setattr(adv, "PHASE_RETRY_SLEEP", lambda _d: None)

    out = generate_phase_by_id(store, pid, "p4", config=object(), use_agents=True)
    loaded = store.load(pid)
    assert loaded is not None
    phase = loaded.phases[0]
    assert phase["status"] == "partial"
    assert str(phase.get("via") or "").startswith("template_fallback")
    assert out["status"] == "partial"


def test_balance_error_marks_failed_without_placeholder(tmp_path: Path, monkeypatch) -> None:
    import mawp.advanced as adv

    store, pid, ws = _store_project(tmp_path)

    def boom(*_a, **_k):
        raise RuntimeError("OpenAI API 错误 (402): Insufficient Balance")

    monkeypatch.setattr(adv, "run_phase_via_deliver", boom)
    monkeypatch.setattr(adv, "PHASE_RETRY_SLEEP", lambda _d: None)

    generate_phase_by_id(store, pid, "p4", config=object(), use_agents=True)
    loaded = store.load(pid)
    assert loaded is not None
    phase = loaded.phases[0]
    assert phase["status"] == "failed"
    assert not (ws / "apps" / "api" / "module_p4.py").exists()
    assert not (ws / "apps" / "web" / "p4.html").exists()
