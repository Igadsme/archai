"""Per-client request rate limiting shared across API processes.

`RedisRateLimiter` keeps fixed one-minute windows in Redis (INCR + EXPIRE) so every API
replica enforces one shared budget. If Redis errors, it degrades to an in-process
sliding window instead of failing open, and reports which backend made the decision.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    count: int
    limit: int
    backend: str


class InProcessRateLimiter:
    backend = "in_process"

    def __init__(self, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.window_seconds, self.clock = window_seconds, clock
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int) -> RateDecision:
        now = self.clock()
        with self._lock:
            window = self._windows[key]
            while window and now - window[0] >= self.window_seconds:
                window.popleft()
            if len(window) >= limit:
                return RateDecision(False, len(window), limit, self.backend)
            window.append(now)
            return RateDecision(True, len(window), limit, self.backend)

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


class RedisRateLimiter:
    backend = "redis"

    def __init__(self, client, *, prefix: str = "archai", window_seconds: int = 60,
                 clock: Callable[[], float] = time.time,
                 fallback: InProcessRateLimiter | None = None):
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.client, self.prefix, self.window_seconds, self.clock = client, prefix, window_seconds, clock
        self.fallback = fallback or InProcessRateLimiter(float(window_seconds))
        self.last_error: str | None = None

    def _key(self, key: str) -> str:
        bucket = int(self.clock() // self.window_seconds)
        return f"{self.prefix}:ratelimit:{key}:{bucket}"

    def hit(self, key: str, limit: int) -> RateDecision:
        redis_key = self._key(key)
        try:
            pipe = self.client.pipeline(transaction=True)
            pipe.incr(redis_key)
            pipe.expire(redis_key, self.window_seconds * 2)
            count = int(pipe.execute()[0])
        except Exception as exc:  # noqa: BLE001 - any Redis failure degrades to local limiting
            self.last_error = f"{type(exc).__name__}: {exc}"
            decision = self.fallback.hit(key, limit)
            return RateDecision(decision.allowed, decision.count, limit, "in_process_fallback")
        self.last_error = None
        return RateDecision(count <= limit, count, limit, self.backend)

    def reset(self) -> None:
        self.fallback.reset()


def make_rate_limiter(url: str | None = None):
    """Redis-backed limiter when a URL and the redis client are available, else in-process."""
    url = url if url is not None else (os.getenv("ARCHAI_RATE_LIMIT_REDIS_URL")
                                       or os.getenv("ARCHAI_REDIS_URL"))
    if not url:
        return InProcessRateLimiter()
    try:
        import redis
    except ImportError:
        return InProcessRateLimiter()
    return RedisRateLimiter(redis.Redis.from_url(url, decode_responses=True,
                                                 socket_timeout=0.5, socket_connect_timeout=0.5))
