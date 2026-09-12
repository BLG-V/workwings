"""Token / 成本账本：事件汇总与粗估。"""

from __future__ import annotations

from mawp.runtime.cost_ledger import (
    estimate_cost_cny,
    merge_usage,
    summarize_usage_from_events,
    usage_dict_from_response,
)


def test_estimate_flash_cheaper_than_pro() -> None:
    flash = estimate_cost_cny(prompt_tokens=1_000_000, completion_tokens=0, model="deepseek-v4-flash")
    pro = estimate_cost_cny(prompt_tokens=1_000_000, completion_tokens=0, model="deepseek-v4-pro")
    assert flash < pro


def test_summarize_by_agent() -> None:
    events = [
        {
            "type": "agent_usage",
            "agent": "coding",
            "usage": usage_dict_from_response(
                prompt_tokens=100, completion_tokens=50, model="deepseek-v4-pro"
            ),
        },
        {
            "type": "agent_usage",
            "agent": "coding",
            "usage": usage_dict_from_response(
                prompt_tokens=20, completion_tokens=10, model="deepseek-v4-pro"
            ),
        },
        {
            "type": "agent_usage",
            "agent": "planner",
            "usage": usage_dict_from_response(
                prompt_tokens=40, completion_tokens=5, model="deepseek-v4-flash"
            ),
        },
    ]
    summary = summarize_usage_from_events(events)
    assert summary["total_tokens"] == 225
    assert summary["by_agent"][0]["agent"] == "coding"
    assert summary["by_agent"][0]["total_tokens"] == 180
    assert summary["by_agent"][0]["calls"] == 2
    assert summary["cost_cny"] >= 0


def test_merge_usage() -> None:
    a = usage_dict_from_response(prompt_tokens=10, completion_tokens=5, model="mock")
    b = usage_dict_from_response(prompt_tokens=3, completion_tokens=2, model="mock")
    m = merge_usage(a, b)
    assert m["prompt_tokens"] == 13
    assert m["completion_tokens"] == 7
    assert m["total_tokens"] == 20


def test_node_end_and_agent_usage_not_double_counted() -> None:
    usage = usage_dict_from_response(prompt_tokens=10, completion_tokens=5, model="mock")
    summary = summarize_usage_from_events(
        [
            {"type": "node_end", "agent": "coding", "usage": usage},
            {"type": "agent_usage", "agent": "coding", "usage": usage},
        ]
    )
    assert summary["total_tokens"] == 15
    assert summary["by_agent"][0]["calls"] == 1


def test_node_end_usage_fallback() -> None:
    usage = usage_dict_from_response(prompt_tokens=8, completion_tokens=2, model="mock")
    summary = summarize_usage_from_events(
        [{"type": "node_end", "agent": "planner", "usage": usage}]
    )
    assert summary["total_tokens"] == 10
    assert summary["by_agent"][0]["agent"] == "planner"
