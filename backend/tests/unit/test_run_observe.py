"""Run 观测摘要：耗时 / 自愈 / 失败分类。"""

from __future__ import annotations

from mawp.runtime.run_observe import summarize_run_observe


def test_summarize_node_durations_and_heal() -> None:
    events = [
        {"type": "run_start", "ts": "2026-08-18T11:00:00+00:00"},
        {"type": "node_start", "node_id": "coding", "ts": "2026-08-18T11:00:01+00:00"},
        {"type": "node_retry", "node_id": "coding", "ts": "2026-08-18T11:00:05+00:00"},
        {"type": "heal_attempt", "node_id": "coding", "reason": "transient", "error_category": "timeout", "ts": "2026-08-18T11:00:06+00:00"},
        {"type": "node_end", "node_id": "coding", "status": "ok", "agent": "coding", "ts": "2026-08-18T11:00:11+00:00", "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost_cny": 0.001, "model": "mock"}},
        {"type": "agent_usage", "node_id": "coding", "agent": "coding", "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost_cny": 0.001, "model": "mock"}},
        {"type": "run_end", "status": "DONE", "ts": "2026-08-18T11:00:12+00:00"},
    ]
    obs = summarize_run_observe(events, status="DONE")
    assert obs["heal_attempts"] == 1
    assert obs["node_retries"] == 1
    assert obs["error_category"] == "timeout"
    coding = next(n for n in obs["nodes"] if n["node_id"] == "coding")
    assert coding["duration_ms"] == 10_000
    assert coding["retries"] == 1
    assert coding["total_tokens"] == 15
    assert obs["duration_ms"] == 12_000
    assert obs["waiting_user"] is False
    assert obs["usage"]["total_tokens"] == 15
    assert obs["usage"]["by_agent"][0]["agent"] == "coding"


def test_waiting_user_and_error_fallback() -> None:
    obs = summarize_run_observe(
        [{"type": "node_start", "node_id": "review", "ts": "2026-08-18T11:00:00+00:00"}],
        status="WAITING_USER",
        error="SyntaxError: invalid syntax",
    )
    assert obs["waiting_user"] is True
    assert obs["error_category"] == "syntax_error"


def test_empty_events_uses_run_timestamps() -> None:
    obs = summarize_run_observe(
        [],
        status="FAILED",
        created_at="2026-08-18T11:00:00+00:00",
        updated_at="2026-08-18T11:00:08+00:00",
        error="connection reset",
    )
    assert obs["duration_ms"] == 8_000
    assert obs["failed"] is True
    assert obs["event_count"] == 0
    assert obs["usage"]["total_tokens"] == 0
    assert obs["error_category"] == "transient"
