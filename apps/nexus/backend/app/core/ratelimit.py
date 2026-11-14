"""Rate limiting with an optional Redis backend and an in-process fallback."""

from __future__ import annotations

import threading
import time
from collections import deque

from app.core.config import settings


class _MemoryLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + window_seconds - now))
                return False, retry_after
            bucket.append(now)
            if len(self._buckets) > 5000:
                for stale in [k for k, v in self._buckets.items() if not v or v[-1] < cutoff]:
                    self._buckets.pop(stale, None)
            return True, 0


class _RedisLimiter:
    def __init__(self, client) -> None:  # type: ignore[no-untyped-def]
        self._client = client

    def allow(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        bucket = f"nexus:rl:{key}:{int(time.time()) // window_seconds}"
        count = int(self._client.incr(bucket))
        if count == 1:
            self._client.expire(bucket, window_seconds + 1)
        if count > limit:
            return False, window_seconds
        return True, 0


_memory = _MemoryLimiter()
_backend: _MemoryLimiter | _RedisLimiter = _memory


def _init_redis() -> None:
    global _backend
    if not settings.redis_url:
        return
    try:
        import redis  # local import so Redis stays optional

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1.5, socket_timeout=1.5)
        client.ping()
        _backend = _RedisLimiter(client)
    except Exception:  # pragma: no cover - depends on deployment infrastructure
        _backend = _memory


_init_redis()


def check_rate_limit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    return _backend.allow(key, limit, window_seconds)
