"""Deliver 工作流选型：全量八 Agent / 增量短链 / 只验收。"""

from __future__ import annotations

from typing import Any

FULL_DELIVER = "apps/demo-code-agent/workflows/deliver.yaml"
INCREMENT_DELIVER = "apps/demo-code-agent/workflows/deliver-increment.yaml"
VERIFY_DELIVER = "apps/demo-code-agent/workflows/deliver-verify.yaml"


def select_deliver_workflow(
    phase: dict[str, Any] | None,
    *,
    verify_only: bool = False,
) -> str:
    """P1 走完整链；后续期走 coding→frontend→testing；verify_only 只跑冒烟。"""
    if verify_only:
        return VERIFY_DELIVER
    phase = phase or {}
    pid = str(phase.get("id") or "").strip().lower()
    deps = phase.get("depends_on")
    if isinstance(deps, list) and deps:
        return INCREMENT_DELIVER
    if pid and pid != "p1":
        return INCREMENT_DELIVER
    return FULL_DELIVER
