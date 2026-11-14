"""Small TTL cache used for upstream snapshots. Redis optional, memory otherwise."""

from __future__ import annotations

import threading
import time
from typing import Any

from app.core.config import settings

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


class _RedisCache:
    def __init__(self, client) -> None:  # type: ignore[no-untyped-def]
        self.client = client

    def get(self, key: str) -> Any | None:
        import json

        raw = self.client.get(f"nexus:cache:{key}")
        return json.loads(raw) if raw else None

    def set(self, key: str, value: Any, ttl: int) -> None:
        import json

        self.client.setex(f"nexus:cache:{key}", ttl, json.dumps(value, default=str))


_redis_cache: _RedisCache | None = None
if settings.redis_url:
    try:
        import redis

        _client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1.5, socket_timeout=1.5)
        _client.ping()
        _redis_cache = _RedisCache(_client)
    except Exception:  # pragma: no cover
        _redis_cache = None


def cache_get(key: str) -> Any | None:
    if _redis_cache is not None:
        try:
            return _redis_cache.get(key)
        except Exception:  # pragma: no cover
            pass
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            _store.pop(key, None)
            return None
        return value


def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    if _redis_cache is not None:
        try:
            _redis_cache.set(key, value, ttl_seconds)
            return
        except Exception:  # pragma: no cover
            pass
    with _lock:
        _store[key] = (time.time() + ttl_seconds, value)
