from __future__ import annotations

from typing import Any

import chromadb

from mawp.config.loader import AgentConfig
from mawp.rag.embeddings import create_embedding_function
from mawp.rag.indexer import RAGIndexer
from mawp.rag.models import RAGChunk, RetrieveResult


class RAGNotIndexedError(FileNotFoundError):
    """索引尚未构建。"""


class RAGRetriever:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.workspace = config.workspace_path()
        self.index_path = config.rag_index_path()
        self.indexer = RAGIndexer(config)
        self.embedder = create_embedding_function(config)
        self.collection_name = self.indexer.collection_name

    def is_ready(self) -> bool:
        return self.indexer.is_indexed()

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        max_context_chars: int | None = None,
    ) -> RetrieveResult:
        if not self.is_ready():
            return RetrieveResult(query=query, chunks=[], index_hit=False)

        k = top_k or self.config.rag.top_k
        budget = max_context_chars or self.config.rag.max_context_chars

        client = chromadb.PersistentClient(path=str(self.index_path))
        collection = client.get_collection(name=self.collection_name)
        query_embedding = self.embedder.embed([query])[0]
        raw = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, max(collection.count(), 1)),
            include=["documents", "metadatas", "distances"],
        )

        chunks = self._parse_results(raw)
        chunks = self._truncate_by_budget(chunks, budget)
        return RetrieveResult(query=query, chunks=chunks, index_hit=True)

    @staticmethod
    def _parse_results(raw: dict[str, Any]) -> list[RAGChunk]:
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        chunks: list[RAGChunk] = []
        for idx, doc_id in enumerate(ids):
            meta = metadatas[idx] if idx < len(metadatas) else {}
            document = documents[idx] if idx < len(documents) else ""
            distance = distances[idx] if idx < len(distances) else 1.0
            score = 1.0 / (1.0 + float(distance))
            chunks.append(
                RAGChunk(
                    path=str(meta.get("path") or doc_id),
                    content=str(document or ""),
                    start_line=int(meta.get("start_line") or 1),
                    end_line=int(meta.get("end_line") or 1),
                    score=score,
                    language=str(meta.get("language") or ""),
                )
            )
        return chunks

    @staticmethod
    def _truncate_by_budget(chunks: list[RAGChunk], budget: int) -> list[RAGChunk]:
        selected: list[RAGChunk] = []
        used = 0
        for chunk in chunks:
            block_len = len(chunk.content) + len(chunk.path) + 32
            if used + block_len > budget and selected:
                break
            selected.append(chunk)
            used += block_len
        return selected
