from __future__ import annotations

from typing import Any

from mawp.rag.models import RAGChunk
from mawp.rag.service import format_rag_context


def rag_chunks_from_dicts(items: list[dict[str, Any]]) -> list[RAGChunk]:
    return [
        RAGChunk(
            path=str(item.get("path") or ""),
            content=str(item.get("content") or ""),
            start_line=int(item.get("start_line") or 1),
            end_line=int(item.get("end_line") or 1),
            score=float(item.get("score") or 0.0),
            language=str(item.get("language") or ""),
        )
        for item in items
    ]


def format_context_rag_chunks(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    return format_rag_context(rag_chunks_from_dicts(items))
