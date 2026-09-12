# -*- coding: utf-8 -*-
"""自愈回合模型选型：错误类型 + 轮次 + Agent 职责，不全程升 Pro。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mawp.config.loader import DEFAULT_AGENT_MODELS, HealModelsConfig


@dataclass(frozen=True)
class HealModelChoice:
    model: str
    strategy: str  # keep | by_category | escalate | failover
    category: str


def resolve_agent_default(
    agent: str,
    agent_models: dict[str, str] | None,
    *,
    global_default: str = "deepseek-v4-pro",
) -> str:
    models = agent_models or {}
    name = (agent or "").strip().lower()
    if name in models and models[name]:
        return str(models[name])
    if name in DEFAULT_AGENT_MODELS:
        return DEFAULT_AGENT_MODELS[name]
    return global_default


def select_heal_model(
    *,
    category: str,
    agent: str,
    heal_round: int,
    agent_models: dict[str, str] | None = None,
    heal_cfg: HealModelsConfig | None = None,
    failover_attempt: int = 0,
    global_default: str = "deepseek-v4-pro",
) -> HealModelChoice:
    """按三信号选型。

    - transient：走 failover 列表（按 attempt 轮换）
    - 其余：先 by_category，再 default/keep；轮次达到 escalate_after_round 则升档
    """
    cfg = heal_cfg or HealModelsConfig()
    cat = (category or "unknown").strip().lower() or "unknown"
    agent_default = resolve_agent_default(
        agent, agent_models, global_default=global_default
    )

    if cat == "transient":
        chain = list(cfg.failover or [])
        if not chain:
            return HealModelChoice(
                model=agent_default, strategy="keep", category=cat
            )
        idx = max(0, int(failover_attempt)) % len(chain)
        return HealModelChoice(
            model=str(chain[idx]), strategy="failover", category=cat
        )

    mapped = (cfg.by_category or {}).get(cat)
    if mapped is None or str(mapped).strip().lower() == "keep":
        if str(cfg.default).strip().lower() not in ("keep", ""):
            model = str(cfg.default)
        else:
            model = agent_default
        strategy = "keep"
    else:
        model = str(mapped)
        strategy = "by_category"

    # 升档：第 N 轮起换 escalate_to
    round_n = max(1, int(heal_round or 1))
    escalate_after = max(1, int(cfg.escalate_after_round or 2))
    escalate_to = str(cfg.escalate_to or "").strip()
    if round_n >= escalate_after and escalate_to and escalate_to != model:
        return HealModelChoice(
            model=escalate_to, strategy="escalate", category=cat
        )

    return HealModelChoice(model=model, strategy=strategy, category=cat)


def category_from_heal_reason(
    reason: str,
    *,
    error_text: str = "",
    failures: list[Any] | None = None,
    log_summary: str = "",
) -> str:
    """把 SelfHeal 原因 / 测试失败日志映射到 by_category 键。"""
    from mawp.runtime.error_classifier import classify_error

    r = (reason or "").strip().lower()
    if r in ("transient",):
        return "transient"
    if r in ("review_blocking",):
        return "review_blocking"
    if r in ("max_steps",):
        return "max_steps"
    if r in ("test_failed",) or failures or log_summary:
        raw = "\n".join(str(f) for f in (failures or [])) or error_text or log_summary
        return classify_error(raw, log_summary).category
    if error_text:
        return classify_error(error_text, log_summary).category
    return "unknown"
