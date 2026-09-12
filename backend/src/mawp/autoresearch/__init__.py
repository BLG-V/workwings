"""Autoresearch — modify → verify → keep/discard 自主迭代。"""

from __future__ import annotations

from typing import Any

__all__ = [
    "AutoresearchLoop",
    "LoopResult",
    "ProgramService",
    "ResumeNotAvailableError",
]


def __getattr__(name: str) -> Any:
    if name in {"AutoresearchLoop", "LoopResult", "ResumeNotAvailableError"}:
        from mawp.autoresearch.loop import (
            AutoresearchLoop,
            LoopResult,
            ResumeNotAvailableError,
        )

        mapping = {
            "AutoresearchLoop": AutoresearchLoop,
            "LoopResult": LoopResult,
            "ResumeNotAvailableError": ResumeNotAvailableError,
        }
        return mapping[name]
    if name == "ProgramService":
        from mawp.autoresearch.program import ProgramService

        return ProgramService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
