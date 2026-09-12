"""高级项目：依赖就绪波次 + 沙箱并行合并。"""

from __future__ import annotations

from pathlib import Path

from mawp.advanced import (
    AdvancedProject,
    AdvancedProjectStore,
    ready_pending_phases,
    generate_remaining_phases,
)


def test_ready_pending_respects_depends_on() -> None:
    phases = [
        {"id": "p1", "status": "done", "depends_on": []},
        {"id": "p2", "status": "pending", "depends_on": ["p1"]},
        {"id": "p3", "status": "pending", "depends_on": ["p1"]},
        {"id": "p4", "status": "pending", "depends_on": ["p2"]},
    ]
    ready = ready_pending_phases(phases)
    assert [p["id"] for p in ready] == ["p2", "p3"]


def test_parallel_wave_template(tmp_path: Path) -> None:
    store = AdvancedProjectStore(tmp_path / "advanced")
    ws = tmp_path / "workspaces" / "ap-demo"
    ws.mkdir(parents=True)
    (ws / "docs").mkdir()
    (ws / "apps" / "api").mkdir(parents=True)
    (ws / "apps" / "web").mkdir(parents=True)

    project = AdvancedProject(
        id="ap-demo",
        title="并行演示",
        source_filename="srs.txt",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        workspace=str(ws),
        phases=[
            {
                "id": "p1",
                "title": "基线",
                "goal": "骨架",
                "depends_on": [],
                "status": "done",
                "generated_files": [],
            },
            {
                "id": "p2",
                "title": "缴费",
                "goal": "账单",
                "depends_on": ["p1"],
                "status": "pending",
            },
            {
                "id": "p3",
                "title": "后台",
                "goal": "运营",
                "depends_on": ["p1"],
                "status": "pending",
            },
        ],
        srs_chars=10,
        current_phase_id="p2",
        status="ready",
    )
    store.save(project)

    out = generate_remaining_phases(
        store,
        "ap-demo",
        use_agents=False,
        parallel_workers=2,
        stop_on_smoke_fail=False,
        max_phases=4,
    )
    assert out["generated_count"] >= 2
    assert out["parallel_workers"] == 2
    assert any(len(w) >= 2 for w in (out.get("waves") or []))

    loaded = store.load("ap-demo")
    assert loaded is not None
    assert all(p["status"] == "done" for p in loaded.phases)
