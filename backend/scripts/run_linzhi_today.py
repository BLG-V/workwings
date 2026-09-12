# -*- coding: utf-8 -*-
"""今日邻智云验证轮：新建项目 → p1 Agent → 剩余期增量模板 → 探活。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRS = ROOT / "workspaces" / "ap-1e2735daa1" / "docs" / "SRS.md"
BASE = "http://127.0.0.1:8787"


def main() -> int:
    if not SRS.is_file():
        # fallback: any existing SRS
        cands = list((ROOT / "workspaces").glob("ap-*/docs/SRS.md"))
        if not cands:
            print("NO_SRS", flush=True)
            return 1
        srs_path = cands[0]
    else:
        srs_path = SRS
    srs = srs_path.read_text(encoding="utf-8")
    print("srs_chars", len(srs), "from", srs_path, flush=True)

    client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(3600.0, connect=30.0))
    h = client.get("/api/health")
    print("health", h.status_code, h.json().get("llm", {}).get("has_api_key"), flush=True)
    if h.status_code != 200:
        return 1

    r = client.post(
        "/api/platform/advanced/projects",
        data={"title": "邻智云 · 今日验证轮"},
        files={"file": ("邻智云-SRS.md", srs.encode("utf-8"), "text/markdown")},
    )
    print("create", r.status_code, flush=True)
    r.raise_for_status()
    proj = r.json().get("project") or r.json()
    pid = proj["id"]
    print("project_id", pid, flush=True)
    print("workspace", proj.get("workspace"), flush=True)

    print("=== P1 Agent Deliver ===", flush=True)
    g = client.post(
        f"/api/platform/advanced/projects/{pid}/generate",
        params={"use_agents": "true"},
    )
    print("p1_http", g.status_code, flush=True)
    if g.status_code >= 400:
        print(g.text[:2000], flush=True)
        return 1
    body = g.json()
    testing = body.get("testing") or {}
    print(
        "p1",
        "via=", body.get("via"),
        "phase=", body.get("phase_id"),
        "files=", len(body.get("written") or []),
        "test_passed=", testing.get("passed"),
        "metric=", testing.get("metric_command"),
        flush=True,
    )
    if testing.get("log_summary"):
        print("p1_log", str(testing.get("log_summary"))[:400], flush=True)

    print("=== Remaining incremental templates (validate no wipe) ===", flush=True)
    rem = client.post(
        f"/api/platform/advanced/projects/{pid}/generate-remaining",
        params={
            "use_agents": "false",
            "parallel_workers": "1",
            "max_phases": "4",
            "stop_on_smoke_fail": "false",
        },
    )
    print("rem_http", rem.status_code, flush=True)
    if rem.status_code >= 400:
        print(rem.text[:2000], flush=True)
        return 1
    rb = rem.json()
    print("generated", rb.get("generated_count"), "waves", rb.get("waves"), flush=True)
    for one in rb.get("results") or []:
        print(
            " ",
            one.get("phase_id"),
            one.get("via"),
            "files",
            len(one.get("written") or []),
            flush=True,
        )
    phases = (rb.get("project") or {}).get("phases") or []
    print(
        "FINAL",
        [(p.get("id"), p.get("status"), (p.get("via") or "")[:48]) for p in phases],
        flush=True,
    )

    # live probe workspace
    ws = Path((rb.get("project") or proj).get("workspace") or "")
    api = ws / "apps" / "api"
    print("=== Live probe ===", flush=True)
    try:
        sys.path.insert(0, str(api.resolve()))
        from fastapi.testclient import TestClient
        import importlib
        import main as api_main

        importlib.reload(api_main)
        c = TestClient(api_main.app)
        health = c.get("/health")
        repairs = c.get("/api/repairs")
        bills = c.get("/api/bills")
        admin = c.get("/api/admin/overview")
        print("health", health.status_code, health.json(), flush=True)
        print("repairs", repairs.status_code, flush=True)
        print("bills", bills.status_code, flush=True)
        print("admin", admin.status_code, flush=True)
        ok = (
            health.status_code == 200
            and repairs.status_code < 500
            and repairs.status_code != 404
        )
        print("PROBE_OK" if ok else "PROBE_FAIL", flush=True)
        print(
            "SUMMARY",
            json.dumps(
                {
                    "project_id": pid,
                    "p1_via": body.get("via"),
                    "p1_test_passed": testing.get("passed"),
                    "remaining": rb.get("generated_count"),
                    "health": health.status_code,
                    "repairs": repairs.status_code,
                    "bills": bills.status_code,
                    "admin": admin.status_code,
                    "probe_ok": ok,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0 if ok else 2
    except Exception as exc:  # noqa: BLE001
        print("PROBE_ERR", type(exc).__name__, exc, flush=True)
        return 3


if __name__ == "__main__":
    sys.exit(main())
