from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass


_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+|\d+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text)]


@dataclass
class BM25Document:
    doc_id: str
    tokens: list[str]
    length: int


class BM25Index:
    """轻量 BM25 关键词检索索引。"""

    def __init__(self, *, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: list[BM25Document] = []
        self.avgdl = 0.0
        self.df: Counter[str] = Counter()
        self._built = False

    def build(self, documents: list[tuple[str, str]]) -> None:
        self.documents = []
        self.df = Counter()
        total_len = 0
        for doc_id, text in documents:
            tokens = tokenize(text)
            total_len += len(tokens)
            for term in set(tokens):
                self.df[term] += 1
            self.documents.append(
                BM25Document(doc_id=doc_id, tokens=tokens, length=len(tokens))
            )
        self.avgdl = total_len / max(len(self.documents), 1)
        self._built = True

    def score(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        if not self._built or not self.documents:
            return []
        query_terms = tokenize(query)
        if not query_terms:
            return []
        n_docs = len(self.documents)
        scores: list[tuple[str, float]] = []

        for doc in self.documents:
            tf = Counter(doc.tokens)
            total = 0.0
            for term in query_terms:
                if term not in tf:
                    continue
                df = self.df.get(term, 0)
                idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * doc.length / self.avgdl)
                total += idf * (freq * (self.k1 + 1)) / denom
            if total > 0:
                scores.append((doc.doc_id, total))

        scores.sort(key=lambda item: item[1], reverse=True)
        return scores[:top_k]
