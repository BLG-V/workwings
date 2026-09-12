from __future__ import annotations

import hashlib
import math
import os
from typing import Any

import httpx

from mawp.config.loader import AgentConfig

EMBED_DIM = 384


class HashEmbeddingFunction:
    """轻量本地嵌入：无需 API、无需下载模型（Phase 1 默认）。"""

    def __init__(self, dim: int = EMBED_DIM):
        self.dim = dim

    def name(self) -> str:
        return "hash-local"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _tokenize(text)
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    __call__ = embed


def _tokenize(text: str) -> list[str]:
    return [t for t in text.lower().split() if t.strip()]


class OpenAIEmbeddingFunction:
    """OpenAI 兼容 Embedding API（可选）。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def name(self) -> str:
        return f"openai:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"model": self.model, "input": texts}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Embedding API 错误 ({response.status_code}): {response.text}"
            )
        data = response.json().get("data") or []
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in ordered]

    __call__ = embed


def resolve_embedding_api_key(config: AgentConfig) -> str | None:
    env_name = config.rag.embedding.api_key_env
    for candidate in (env_name, "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        value = os.environ.get(candidate)
        if value:
            return value
    return None


def create_embedding_function(config: AgentConfig) -> HashEmbeddingFunction | OpenAIEmbeddingFunction:
    provider = config.rag.embedding.provider.lower()
    if provider == "openai":
        api_key = resolve_embedding_api_key(config)
        if not api_key:
            raise RuntimeError(
                f"RAG embedding provider=openai 但未找到 API Key（{config.rag.embedding.api_key_env}）"
            )
        base_url = config.rag.embedding.base_url or "https://api.openai.com/v1"
        return OpenAIEmbeddingFunction(
            api_key=api_key,
            model=config.rag.embedding.model,
            base_url=base_url,
        )
    return HashEmbeddingFunction()
