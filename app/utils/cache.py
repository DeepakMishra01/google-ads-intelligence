"""A tiny thread-safe in-process TTL cache.

Used to keep hot dashboard aggregates under the latency budget without pulling in
Redis for Phase 2. Values are cached for a short TTL (seconds); data freshness is
bounded by the sync cadence anyway, so a 30-60s cache is safe. Swap this for a
shared Redis cache if the console is scaled horizontally.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

_MISS = object()


class TTLCache:
    def __init__(self, default_ttl: float = 30.0, max_size: int = 512) -> None:
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            item = self._store.get(key, _MISS)
            if item is _MISS:
                return _MISS
            expires_at, value = item
            if time.monotonic() >= expires_at:
                self._store.pop(key, None)
                return _MISS
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            if len(self._store) >= self._max_size:
                # Cheap eviction: drop the soonest-to-expire entry.
                oldest = min(self._store, key=lambda k: self._store[k][0])
                self._store.pop(oldest, None)
            self._store[key] = (time.monotonic() + (ttl or self._default_ttl), value)

    def get_or_set(self, key: str, producer: Callable[[], Any], ttl: float | None = None) -> Any:
        cached = self.get(key)
        if cached is not _MISS:
            return cached
        value = producer()
        self.set(key, value, ttl)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# Shared cache for dashboard aggregates.
dashboard_cache = TTLCache(default_ttl=45.0)
