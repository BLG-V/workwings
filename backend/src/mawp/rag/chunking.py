from __future__ import annotations

import hashlib
from pathlib import Path

import pathspec

from mawp.config.loader import AgentConfig
from mawp.rag.ast_chunking import chunk_python_ast
from mawp.rag.models import CodeChunk

INDEX_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".rs",
    ".java",
    ".kt",
    ".sql",
    ".html",
    ".css",
    ".vue",
    ".txt",
}

MAX_FILE_BYTES = 512 * 1024
LANGUAGE_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def _load_gitignore_spec(workspace: Path) -> pathspec.PathSpec | None:
    gitignore = workspace / ".gitignore"
    if not gitignore.is_file():
        return None
    lines = gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
    return pathspec.PathSpec.from_lines("gitignore", lines)


def _exclude_spec(config: AgentConfig) -> pathspec.PathSpec:
    return pathspec.PathSpec.from_lines("gitignore", config.rag.exclude)


def collect_indexable_files(workspace: Path, config: AgentConfig) -> list[Path]:
    workspace = workspace.resolve()
    gitignore = _load_gitignore_spec(workspace)
    exclude = _exclude_spec(config)
    files: list[Path] = []

    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if exclude.match_file(rel):
            continue
        if gitignore is not None and gitignore.match_file(rel):
            continue
        if path.suffix.lower() not in INDEX_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        files.append(path)

    return sorted(files)


def _read_text(path: Path) -> str | None:
    raw = path.read_bytes()
    if b"\x00" in raw[:4096]:
        return None
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _line_range(content: str, start_char: int, end_char: int) -> tuple[int, int]:
    prefix = content[:start_char]
    chunk = content[start_char:end_char]
    start_line = prefix.count("\n") + 1
    end_line = start_line + max(chunk.count("\n"), 0)
    return start_line, end_line


def chunk_file_content(
    rel_path: str,
    content: str,
    *,
    chunk_size: int,
    overlap: int,
    language: str = "",
) -> list[CodeChunk]:
    if not content.strip():
        return []

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    if len(content) <= chunk_size:
        return [
            CodeChunk(
                chunk_id=f"{rel_path}::0",
                path=rel_path,
                content=content,
                start_line=1,
                end_line=max(content.count("\n") + 1, 1),
                language=language,
                content_hash=content_hash,
            )
        ]

    chunks: list[CodeChunk] = []
    step = max(chunk_size - overlap, 1)
    index = 0
    offset = 0
    while offset < len(content):
        piece = content[offset : offset + chunk_size]
        if not piece.strip():
            break
        start_line, end_line = _line_range(content, offset, offset + len(piece))
        chunks.append(
            CodeChunk(
                chunk_id=f"{rel_path}::{index}",
                path=rel_path,
                content=piece,
                start_line=start_line,
                end_line=end_line,
                language=language,
                content_hash=content_hash,
            )
        )
        index += 1
        offset += step

    return chunks


def build_chunks_for_file(
    workspace: Path,
    file_path: Path,
    config: AgentConfig,
) -> list[CodeChunk]:
    rel = file_path.relative_to(workspace).as_posix()
    text = _read_text(file_path)
    if text is None:
        return []
    language = LANGUAGE_BY_EXT.get(file_path.suffix.lower(), "")
    if (
        config.rag.use_ast_chunking
        and file_path.suffix.lower() == ".py"
    ):
        ast_chunks = chunk_python_ast(rel, text)
        if ast_chunks:
            return ast_chunks
    return chunk_file_content(
        rel,
        text,
        chunk_size=config.rag.chunk_size_chars,
        overlap=config.rag.chunk_overlap_chars,
        language=language,
    )


def build_all_chunks(workspace: Path, config: AgentConfig) -> tuple[list[CodeChunk], int, int]:
    files = collect_indexable_files(workspace, config)
    all_chunks: list[CodeChunk] = []
    indexed = 0
    skipped = 0

    for file_path in files:
        chunks = build_chunks_for_file(workspace, file_path, config)
        if chunks:
            all_chunks.extend(chunks)
            indexed += 1
        else:
            skipped += 1

    return all_chunks, len(files), indexed
