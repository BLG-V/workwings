# -*- coding: utf-8 -*-
"""继续邻智云实跑：重置卡住状态并生成 p1。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / ".mawp" / "advanced_projects" / "ap-10b4ae1179.json"
OUT = ROOT / ".last_linzhi_run.json"
BASE = "http://127.0.0.1:8787"
PID = "ap-10b4ae1179"


def main() -> int:
    if META.is_file():
        data = json.loads(META.read_text(encoding="utf-8"))
        if data.get("status") == "generating":
            data["status"] = "ready"
            data["current_phase_id"] = "p1"
            for p in data.get("phases") or []:
                if p.get("id") == "p1" and p.get("status") != "done":
                    p["status"] = "pending"
            META.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print("reset status generating -> ready")

    client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(1200.0, connect=30.0))
    print("generating p1 for", PID)
    g = client.post(
        f"/api/platform/advanced/projects/{PID}/generate",
        params={"use_agents": "true"},
    )
    print("generate", g.status_code)
    if g.status_code >= 400:
        print(g.text[:3000])
        OUT.write_text(
            json.dumps({"error": g.text[:3000], "status_code": g.status_code}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 1
    body = g.json()
    proj = body.get("project") or {}
    summary = {
        "project_id": PID,
        "workspace": proj.get("workspace"),
        "phase_id": body.get("phase_id"),
        "via": body.get("via"),
        "written_count": len(body.get("written") or []),
        "written": body.get("written") or [],
        "changed_files": body.get("changed_files") or [],
        "testing": body.get("testing"),
        "task_runs": body.get("task_runs"),
        "run": body.get("run"),
        "phases": [
            {"id": p.get("id"), "status": p.get("status"), "via": p.get("via")}
            for p in (proj.get("phases") or [])
        ],
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
