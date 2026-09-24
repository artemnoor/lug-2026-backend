"""Async-safe fixed-window rate limiting with a Redis seam."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LimitResult:
    allowed: bool
    remaining: int
    retry_after: int


class RateLimiter(Protocol):
    name: str

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> LimitResult: ...

    async def ready(self) -> bool: ...

    async def close(self) -> None: ...


class MemoryRateLimiter:
    name = "memory"

    def __init__(self) -> None:
        self._values: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> LimitResult:
        now = time.monotonic()
        async with self._lock:
            count, expires = self._values.get(key, (0, now + window_seconds))
            if expires <= now:
                count, expires = 0, now + window_seconds
            count += 1
            self._values[key] = (count, expires)
            if len(self._values) > 10_000:
                self._values = {k: v for k, v in self._values.items() if v[1] > now}
            return LimitResult(count <= limit, max(0, limit - count), max(1, int(expires - now)))

    async def ready(self) -> bool:
        return True

    async def close(self) -> None:
        self._values.clear()


class RedisRateLimiter:
    name = "redis"

    def __init__(self, url: str) -> None:
        from redis.asyncio import Redis

        self._client = Redis.from_url(
            url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3
        )

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> LimitResult:
        namespaced = f"lug:rate:{key}"
        try:
            count = int(await self._client.incr(namespaced))
            if count == 1:
                await self._client.expire(namespaced, window_seconds)
            ttl = int(await self._client.ttl(namespaced))
            return LimitResult(count <= limit, max(0, limit - count), max(1, ttl))
        except Exception:
            # Availability of rate limiting must not become an opaque 500. In a
            # degraded state the caller can fail closed for hardened environments.
            return LimitResult(False, 0, 5)

    async def ready(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()


async def create_rate_limiter(url: str) -> RateLimiter:
    return RedisRateLimiter(url) if url else MemoryRateLimiter()
