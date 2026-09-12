from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb

from mawp.config.loader import AgentConfig
from mawp.rag.chunking import build_all_chunks
from mawp.rag.embeddings import create_embedding_function
from mawp.rag.models import IndexStats


class RAGIndexer:
    BATCH_SIZE = 64

    def __init__(self, config: AgentConfig):
        self.config = config
        self.workspace = config.workspace_path()
        self.index_path = config.rag_index_path()
        self.collection_name = self._collection_name(self.workspace)
        self.embedder = create_embedding_function(config)

    @staticmethod
    def _collection_name(workspace: Path) -> str:
        digest = hashlib.sha256(str(workspace.resolve()).encode("utf-8")).hexdigest()
        return f"code_{digest[:12]}"

    def manifest_path(self) -> Path:
        return self.index_path / "manifest.json"

    def is_indexed(self) -> bool:
        manifest = self._read_manifest()
        if manifest is None:
            return False
        return (
            manifest.get("workspace") == str(self.workspace)
            and manifest.get("collection") == self.collection_name
            and int(manifest.get("chunks_indexed") or 0) > 0
        )

    def build(self, *, force: bool = False) -> IndexStats:
        start = time.perf_counter()
        if self.is_indexed() and not force:
            manifest = self._read_manifest() or {}
            return IndexStats(
                files_scanned=int(manifest.get("files_scanned") or 0),
                files_indexed=int(manifest.get("files_indexed") or 0),
                chunks_indexed=int(manifest.get("chunks_indexed") or 0),
                skipped=int(manifest.get("skipped") or 0),
                duration_ms=0,
                collection=self.collection_name,
                index_path=str(self.index_path),
                rebuilt=False,
            )

        self.index_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.index_path))
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            pass
        collection = client.create_collection(name=self.collection_name)

        chunks, files_scanned, files_indexed = build_all_chunks(
            self.workspace, self.config
        )
        skipped = files_scanned - files_indexed

        for batch_start in range(0, len(chunks), self.BATCH_SIZE):
            batch = chunks[batch_start : batch_start + self.BATCH_SIZE]
            documents = [c.content for c in batch]
            embeddings = self.embedder.embed(documents)
            metadatas: list[dict[str, Any]] = [
                {
                    "path": c.path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "language": c.language,
                    "content_hash": c.content_hash,
                }
                for c in batch
            ]
            collection.add(
                ids=[c.chunk_id for c in batch],
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )

        duration_ms = int((time.perf_counter() - start) * 1000)
        stats = IndexStats(
            files_scanned=files_scanned,
            files_indexed=files_indexed,
            chunks_indexed=len(chunks),
            skipped=skipped,
            duration_ms=duration_ms,
            collection=self.collection_name,
            index_path=str(self.index_path),
            rebuilt=True,
        )
        self._write_manifest(stats, chunks)
        return stats

    def search_index_path(self) -> Path:
        return self.index_path / "search_index.json"

    def _write_manifest(self, stats: IndexStats, chunks: list[Any]) -> None:
        payload = {
            **stats.to_dict(),
            "workspace": str(self.workspace),
            "embedding": self.embedder.name(),
            "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        self.manifest_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        catalog = [
            {
                "chunk_id": c.chunk_id,
                "path": c.path,
                "content": c.content,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "language": c.language,
            }
            for c in chunks
        ]
        self.search_index_path().write_text(
            json.dumps(catalog, ensure_ascii=False),
            encoding="utf-8",
        )

    def _read_manifest(self) -> dict[str, Any] | None:
        path = self.manifest_path()
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
