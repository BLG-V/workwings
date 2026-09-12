"""Token / 成本账本：从 usage 事件汇总，不新增 Agent。

粗略估价仅供演示省钱参考，非账单。
"""

from __future__ import annotations

from typing import Any

# 元 / 百万 tokens（粗估，DeepSeek 量级；未知模型用默认）
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    # (prompt, completion) CNY per 1M tokens
    "deepseek-v4-flash": (0.2, 0.8),
    "deepseek-v4-pro": (2.0, 8.0),
    "deepseek-chat": (1.0, 2.0),
    "deepseek-reasoner": (4.0, 16.0),
    "gpt-4o-mini": (1.0, 4.0),
    "gpt-4o": (18.0, 72.0),
    "claude-3-haiku": (2.0, 10.0),
    "claude-3-5-sonnet": (20.0, 100.0),
    "mock": (0.0, 0.0),
}
_DEFAULT_PRICE = (2.0, 8.0)


def estimate_cost_cny(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None = None,
) -> float:
    key = (model or "").strip().lower()
    prompt_rate, completion_rate = _PRICE_PER_MTOK.get(key, _DEFAULT_PRICE)
    return round(
        prompt_tokens / 1_000_000 * prompt_rate
        + completion_tokens / 1_000_000 * completion_rate,
        6,
    )


def summarize_usage_from_events(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    """扫描 agent_usage / node_end.usage 事件，按 Agent 汇总。

    引擎会同时写 node_end.usage 与 agent_usage；有 agent_usage 时只计后者，避免翻倍。
    """
    by_agent: dict[str, dict[str, Any]] = {}
    total_prompt = 0
    total_completion = 0
    total_tokens = 0
    total_cost = 0.0
    rows = list(events or [])
    has_agent_usage = any(str(ev.get("type") or "") == "agent_usage" for ev in rows)

    for ev in rows:
        kind = str(ev.get("type") or "")
        usage = ev.get("usage") if isinstance(ev.get("usage"), dict) else None
        if kind == "agent_usage":
            agent = str(ev.get("agent") or ev.get("node_id") or "unknown")
        elif kind == "node_end" and usage and not has_agent_usage:
            agent = str(ev.get("agent") or ev.get("node_id") or "unknown")
        else:
            continue
        if not usage:
            continue
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or (prompt + completion))
        if prompt == 0 and completion == 0 and total == 0:
            continue
        model = str(usage.get("model") or ev.get("model") or "") or None
        cost = float(
            usage.get("cost_cny")
            if usage.get("cost_cny") is not None
            else estimate_cost_cny(
                prompt_tokens=prompt,
                completion_tokens=completion,
                model=model,
            )
        )
        bucket = by_agent.setdefault(
            agent,
            {
                "agent": agent,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_cny": 0.0,
                "calls": 0,
                "models": [],
            },
        )
        bucket["prompt_tokens"] += prompt
        bucket["completion_tokens"] += completion
        bucket["total_tokens"] += total
        bucket["cost_cny"] = round(float(bucket["cost_cny"]) + cost, 6)
        bucket["calls"] = int(bucket["calls"]) + 1
        if model and model not in bucket["models"]:
            bucket["models"].append(model)

        total_prompt += prompt
        total_completion += completion
        total_tokens += total
        total_cost += cost

    agents = sorted(by_agent.values(), key=lambda x: -int(x["total_tokens"]))
    return {
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "cost_cny": round(total_cost, 6),
        "by_agent": agents,
    }


def usage_dict_from_response(
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model: str | None = None,
) -> dict[str, Any]:
    prompt = max(0, int(prompt_tokens))
    completion = max(0, int(completion_tokens))
    total = max(0, int(total_tokens) or (prompt + completion))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "model": model,
        "cost_cny": estimate_cost_cny(
            prompt_tokens=prompt,
            completion_tokens=completion,
            model=model,
        ),
    }


def merge_usage(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, Any]:
    left = a or {}
    right = b or {}
    prompt = int(left.get("prompt_tokens") or 0) + int(right.get("prompt_tokens") or 0)
    completion = int(left.get("completion_tokens") or 0) + int(
        right.get("completion_tokens") or 0
    )
    total = int(left.get("total_tokens") or 0) + int(right.get("total_tokens") or 0)
    model = right.get("model") or left.get("model")
    return usage_dict_from_response(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total or (prompt + completion),
        model=str(model) if model else None,
    )
