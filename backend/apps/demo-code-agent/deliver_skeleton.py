"""Deliver skeleton feature for the demo-code-agent.

This module is the code-level contract of the AC-08 delivery skeleton:

    planner -> requirement -> coding -> frontend -> testing <-> debug -> review -> ship

It makes the demo pipeline concrete and testable alongside the YAML workflow
(``apps/demo-code-agent/workflows/deliver.yaml``) and the generated status page
(``apps/demo-code-agent/frontend/index.html``).

Acceptance criteria reflected here:

- the main chain reaches Ship
- Review ``blocking`` requires a human confirmation entry before Ship
- Ship must never auto-push or auto-merge
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DELIVERY_CHAIN: tuple[str, ...] = (
    "planner",
    "requirement",
    "coding",
    "frontend",
    "testing",
    "debug",
    "review",
    "ship",
)

# Frozen output keys (see docs/w4-ad-deliver-yaml-align.md). The workflow must
# keep these stable even though individual agents may add extra keys.
FROZEN_OUTPUT_KEYS: dict[str, tuple[str, ...]] = {
    "planner": ("tasks", "status", "count"),
    "testing": ("passed", "status", "failures", "log_summary", "attempt"),
    "review": ("status", "blocking_count", "findings"),
    "ship": ("status", "delivery_notes", "auto_push", "auto_merge"),
}

# Hard gates: the delivered skeleton is allowed to prepare a delivery, but a
# human must perform the actual push / merge outside the platform.
AUTO_PUSH_ALLOWED = False
AUTO_MERGE_ALLOWED = False


@dataclass(frozen=True)
class ShipDecision:
    """The decision the pipeline is allowed to make at the Ship gate."""

    human_confirmed: bool
    auto_push: bool = False
    auto_merge: bool = False

    def can_ship(self) -> bool:
        """Ship only after human confirmation, and never via auto push/merge."""
        return self.human_confirmed and not self.auto_push and not self.auto_merge


def build_delivery_status(
    *,
    review_status: str = "pass",
    human_confirmed: bool | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build the status payload consumed by the generated status page.

    ``review_status`` mirrors the demo param ``params.review_status``.
    ``human_confirmed`` mirrors the ``human_review`` checkpoint decision.
    """
    review_status = review_status if review_status in {"pass", "blocking"} else "pass"
    blocking = review_status == "blocking"
    confirmed = bool(human_confirmed)
    needs_human = blocking or not confirmed

    chain_steps = [
        {
            "id": step,
            "label": step.title(),
            "reached": True,
        }
        for step in DELIVERY_CHAIN
    ]

    return {
        "chain": chain_steps,
        "reaches_ship": True,
        "review_status": review_status,
        "review_blocking": blocking,
        "human_confirmation_required": needs_human,
        "human_confirmed": confirmed,
        "ship_ready": not needs_human or confirmed,
        "auto_push": AUTO_PUSH_ALLOWED,
        "auto_merge": AUTO_MERGE_ALLOWED,
        "run_id": run_id,
        "approve_hint": f"platform approve {run_id}" if run_id else "platform approve <run_id>",
    }


def ship_decision(human_confirmed: bool) -> ShipDecision:
    """Return a Ship decision with auto push/merge hard-disabled.

    ``human_confirmed`` is the only signal that can move the gate; push and
    merge flags are always ``False`` regardless of any caller intent.
    """
    return ShipDecision(
        human_confirmed=bool(human_confirmed),
        auto_push=False,
        auto_merge=False,
    )


__all__ = [
    "AUTO_MERGE_ALLOWED",
    "AUTO_PUSH_ALLOWED",
    "DELIVERY_CHAIN",
    "FROZEN_OUTPUT_KEYS",
    "ShipDecision",
    "build_delivery_status",
    "ship_decision",
]
