"""Control plane rate limiting — per device+IP sliding window.

Ported from ``src/gateway/control-plane-rate-limit.ts``.

Provides:
- Per device+IP write rate limiting (default: 3 req/60s)
- Sliding window implementation
- Configurable limits and window size
- Rate limit status reporting
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RateLimitConfig:
    """Configuration for control plane rate limiting."""
    max_requests: int = 3
    window_s: float = 60.0
    enabled: bool = True


@dataclass
class RateLimitEntry:
    """Timestamps of recent requests for a single key."""
    timestamps: list[float] = field(default_factory=list)

    def prune(self, window_s: float, now: float | None = None) -> None:
        cutoff = (now or time.time()) - window_s
        self.timestamps = [t for t in self.timestamps if t > cutoff]


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    retry_after_s: float = 0.0
    total_limit: int = 0


class ControlPlaneRateLimiter:
    """Sliding window rate limiter keyed by device_id + IP."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self._config = config or RateLimitConfig()
        self._entries: dict[str, RateLimitEntry] = {}

    @staticmethod
    def _make_key(device_id: str, ip: str) -> str:
        return f"{device_id}:{ip}"

    def check(self, device_id: str, ip: str) -> RateLimitResult:
        """Check if a request is allowed (does not consume)."""
        if not self._config.enabled:
            return RateLimitResult(allowed=True, remaining=self._config.max_requests, total_limit=self._config.max_requests)

        key = self._make_key(device_id, ip)
        entry = self._entries.get(key)
        if not entry:
            return RateLimitResult(
                allowed=True,
                remaining=self._config.max_requests,
                total_limit=self._config.max_requests,
            )

        now = time.time()
        entry.prune(self._config.window_s, now)
        count = len(entry.timestamps)
        remaining = max(0, self._config.max_requests - count)

        if count >= self._config.max_requests:
            oldest = entry.timestamps[0] if entry.timestamps else now
            retry_after = oldest + self._config.window_s - now
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after_s=max(0, retry_after),
                total_limit=self._config.max_requests,
            )

        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            total_limit=self._config.max_requests,
        )

    def consume(self, device_id: str, ip: str) -> RateLimitResult:
        """Consume a request slot. Returns whether it was allowed."""
        result = self.check(device_id, ip)
        if not result.allowed:
            return result

        key = self._make_key(device_id, ip)
        if key not in self._entries:
            self._entries[key] = RateLimitEntry()

        self._entries[key].timestamps.append(time.time())
        result.remaining = max(0, result.remaining - 1)
        return result

    def reset(self, device_id: str, ip: str) -> None:
        key = self._make_key(device_id, ip)
        self._entries.pop(key, None)

    def reset_all(self) -> None:
        self._entries.clear()

    def cleanup(self) -> int:
        """Remove expired entries. Returns count removed."""
        now = time.time()
        to_remove: list[str] = []
        for key, entry in self._entries.items():
            entry.prune(self._config.window_s, now)
            if not entry.timestamps:
                to_remove.append(key)
        for key in to_remove:
            del self._entries[key]
        return len(to_remove)

    @property
    def active_keys(self) -> int:
        return len(self._entries)
