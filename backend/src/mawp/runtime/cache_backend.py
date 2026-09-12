"""可插拔缓存：默认 memory，MAWP_CACHE_BACKEND=redis 时尝试 Redis。

不新增 Agent。缺 redis 包或连不上时自动降级 memory，保证实训可跑。
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Cache(Protocol):
    backend_name: str

    def get(self, key: str) -> Any: ...

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None: ...

    def delete(self, key: str) -> None: ...


class MemoryCache:
    backend_name = "memory"

    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, float | None]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            value, expires = item
            if expires is not None and time.time() > expires:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        expires = time.time() + max(0, int(ttl_seconds)) if ttl_seconds else None
        with self._lock:
            self._data[key] = (value, expires)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


class RedisCache:
    backend_name = "redis"

    def __init__(self, redis_url: str) -> None:
        import redis  # type: ignore

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._client.ping()

    def get(self, key: str) -> Any:
        raw = self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        if ttl_seconds and ttl_seconds > 0:
            self._client.setex(key, int(ttl_seconds), payload)
        else:
            self._client.set(key, payload)

    def delete(self, key: str) -> None:
        self._client.delete(key)


_CACHE: Cache | None = None
_LOCK = threading.Lock()


def make_cache(backend: str | None = None, *, redis_url: str | None = None) -> Cache:
    name = (backend or os.environ.get("MAWP_CACHE_BACKEND") or "memory").strip().lower()
    url = redis_url or os.environ.get("REDIS_URL") or "redis://127.0.0.1:6379/0"
    if name == "redis":
        try:
            return RedisCache(url)
        except Exception:  # noqa: BLE001
            return MemoryCache()
    return MemoryCache()


def get_cache(*, force_new: bool = False) -> Cache:
    global _CACHE
    if force_new:
        with _LOCK:
            _CACHE = make_cache()
            return _CACHE
    if _CACHE is None:
        with _LOCK:
            if _CACHE is None:
                _CACHE = make_cache()
    return _CACHE
