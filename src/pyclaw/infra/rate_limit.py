"""Rate limiting — token bucket and sliding window for gateway/API protection.

Ported from ``src/gateway/control-plane-rate-limit.ts``.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    """Sliding-window rate limit configuration."""

    max_requests: int = 3
    window_seconds: float = 60.0


DEFAULT_CONTROL_PLANE_LIMIT = RateLimitConfig(max_requests=3, window_seconds=60.0)
DEFAULT_AUTH_LIMIT = RateLimitConfig(max_requests=5, window_seconds=300.0)


class RateLimitExceeded(Exception):
    """Raised when a rate limit is hit."""

    def __init__(self, message: str, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class SlidingWindowLimiter:
    """Sliding-window rate limiter keyed by an identifier (e.g. IP address).

    Tracks timestamps of past requests per key and rejects requests
    that exceed the configured limit within the window.
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self._config = config or DEFAULT_CONTROL_PLANE_LIMIT
        self._windows: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        """Check if the request is allowed. Raises ``RateLimitExceeded`` if not."""
        now = time.monotonic()
        window = self._windows[key]

        # Evict expired timestamps
        cutoff = now - self._config.window_seconds
        self._windows[key] = window = [ts for ts in window if ts > cutoff]

        if len(window) >= self._config.max_requests:
            oldest = window[0]
            retry_after = oldest + self._config.window_seconds - now
            raise RateLimitExceeded(
                f"Rate limit exceeded ({self._config.max_requests} requests per "
                f"{self._config.window_seconds}s). Retry after {retry_after:.1f}s.",
                retry_after=max(0.0, retry_after),
            )

        window.append(now)

    def reset(self, key: str) -> None:
        """Clear rate limit state for a key."""
        self._windows.pop(key, None)

    def reset_all(self) -> None:
        """Clear all rate limit state."""
        self._windows.clear()


class AuthBruteForceLimiter:
    """Brute-force protection for authentication endpoints.

    Tracks failed auth attempts per key and enforces a lockout
    after too many failures.
    """

    def __init__(
        self,
        *,
        max_failures: int = 5,
        lockout_seconds: float = 300.0,
    ) -> None:
        self._max_failures = max_failures
        self._lockout_seconds = lockout_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lockout_until: dict[str, float] = {}

    def check(self, key: str) -> None:
        """Check if the key is locked out. Raises ``RateLimitExceeded`` if so."""
        now = time.monotonic()
        lockout = self._lockout_until.get(key)
        if lockout and now < lockout:
            retry_after = lockout - now
            raise RateLimitExceeded(
                f"Too many failed attempts. Locked out for {retry_after:.0f}s.",
                retry_after=retry_after,
            )
        # Evict old failures
        cutoff = now - self._lockout_seconds
        self._failures[key] = [ts for ts in self._failures[key] if ts > cutoff]

    def record_failure(self, key: str) -> None:
        """Record a failed attempt."""
        now = time.monotonic()
        self._failures[key].append(now)
        cutoff = now - self._lockout_seconds
        self._failures[key] = [ts for ts in self._failures[key] if ts > cutoff]

        if len(self._failures[key]) >= self._max_failures:
            self._lockout_until[key] = now + self._lockout_seconds

    def record_success(self, key: str) -> None:
        """Clear failure state on successful auth."""
        self._failures.pop(key, None)
        self._lockout_until.pop(key, None)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
        self._lockout_until.pop(key, None)
