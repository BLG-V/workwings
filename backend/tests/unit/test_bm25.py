from __future__ import annotations

from mawp.rag.bm25 import BM25Index


def test_bm25_prefers_matching_document() -> None:
    index = BM25Index()
    index.build(
        [
            ("a", "user authentication login module"),
            ("b", "database migration script"),
        ]
    )
    scores = index.score("login authentication", top_k=2)
    assert scores
    assert scores[0][0] == "a"
