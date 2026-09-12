from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CodeChunk:
    """索引/检索的基本单元。"""

    chunk_id: str
    path: str
    content: str
    start_line: int = 1
    end_line: int = 1
    language: str = ""
    content_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "path": self.path,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "content_hash": self.content_hash,
        }


@dataclass
class RAGChunk:
    """检索结果，注入 Agent 上下文。"""

    path: str
    content: str
    start_line: int
    end_line: int
    score: float
    language: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": self.score,
            "language": self.language,
        }


@dataclass
class IndexStats:
    files_scanned: int = 0
    files_indexed: int = 0
    chunks_indexed: int = 0
    skipped: int = 0
    duration_ms: int = 0
    collection: str = ""
    index_path: str = ""
    rebuilt: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_scanned": self.files_scanned,
            "files_indexed": self.files_indexed,
            "chunks_indexed": self.chunks_indexed,
            "skipped": self.skipped,
            "duration_ms": self.duration_ms,
            "collection": self.collection,
            "index_path": self.index_path,
            "rebuilt": self.rebuilt,
        }


@dataclass
class RetrieveResult:
    query: str
    chunks: list[RAGChunk] = field(default_factory=list)
    index_hit: bool = True
