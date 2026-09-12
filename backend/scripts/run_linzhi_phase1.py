# -*- coding: utf-8 -*-
"""邻智云 SRS 实跑：创建高级项目并生成第 1 期。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRS = ROOT / "workspaces" / "ap-1e2735daa1" / "docs" / "SRS.md"
OUT = ROOT / ".last_linzhi_run.json"
BASE = "http://127.0.0.1:8787"


def main() -> int:
    srs = SRS.read_text(encoding="utf-8")
    print("srs_chars", len(srs))
    client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(900.0, connect=30.0))

    r = client.post(
        "/api/platform/advanced/projects",
        data={"title": "邻智云 AI 社区 · 实跑验收"},
        files={"file": ("邻智云-SRS.md", srs.encode("utf-8"), "text/markdown")},
    )
    print("create", r.status_code)
    r.raise_for_status()
    proj = (r.json().get("project") or r.json())
    pid = proj["id"]
    print("project_id", pid)
    print(
        "phases",
        [
            (p["id"], p.get("title"), p.get("status"), p.get("depends_on"))
            for p in proj.get("phases", [])
        ],
    )
    print("workspace", proj.get("workspace"))

    print("generating phase1 via agents…")
    g = client.post(
        f"/api/platform/advanced/projects/{pid}/generate",
        params={"use_agents": "true"},
    )
    print("generate", g.status_code)
    if g.status_code >= 400:
        print(g.text[:2000])
        return 1
    body = g.json()
    summary = {
        "project_id": pid,
        "workspace": (body.get("project") or {}).get("workspace") or proj.get("workspace"),
        "phase_id": body.get("phase_id"),
        "via": body.get("via"),
        "written_count": len(body.get("written") or []),
        "written": (body.get("written") or [])[:40],
        "changed_files": (body.get("changed_files") or [])[:40],
        "testing": body.get("testing"),
        "task_runs": body.get("task_runs"),
        "run": body.get("run"),
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
