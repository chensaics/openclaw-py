"""Generic retry policy with exponential backoff and jitter.

Ported from ``src/infra/retry-policy.ts``.
"""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar, cast

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    min_delay_ms: float = 500.0
    max_delay_ms: float = 30_000.0
    jitter: float = 0.1
    retry_on_status: set[int] | None = None


DEFAULT_RETRY = RetryConfig()


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, message: str, last_error: Exception | None = None, attempts: int = 0) -> None:
        super().__init__(message)
        self.last_error = last_error
        self.attempts = attempts


def _compute_delay(attempt: int, config: RetryConfig) -> float:
    """Compute delay in seconds using exponential backoff + jitter."""
    base = config.min_delay_ms * (2 ** attempt)
    capped = min(base, config.max_delay_ms)
    jitter_range = capped * config.jitter
    jittered = capped + random.uniform(-jitter_range, jitter_range)
    return cast(float, max(0.0, jittered) / 1000.0)


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    config: RetryConfig | None = None,
    should_retry: Callable[[Exception], bool] | None = None,
) -> T:
    """Execute *fn* with automatic retries.

    Args:
        fn: async callable to retry.
        config: retry configuration.
        should_retry: optional predicate to decide if an error is retryable.
    """
    cfg = config or DEFAULT_RETRY
    last_error: Exception | None = None

    for attempt in range(cfg.max_attempts):
        try:
            return await fn()
        except Exception as exc:
            last_error = exc
            if attempt == cfg.max_attempts - 1:
                break
            if should_retry and not should_retry(exc):
                break
            delay = _compute_delay(attempt, cfg)
            await asyncio.sleep(delay)

    raise RetryError(
        f"Failed after {cfg.max_attempts} attempts",
        last_error=last_error,
        attempts=cfg.max_attempts,
    )


# ---------------------------------------------------------------------------
# Provider error classification
# ---------------------------------------------------------------------------

class ProviderErrorKind:
    RATE_LIMIT = "rate_limit"
    CONTEXT_OVERFLOW = "context_overflow"
    AUTH_ERROR = "auth_error"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


def classify_provider_error(exc: Exception) -> str:
    """Classify an LLM provider error for retry/reporting."""
    msg = str(exc).lower()

    if "rate" in msg and "limit" in msg:
        return ProviderErrorKind.RATE_LIMIT
    if "429" in msg:
        return ProviderErrorKind.RATE_LIMIT
    if "context" in msg and ("overflow" in msg or "length" in msg or "too long" in msg):
        return ProviderErrorKind.CONTEXT_OVERFLOW
    if any(kw in msg for kw in ("unauthorized", "forbidden", "401", "403", "invalid api key", "authentication")):
        return ProviderErrorKind.AUTH_ERROR
    if any(kw in msg for kw in ("500", "502", "503", "504", "internal server error", "bad gateway")):
        return ProviderErrorKind.SERVER_ERROR
    if any(kw in msg for kw in ("connection", "timeout", "dns", "network")):
        return ProviderErrorKind.NETWORK_ERROR

    return ProviderErrorKind.UNKNOWN


def is_retryable_provider_error(exc: Exception) -> bool:
    """Return True if the error is retryable (rate limit, server, network)."""
    kind = classify_provider_error(exc)
    return kind in (
        ProviderErrorKind.RATE_LIMIT,
        ProviderErrorKind.SERVER_ERROR,
        ProviderErrorKind.NETWORK_ERROR,
    )


def extract_retry_after(exc: Exception) -> float | None:
    """Try to extract a Retry-After value (in seconds) from the exception."""
    msg = str(exc)
    import re
    m = re.search(r"retry[- _]after[:\s]+(\d+(?:\.\d+)?)", msg, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None
