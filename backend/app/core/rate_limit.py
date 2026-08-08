"""In-process sliding-window rate limiter for the public endpoint.

Deliberately simple: a per-IP deque of hit timestamps in local memory. That is
correct for a single instance and enough to blunt casual form spam. It does not
survive a restart and does not coordinate across replicas — a real deployment
would move this to Redis or the edge. Called out in SYSTEM_OVERVIEW.md.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitedError


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, identity: str) -> None:
        now = time.monotonic()
        cutoff = now - self._window

        with self._lock:
            bucket = self._hits[identity]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self._limit:
                retry_after = int(bucket[0] - cutoff) + 1
                raise RateLimitedError(
                    "Too many submissions. Please try again in a moment.",
                    details={"retry_after_seconds": retry_after},
                )

            bucket.append(now)

            # Opportunistic cleanup so idle IPs don't accumulate forever.
            if len(self._hits) > 10_000:
                for key in [k for k, v in self._hits.items() if not v]:
                    del self._hits[key]


_public_submit_limiter = SlidingWindowRateLimiter(
    limit=settings.public_submit_rate_limit,
    window_seconds=settings.public_submit_rate_window_seconds,
)


def client_identity(request: Request) -> str:
    """Best-effort client IP.

    X-Forwarded-For is trusted only because this sits behind a proxy we
    control; exposed directly, it would be trivially spoofed.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_public_submit_rate_limit(request: Request) -> None:
    _public_submit_limiter.check(client_identity(request))
