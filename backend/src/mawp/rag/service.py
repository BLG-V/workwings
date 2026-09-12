from __future__ import annotations

from mawp.config.loader import AgentConfig
from mawp.rag.hybrid import HybridRAGRetriever
from mawp.rag.indexer import RAGIndexer
from mawp.rag.models import IndexStats, RAGChunk, RetrieveResult
from mawp.rag.retriever import RAGRetriever


def format_rag_context(chunks: list[RAGChunk]) -> str:
    if not chunks:
        return ""
    lines = ["以下是与需求相关的代码库检索片段（path:line，供分析参考）："]
    for chunk in chunks:
        header = f"\n--- {chunk.path}:{chunk.start_line}-{chunk.end_line} (score={chunk.score:.3f}) ---"
        lines.append(header)
        lines.append(chunk.content.strip())
    return "\n".join(lines)


class RAGService:
    """RAG 门面：索引构建 + 检索。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.indexer = RAGIndexer(config)
        if config.rag.hybrid_search:
            self.retriever = HybridRAGRetriever(config)
        else:
            self.retriever = RAGRetriever(config)

    def is_indexed(self) -> bool:
        return self.indexer.is_indexed()

    def build_index(self, *, force: bool = False) -> IndexStats:
        return self.indexer.build(force=force)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        max_context_chars: int | None = None,
    ) -> RetrieveResult:
        return self.retriever.retrieve(
            query,
            top_k=top_k,
            max_context_chars=max_context_chars,
        )

    def retrieve_chunks(self, query: str) -> list[RAGChunk]:
        return self.retrieve(query).chunks
