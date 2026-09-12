from __future__ import annotations

import ast
import hashlib
from typing import Any

from mawp.rag.models import CodeChunk


def _node_lines(content: str, node: ast.AST) -> tuple[int, int]:
    start = getattr(node, "lineno", 1) or 1
    end = getattr(node, "end_lineno", start) or start
    return start, end


def _slice_lines(content: str, start_line: int, end_line: int) -> str:
    lines = content.splitlines()
    return "\n".join(lines[start_line - 1 : end_line])


def chunk_python_ast(rel_path: str, content: str) -> list[CodeChunk]:
    """按函数/类切分 Python 文件；失败时返回空列表。"""
    if not content.strip():
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    chunks: list[CodeChunk] = []
    index = 0

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start_line, end_line = _node_lines(content, node)
        piece = _slice_lines(content, start_line, end_line).strip()
        if not piece:
            continue
        symbol = getattr(node, "name", "block")
        chunks.append(
            CodeChunk(
                chunk_id=f"{rel_path}::ast::{index}",
                path=rel_path,
                content=piece,
                start_line=start_line,
                end_line=end_line,
                language="python",
                content_hash=content_hash,
            )
        )
        index += 1

    if chunks:
        return chunks

    return [
        CodeChunk(
            chunk_id=f"{rel_path}::0",
            path=rel_path,
            content=content,
            start_line=1,
            end_line=max(content.count("\n") + 1, 1),
            language="python",
            content_hash=content_hash,
        )
    ]
