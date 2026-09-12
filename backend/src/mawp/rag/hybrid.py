from __future__ import annotations

import json
from typing import Any

from mawp.config.loader import AgentConfig
from mawp.rag.bm25 import BM25Index
from mawp.rag.indexer import RAGIndexer
from mawp.rag.models import RAGChunk, RetrieveResult
from mawp.rag.retriever import RAGRetriever


class HybridRAGRetriever(RAGRetriever):
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.bm25 = BM25Index()
        self._catalog: dict[str, dict[str, Any]] = {}
        self._load_search_index()

    def _load_search_index(self) -> None:
        path = self.indexer.search_index_path()
        if not path.is_file():
            return
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        documents: list[tuple[str, str]] = []
        for row in rows:
            chunk_id = str(row.get("chunk_id") or "")
            if not chunk_id:
                continue
            self._catalog[chunk_id] = row
            documents.append((chunk_id, str(row.get("content") or "")))
        if documents:
            self.bm25.build(documents)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        max_context_chars: int | None = None,
    ) -> RetrieveResult:
        if not self.config.rag.hybrid_search or not self._catalog:
            return super().retrieve(
                query,
                top_k=top_k,
                max_context_chars=max_context_chars,
            )

        vector_result = super().retrieve(
            query,
            top_k=(top_k or self.config.rag.top_k) * 2,
            max_context_chars=max_context_chars,
        )
        if not vector_result.index_hit:
            return vector_result

        bm25_hits = self.bm25.score(query, top_k=(top_k or self.config.rag.top_k) * 2)
        if not bm25_hits:
            return vector_result

        max_bm25 = max(score for _, score in bm25_hits) or 1.0
        fused: dict[str, RAGChunk] = {}

        for chunk in vector_result.chunks:
            fused_key = f"{chunk.path}:{chunk.start_line}"
            fused[fused_key] = RAGChunk(
                path=chunk.path,
                content=chunk.content,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                score=chunk.score * (1.0 - self.config.rag.bm25_weight),
                language=chunk.language,
            )

        for chunk_id, score in bm25_hits:
            row = self._catalog.get(chunk_id)
            if row is None:
                continue
            key = f"{row['path']}:{row['start_line']}"
            bm25_score = (score / max_bm25) * self.config.rag.bm25_weight
            if key in fused:
                fused[key].score += bm25_score
            else:
                fused[key] = RAGChunk(
                    path=str(row["path"]),
                    content=str(row["content"]),
                    start_line=int(row.get("start_line") or 1),
                    end_line=int(row.get("end_line") or 1),
                    score=bm25_score,
                    language=str(row.get("language") or ""),
                )

        merged = sorted(fused.values(), key=lambda c: c.score, reverse=True)
        k = top_k or self.config.rag.top_k
        budget = max_context_chars or self.config.rag.max_context_chars
        chunks = self._truncate_by_budget(merged[:k], budget)
        return RetrieveResult(query=query, chunks=chunks, index_hit=True)
