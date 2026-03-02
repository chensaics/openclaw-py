"""Model fallback — multi-level provider fallback with cooldown and error classification.

Ported from ``src/agents/`` fallback logic in the TypeScript codebase.

Provides a robust model fallback system that:
- Maintains ordered fallback chains per provider
- Detects cooldown/rate-limit from provider responses
- Classifies errors for retry decisions (rate_limit, auth, context_overflow, unknown)
- Supports same-provider fallback (e.g. gpt-4o → gpt-4o-mini)
- Tracks per-model health with cooldown timers
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_S = 60.0
DEFAULT_MAX_COOLDOWN_S = 300.0


class ErrorCategory(str, Enum):
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    AUTH_PERMANENT = "auth_permanent"
    CONTEXT_OVERFLOW = "context_overflow"
    MODEL_COOLDOWN = "model_cooldown"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"


@dataclass
class ModelHealth:
    """Health state of a single model."""

    model_id: str
    provider: str
    available: bool = True
    cooldown_until: float = 0.0
    last_error: str = ""
    last_error_category: ErrorCategory | None = None
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0

    @property
    def is_cooled_down(self) -> bool:
        return self.cooldown_until > 0 and time.time() < self.cooldown_until

    @property
    def is_available(self) -> bool:
        return self.available and not self.is_cooled_down


@dataclass
class FallbackCandidate:
    """A candidate model in a fallback chain."""

    model_id: str
    provider: str
    is_primary: bool = False
    api_key: str = ""
    base_url: str = ""


@dataclass
class FallbackChain:
    """Ordered list of fallback candidates."""

    candidates: list[FallbackCandidate] = field(default_factory=list)

    def get_available(self, health_map: dict[str, ModelHealth]) -> list[FallbackCandidate]:
        """Get candidates that are currently available (not in cooldown)."""
        available: list[FallbackCandidate] = []
        for c in self.candidates:
            health = health_map.get(c.model_id)
            if health is None or health.is_available:
                available.append(c)
        return available


def classify_error(error: Any) -> ErrorCategory:
    """Classify a provider error into a category for retry decisions."""
    if error is None:
        return ErrorCategory.UNKNOWN

    err_str = str(error).lower()

    # Rate limit patterns
    rate_limit_patterns = [
        "rate_limit", "rate limit", "too many requests",
        "429", "quota", "throttl", "cooling down", "model_cooldown",
    ]
    if any(p in err_str for p in rate_limit_patterns):
        return ErrorCategory.RATE_LIMIT

    # Auth permanent (check first — more specific)
    auth_keywords = ["401", "unauthorized", "invalid api key", "authentication", "api key"]
    permanent_keywords = ["revoked", "expired", "disabled", "permanent"]
    if any(p in err_str for p in permanent_keywords) and any(p in err_str for p in auth_keywords + ["key", "account"]):
        return ErrorCategory.AUTH_PERMANENT

    # Auth patterns
    if any(p in err_str for p in auth_keywords):
        return ErrorCategory.AUTH_ERROR

    # Context overflow
    if any(p in err_str for p in ["context_length", "context length", "token limit", "too long", "maximum context"]):
        return ErrorCategory.CONTEXT_OVERFLOW

    # Server errors
    if any(p in err_str for p in ["500", "502", "503", "504", "server error", "internal error"]):
        return ErrorCategory.SERVER_ERROR

    return ErrorCategory.UNKNOWN


def should_retry_with_fallback(category: ErrorCategory) -> bool:
    """Determine if an error category warrants trying the next fallback candidate."""
    return category in (
        ErrorCategory.RATE_LIMIT,
        ErrorCategory.MODEL_COOLDOWN,
        ErrorCategory.SERVER_ERROR,
        ErrorCategory.UNKNOWN,
    )


class ModelFallbackManager:
    """Manages model fallback chains and health tracking."""

    def __init__(self, *, default_cooldown_s: float = DEFAULT_COOLDOWN_S) -> None:
        self._health: dict[str, ModelHealth] = {}
        self._chains: dict[str, FallbackChain] = {}
        self._default_cooldown = default_cooldown_s

    def register_chain(self, chain_id: str, candidates: list[FallbackCandidate]) -> None:
        """Register a fallback chain."""
        self._chains[chain_id] = FallbackChain(candidates=candidates)
        for c in candidates:
            if c.model_id not in self._health:
                self._health[c.model_id] = ModelHealth(
                    model_id=c.model_id,
                    provider=c.provider,
                )

    def get_chain(self, chain_id: str) -> FallbackChain | None:
        return self._chains.get(chain_id)

    def resolve_model(self, chain_id: str) -> FallbackCandidate | None:
        """Resolve the best available model from a fallback chain.

        Returns the first available candidate, or None if all are in cooldown.
        """
        chain = self._chains.get(chain_id)
        if not chain:
            return None

        available = chain.get_available(self._health)
        return available[0] if available else None

    def record_success(self, model_id: str) -> None:
        """Record a successful model invocation."""
        health = self._health.get(model_id)
        if health:
            health.consecutive_failures = 0
            health.total_successes += 1
            health.cooldown_until = 0.0
            health.last_error = ""
            health.last_error_category = None

    def record_failure(self, model_id: str, error: Any) -> ErrorCategory:
        """Record a model failure and apply cooldown if needed.

        Returns the error category.
        """
        category = classify_error(error)

        health = self._health.get(model_id)
        if not health:
            health = ModelHealth(model_id=model_id, provider="")
            self._health[model_id] = health

        health.consecutive_failures += 1
        health.total_failures += 1
        health.last_error = str(error)[:200]
        health.last_error_category = category

        # Apply cooldown for rate limits
        if category in (ErrorCategory.RATE_LIMIT, ErrorCategory.MODEL_COOLDOWN):
            cooldown = min(
                self._default_cooldown * (2 ** (health.consecutive_failures - 1)),
                DEFAULT_MAX_COOLDOWN_S,
            )
            health.cooldown_until = time.time() + cooldown
            logger.info(
                "Model %s in cooldown for %.0fs (category=%s)",
                model_id, cooldown, category.value,
            )

        # Permanent auth → disable
        if category == ErrorCategory.AUTH_PERMANENT:
            health.available = False
            logger.warning("Model %s permanently disabled: %s", model_id, error)

        return category

    def get_health(self, model_id: str) -> ModelHealth | None:
        return self._health.get(model_id)

    def get_all_health(self) -> dict[str, ModelHealth]:
        return dict(self._health)

    def reset_cooldown(self, model_id: str) -> None:
        """Manually reset a model's cooldown."""
        health = self._health.get(model_id)
        if health:
            health.cooldown_until = 0.0
            health.consecutive_failures = 0

    def reset_all(self) -> None:
        """Reset all health states."""
        for health in self._health.values():
            health.cooldown_until = 0.0
            health.consecutive_failures = 0
            health.available = True
