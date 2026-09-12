# -*- coding: utf-8 -*-
"""邻智云剩余里程碑实跑（结果打印到 stdout，不写报告文件）。"""
from __future__ import annotations

import json
import sys

import httpx

BASE = "http://127.0.0.1:8787"
PID = "ap-10b4ae1179"


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(3600.0, connect=30.0))
    print("START generate-remaining", PID, flush=True)
    r = client.post(
        f"/api/platform/advanced/projects/{PID}/generate-remaining",
        params={
            "use_agents": "true",
            "parallel_workers": "1",
            "max_phases": "4",
            "stop_on_smoke_fail": "false",
        },
    )
    print("HTTP", r.status_code, flush=True)
    if r.status_code >= 400:
        print(r.text[:4000], flush=True)
        return 1
    body = r.json()
    print("generated_count", body.get("generated_count"), flush=True)
    print("stopped_early", body.get("stopped_early"), flush=True)
    print("waves", body.get("waves"), flush=True)
    for i, one in enumerate(body.get("results") or []):
        testing = one.get("testing") or {}
        print(
            f"RESULT[{i}] phase={one.get('phase_id')} via={one.get('via')} "
            f"files={len(one.get('written') or [])} "
            f"test_passed={testing.get('passed')} "
            f"metric={testing.get('metric_command')}",
            flush=True,
        )
        if testing.get("log_summary"):
            print("  log:", str(testing.get("log_summary"))[:300], flush=True)
    proj = body.get("project") or {}
    print(
        "FINAL_PHASES",
        [(p.get("id"), p.get("status"), p.get("via")) for p in (proj.get("phases") or [])],
        flush=True,
    )
    # 简洁摘要只打 stdout
    print("SUMMARY_JSON", json.dumps({
        "generated_count": body.get("generated_count"),
        "stopped_early": body.get("stopped_early"),
        "phases": [
            {
                "id": p.get("id"),
                "status": p.get("status"),
                "via": p.get("via"),
                "testing_passed": (p.get("testing") or {}).get("passed"),
            }
            for p in (proj.get("phases") or [])
        ],
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
