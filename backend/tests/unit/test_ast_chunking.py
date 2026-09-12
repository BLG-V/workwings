from __future__ import annotations

from mawp.rag.ast_chunking import chunk_python_ast


def test_chunk_python_ast_splits_functions() -> None:
    content = (
        "def add(a, b):\n"
        "    return a + b\n\n"
        "class Calculator:\n"
        "    def mul(self, x, y):\n"
        "        return x * y\n"
    )
    chunks = chunk_python_ast("src/math.py", content)
    assert len(chunks) >= 2
    assert any("def add" in c.content for c in chunks)
    assert any("class Calculator" in c.content for c in chunks)
