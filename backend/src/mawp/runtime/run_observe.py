"""Run 观测摘要：节点耗时、自愈次数、失败分类。确定性扫描事件，不新增 Agent。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mawp.runtime.cost_ledger import summarize_usage_from_events
from mawp.runtime.error_classifier import classify_error


def _parse_ts(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _ms_between(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds() * 1000))


def summarize_run_observe(
    events: list[dict[str, Any]] | None,
    *,
    status: str = "",
    error: str | None = None,
    heal: dict[str, Any] | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    rows = list(events or [])
    starts: dict[str, datetime] = {}
    nodes: dict[str, dict[str, Any]] = {}
    heal_attempts = 0
    heal_handoffs = 0
    node_retries = 0
    last_category: str | None = None
    last_reason: str | None = None
    event_times: list[datetime] = []

    for ev in rows:
        ts = _parse_ts(str(ev.get("ts") or ""))
        if ts:
            event_times.append(ts)
        kind = str(ev.get("type") or "")
        nid = str(ev.get("node_id") or "")
        if kind == "node_start" and nid:
            starts[nid] = ts or starts.get(nid) or datetime.now(timezone.utc)
            nodes.setdefault(
                nid,
                {"node_id": nid, "status": "running", "duration_ms": None, "retries": 0},
            )
        elif kind == "node_end" and nid:
            item = nodes.setdefault(
                nid,
                {"node_id": nid, "status": "ok", "duration_ms": None, "retries": 0},
            )
            item["status"] = str(ev.get("status") or "ok")
            start = starts.get(nid)
            dur = _ms_between(start, ts)
            if dur is not None:
                prev = item.get("duration_ms")
                item["duration_ms"] = (prev or 0) + dur
            usage = ev.get("usage") if isinstance(ev.get("usage"), dict) else None
            if usage:
                item["prompt_tokens"] = int(usage.get("prompt_tokens") or 0)
                item["completion_tokens"] = int(usage.get("completion_tokens") or 0)
                item["total_tokens"] = int(usage.get("total_tokens") or 0)
                item["cost_cny"] = usage.get("cost_cny")
                if usage.get("model"):
                    item["model"] = usage.get("model")
        elif kind == "node_retry":
            node_retries += 1
            if nid:
                item = nodes.setdefault(
                    nid,
                    {"node_id": nid, "status": "retry", "duration_ms": None, "retries": 0},
                )
                item["retries"] = int(item.get("retries") or 0) + 1
                item["status"] = "retry"
        elif kind == "heal_attempt":
            heal_attempts += 1
            cat = ev.get("error_category")
            if cat:
                last_category = str(cat)
            if ev.get("reason"):
                last_reason = str(ev.get("reason"))
        elif kind == "heal_handoff":
            heal_handoffs += 1

    if not last_category and isinstance(heal, dict):
        last_category = heal.get("error_category") or None
        last_reason = last_reason or heal.get("last_reason")
    # heal 未写入类别、或只记了 unknown 时，用 run.error 再分一次
    if (not last_category or last_category == "unknown") and error:
        fallback = classify_error(error).category
        if fallback and (not last_category or fallback != "unknown"):
            last_category = fallback

    first_ts = event_times[0] if event_times else _parse_ts(created_at)
    last_ts = event_times[-1] if event_times else _parse_ts(updated_at)
    total_ms = _ms_between(first_ts, last_ts)
    if total_ms is None:
        total_ms = _ms_between(_parse_ts(created_at), _parse_ts(updated_at))

    status_u = (status or "").upper()
    return {
        "duration_ms": total_ms,
        "nodes": list(nodes.values()),
        "heal_attempts": heal_attempts,
        "heal_handoffs": heal_handoffs,
        "node_retries": node_retries,
        "error_category": last_category,
        "heal_reason": last_reason,
        "waiting_user": status_u == "WAITING_USER",
        "failed": status_u in {"FAILED", "CANCELLED"},
        "event_count": len(rows),
        "usage": summarize_usage_from_events(rows),
    }
