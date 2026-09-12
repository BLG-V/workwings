from __future__ import annotations

from mawp.security.policy import PolicyEngine


def echo(policy: PolicyEngine, *, text: str = "") -> dict:
    """安全回显：仅返回文本，无副作用。"""
    _ = policy
    return {"text": str(text)}
