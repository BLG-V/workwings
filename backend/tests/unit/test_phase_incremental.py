"""多期增量挂载：后期不得覆盖前期路由。"""

from __future__ import annotations

from pathlib import Path

from mawp.advanced import (
    AdvancedProject,
    generate_phase_admin,
    generate_phase_billing,
    generate_phase_mall,
    generate_phase_mvp_repair,
)
from mawp.runtime.agents import AgentRunContext
from mawp.runtime.hybrid import HybridAgentRunner
from mawp.config.loader import load_config


def _proj(ws: Path) -> AdvancedProject:
    return AdvancedProject(
        id="t1",
        title="邻智云测",
        source_filename="s.md",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        workspace=str(ws),
    )


def test_billing_admin_do_not_wipe_repairs(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    p = _proj(ws)
    generate_phase_mvp_repair(ws, p)
    main = (ws / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    assert "Repair" in main or "/api/repairs" in main

    generate_phase_billing(ws, p)
    main2 = (ws / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    assert "Repair" in main2 or "/api/repairs" in main2
    assert (ws / "apps" / "api" / "routers" / "bills.py").is_file()

    generate_phase_admin(ws, p)
    main3 = (ws / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    assert "Repair" in main3 or "/api/repairs" in main3
    assert (ws / "apps" / "api" / "routers" / "admin.py").is_file()
    assert "include_router" in main3

    generate_phase_mall(ws, p)
    main4 = (ws / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    assert "Repair" in main4 or "/api/repairs" in main4
    mall = (ws / "apps" / "api" / "routers" / "mall.py").read_text(encoding="utf-8")
    assert "/api/products" in mall
    assert "/api/orders" in mall
    assert "新增条目" not in mall


def test_project_mode_normalize_testing_refuses_llm_pass_without_smoke() -> None:
    cfg = load_config()
    runner = HybridAgentRunner(cfg)
    ctx = AgentRunContext(
        run_id="r",
        params={"project_mode": True, "metric_command": 'python "x.py"'},
        nodes_outputs={},
        node_id="testing",
    )
    out = runner._normalize_testing(
        {"passed": True, "log_summary": "LLM says ok", "attempt": 1},
        {},
        ctx,
    )
    assert out["passed"] is False
    assert out["status"] == "fail"
