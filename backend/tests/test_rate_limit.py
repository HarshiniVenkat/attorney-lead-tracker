"""Unit tests for the public-endpoint rate limiter.

Exercised directly rather than through the API: the limiter keeps counters in
process memory, so driving it via HTTP would leak state between tests.
"""

from __future__ import annotations

import pytest

from app.core.errors import RateLimitedError
from app.core.rate_limit import SlidingWindowRateLimiter


def test_requests_under_the_limit_pass():
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60)

    for _ in range(3):
        limiter.check("1.2.3.4")


def test_exceeding_the_limit_raises():
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60)
    for _ in range(3):
        limiter.check("1.2.3.4")

    with pytest.raises(RateLimitedError) as exc_info:
        limiter.check("1.2.3.4")

    assert exc_info.value.status_code == 429
    assert exc_info.value.details["retry_after_seconds"] > 0


def test_clients_are_counted_independently():
    """One noisy IP must not lock everyone else out."""
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)

    limiter.check("1.1.1.1")
    limiter.check("1.1.1.1")
    with pytest.raises(RateLimitedError):
        limiter.check("1.1.1.1")

    # A different client still has its full budget.
    limiter.check("2.2.2.2")
    limiter.check("2.2.2.2")


def test_window_expiry_restores_the_budget(monkeypatch):
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)

    now = 1_000.0
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: now)

    limiter.check("1.2.3.4")
    limiter.check("1.2.3.4")
    with pytest.raises(RateLimitedError):
        limiter.check("1.2.3.4")

    # Step past the window; the earlier hits should have aged out.
    now += 61
    limiter.check("1.2.3.4")
    limiter.check("1.2.3.4")
