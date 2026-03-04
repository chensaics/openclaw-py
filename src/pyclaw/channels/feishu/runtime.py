"""Feishu runtime optimizations — probe caching, typing backoff, webhook rate limiting.

Ported from various ``extensions/feishu/src/`` modules.

Provides:
- Probe result caching (10-min TTL per account)
- Typing indicator backoff with circuit breaker for rate-limit/quota errors
- Webhook ingress rate limiting with stale-window pruning
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PROBE_CACHE_TTL_S = 600.0  # 10 minutes
DEFAULT_RATE_LIMIT_WINDOW_S = 60.0
DEFAULT_RATE_LIMIT_MAX_REQUESTS = 100
DEFAULT_RATE_LIMIT_MAX_KEYS = 10000


# ---------------------------------------------------------------------------
# Probe caching
# ---------------------------------------------------------------------------


@dataclass
class ProbeCacheEntry:
    """Cached probe result for a Feishu account."""

    bot_info: dict[str, Any]
    cached_at: float
    success: bool = True


class ProbeCache:
    """TTL-bounded cache for Feishu probe results (bot info)."""

    def __init__(self, ttl_s: float = DEFAULT_PROBE_CACHE_TTL_S) -> None:
        self._ttl_s = ttl_s
        self._cache: dict[str, ProbeCacheEntry] = {}

    def get(self, account_key: str) -> dict[str, Any] | None:
        """Get cached probe result, or None if expired/missing."""
        entry = self._cache.get(account_key)
        if entry is None:
            return None
        if not entry.success:
            return None
        if time.time() - entry.cached_at > self._ttl_s:
            del self._cache[account_key]
            return None
        return entry.bot_info

    def put(self, account_key: str, bot_info: dict[str, Any], *, success: bool = True) -> None:
        """Cache a probe result. Failures are not cached."""
        if not success:
            return
        self._cache[account_key] = ProbeCacheEntry(
            bot_info=bot_info,
            cached_at=time.time(),
            success=success,
        )

    def invalidate(self, account_key: str) -> None:
        self._cache.pop(account_key, None)

    def clear(self) -> None:
        self._cache.clear()


# ---------------------------------------------------------------------------
# Typing backoff
# ---------------------------------------------------------------------------

RATE_LIMIT_CODES = {429, 99991400, 99991403}


@dataclass
class TypingBackoffState:
    """State for typing indicator backoff on rate-limit errors."""

    consecutive_failures: int = 0
    suppressed_until: float = 0.0
    total_failures: int = 0

    @property
    def is_suppressed(self) -> bool:
        return time.time() < self.suppressed_until


class TypingBackoff:
    """Circuit-breaker for Feishu typing indicators.

    Stops retrying typing indicator API calls after rate-limit or quota
    errors, applying exponential backoff before resuming.
    """

    def __init__(self, *, max_consecutive: int = 3, base_delay_s: float = 10.0, max_delay_s: float = 120.0) -> None:
        self._max_consecutive = max_consecutive
        self._base_delay = base_delay_s
        self._max_delay = max_delay_s
        self._states: dict[str, TypingBackoffState] = {}

    def should_send(self, chat_id: str) -> bool:
        """Check if typing indicator should be sent for this chat."""
        state = self._states.get(chat_id)
        if state is None:
            return True
        return not state.is_suppressed

    def record_success(self, chat_id: str) -> None:
        """Record a successful typing API call."""
        state = self._states.get(chat_id)
        if state:
            state.consecutive_failures = 0

    def record_failure(self, chat_id: str, *, error_code: int = 0) -> None:
        """Record a typing API failure.

        If the error is a rate-limit/quota error, apply suppression backoff.
        """
        if chat_id not in self._states:
            self._states[chat_id] = TypingBackoffState()

        state = self._states[chat_id]
        state.consecutive_failures += 1
        state.total_failures += 1

        if error_code in RATE_LIMIT_CODES or state.consecutive_failures >= self._max_consecutive:
            delay = min(
                self._base_delay * (2 ** (state.consecutive_failures - 1)),
                self._max_delay,
            )
            state.suppressed_until = time.time() + delay
            logger.info(
                "Feishu typing suppressed for %s (%.0fs, code=%d)",
                chat_id,
                delay,
                error_code,
            )

    def reset(self, chat_id: str) -> None:
        self._states.pop(chat_id, None)


# ---------------------------------------------------------------------------
# Webhook ingress rate limiter
# ---------------------------------------------------------------------------


@dataclass
class _RateLimitBucket:
    """Per-key rate limit bucket."""

    timestamps: list[float] = field(default_factory=list)
    first_seen: float = 0.0

    def __post_init__(self) -> None:
        if self.first_seen == 0.0:
            self.first_seen = time.time()


class WebhookRateLimiter:
    """Rate limiter for Feishu webhook ingress.

    Bounds unauthenticated webhook request rates per source key
    with stale-window pruning and hard key cap to prevent unbounded
    pre-auth memory growth.
    """

    def __init__(
        self,
        *,
        window_s: float = DEFAULT_RATE_LIMIT_WINDOW_S,
        max_requests: int = DEFAULT_RATE_LIMIT_MAX_REQUESTS,
        max_keys: int = DEFAULT_RATE_LIMIT_MAX_KEYS,
    ) -> None:
        self._window_s = window_s
        self._max_requests = max_requests
        self._max_keys = max_keys
        self._buckets: dict[str, _RateLimitBucket] = {}

    def check(self, key: str) -> bool:
        """Check if a request from this key is allowed.

        Returns True if allowed, False if rate-limited.
        """
        now = time.time()
        self._prune_stale(now)

        if key not in self._buckets:
            if len(self._buckets) >= self._max_keys:
                # Hard cap reached, reject
                return False
            self._buckets[key] = _RateLimitBucket()

        bucket = self._buckets[key]

        # Remove timestamps outside window
        cutoff = now - self._window_s
        bucket.timestamps = [t for t in bucket.timestamps if t > cutoff]

        if len(bucket.timestamps) >= self._max_requests:
            return False

        bucket.timestamps.append(now)
        return True

    def _prune_stale(self, now: float) -> None:
        """Remove buckets that haven't been used within 2x the window."""
        if len(self._buckets) < self._max_keys // 2:
            return

        stale_cutoff = now - self._window_s * 2
        stale_keys = [k for k, v in self._buckets.items() if not v.timestamps or v.timestamps[-1] < stale_cutoff]
        for k in stale_keys:
            del self._buckets[k]

    @property
    def tracked_keys(self) -> int:
        return len(self._buckets)
