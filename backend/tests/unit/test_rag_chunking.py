from __future__ import annotations

from pathlib import Path

from mawp.config.loader import AgentConfig
from mawp.rag.chunking import build_all_chunks, chunk_file_content, collect_indexable_files


def test_collect_indexable_files_respects_gitignore(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    config = AgentConfig(workspace=str(tmp_path))
    files = collect_indexable_files(tmp_path, config)
    rel_paths = {f.relative_to(tmp_path).as_posix() for f in files}
    assert "src/app.py" in rel_paths
    assert "node_modules/pkg.js" not in rel_paths


def test_chunk_file_content_sliding_window() -> None:
    content = "line\n" * 2000
    chunks = chunk_file_content(
        "src/big.py",
        content,
        chunk_size=100,
        overlap=20,
        language="python",
    )
    assert len(chunks) > 1
    assert chunks[0].path == "src/big.py"
    assert chunks[0].start_line == 1


def test_build_all_chunks(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text(
        "def login(email, password):\n    return True\n",
        encoding="utf-8",
    )
    config = AgentConfig(workspace=str(tmp_path))
    chunks, scanned, indexed = build_all_chunks(tmp_path, config)
    assert scanned == 1
    assert indexed == 1
    assert len(chunks) == 1
    assert "login" in chunks[0].content
