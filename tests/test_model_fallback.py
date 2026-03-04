"""Tests for model fallback manager."""

from __future__ import annotations

import time

import pytest

from pyclaw.agents.model_fallback import (
    ErrorCategory,
    FallbackCandidate,
    ModelFallbackManager,
    ModelHealth,
    classify_error,
    should_retry_with_fallback,
)


class TestClassifyError:
    def test_rate_limit(self) -> None:
        assert classify_error("429 Too Many Requests") == ErrorCategory.RATE_LIMIT
        assert classify_error("rate_limit_exceeded") == ErrorCategory.RATE_LIMIT
        assert classify_error("quota exceeded") == ErrorCategory.RATE_LIMIT

    def test_auth_error(self) -> None:
        assert classify_error("401 Unauthorized") == ErrorCategory.AUTH_ERROR
        assert classify_error("Invalid API key") == ErrorCategory.AUTH_ERROR

    def test_auth_permanent(self) -> None:
        assert classify_error("API key revoked permanently") == ErrorCategory.AUTH_PERMANENT
        assert classify_error("Account disabled") == ErrorCategory.AUTH_PERMANENT

    def test_context_overflow(self) -> None:
        assert classify_error("context_length_exceeded") == ErrorCategory.CONTEXT_OVERFLOW
        assert classify_error("maximum context length") == ErrorCategory.CONTEXT_OVERFLOW

    def test_server_error(self) -> None:
        assert classify_error("500 Internal Server Error") == ErrorCategory.SERVER_ERROR
        assert classify_error("503 Service Unavailable") == ErrorCategory.SERVER_ERROR

    def test_unknown(self) -> None:
        assert classify_error("something weird happened") == ErrorCategory.UNKNOWN
        assert classify_error(None) == ErrorCategory.UNKNOWN


class TestShouldRetry:
    def test_rate_limit_retries(self) -> None:
        assert should_retry_with_fallback(ErrorCategory.RATE_LIMIT) is True

    def test_server_error_retries(self) -> None:
        assert should_retry_with_fallback(ErrorCategory.SERVER_ERROR) is True

    def test_auth_no_retry(self) -> None:
        assert should_retry_with_fallback(ErrorCategory.AUTH_ERROR) is False

    def test_context_overflow_no_retry(self) -> None:
        assert should_retry_with_fallback(ErrorCategory.CONTEXT_OVERFLOW) is False


class TestModelHealth:
    def test_initial_state(self) -> None:
        h = ModelHealth(model_id="gpt-4o", provider="openai")
        assert h.is_available is True
        assert h.is_cooled_down is False

    def test_cooldown(self) -> None:
        h = ModelHealth(model_id="gpt-4o", provider="openai")
        h.cooldown_until = time.time() + 100
        assert h.is_cooled_down is True
        assert h.is_available is False

    def test_expired_cooldown(self) -> None:
        h = ModelHealth(model_id="gpt-4o", provider="openai")
        h.cooldown_until = time.time() - 1
        assert h.is_cooled_down is False

    def test_disabled(self) -> None:
        h = ModelHealth(model_id="gpt-4o", provider="openai", available=False)
        assert h.is_available is False


class TestModelFallbackManager:
    @pytest.fixture
    def manager(self) -> ModelFallbackManager:
        mgr = ModelFallbackManager(default_cooldown_s=0.1)
        mgr.register_chain(
            "default",
            [
                FallbackCandidate(model_id="gpt-4o", provider="openai", is_primary=True),
                FallbackCandidate(model_id="gpt-4o-mini", provider="openai"),
                FallbackCandidate(model_id="claude-sonnet", provider="anthropic"),
            ],
        )
        return mgr

    def test_resolve_primary(self, manager: ModelFallbackManager) -> None:
        candidate = manager.resolve_model("default")
        assert candidate is not None
        assert candidate.model_id == "gpt-4o"

    def test_resolve_fallback_after_cooldown(self, manager: ModelFallbackManager) -> None:
        manager.record_failure("gpt-4o", "rate_limit_exceeded")
        candidate = manager.resolve_model("default")
        assert candidate is not None
        assert candidate.model_id == "gpt-4o-mini"

    def test_resolve_cross_provider(self, manager: ModelFallbackManager) -> None:
        manager.record_failure("gpt-4o", "rate_limit_exceeded")
        manager.record_failure("gpt-4o-mini", "rate_limit_exceeded")
        candidate = manager.resolve_model("default")
        assert candidate is not None
        assert candidate.model_id == "claude-sonnet"

    def test_all_in_cooldown(self, manager: ModelFallbackManager) -> None:
        for mid in ["gpt-4o", "gpt-4o-mini", "claude-sonnet"]:
            manager.record_failure(mid, "rate_limit_exceeded")
        candidate = manager.resolve_model("default")
        assert candidate is None

    def test_record_success_resets(self, manager: ModelFallbackManager) -> None:
        manager.record_failure("gpt-4o", "rate_limit_exceeded")
        assert manager.get_health("gpt-4o") is not None
        assert manager.get_health("gpt-4o").is_cooled_down is True

        manager.record_success("gpt-4o")
        assert manager.get_health("gpt-4o").is_cooled_down is False

    def test_permanent_auth_disables(self, manager: ModelFallbackManager) -> None:
        cat = manager.record_failure("gpt-4o", "API key revoked permanently")
        assert cat == ErrorCategory.AUTH_PERMANENT
        health = manager.get_health("gpt-4o")
        assert health is not None
        assert health.available is False

    def test_unknown_chain(self, manager: ModelFallbackManager) -> None:
        assert manager.resolve_model("nonexistent") is None

    def test_reset_cooldown(self, manager: ModelFallbackManager) -> None:
        manager.record_failure("gpt-4o", "rate_limit")
        manager.reset_cooldown("gpt-4o")
        health = manager.get_health("gpt-4o")
        assert health is not None
        assert health.is_cooled_down is False

    def test_reset_all(self, manager: ModelFallbackManager) -> None:
        for mid in ["gpt-4o", "gpt-4o-mini"]:
            manager.record_failure(mid, "rate_limit")
        manager.reset_all()
        for mid in ["gpt-4o", "gpt-4o-mini"]:
            assert manager.get_health(mid).is_cooled_down is False

    def test_get_all_health(self, manager: ModelFallbackManager) -> None:
        all_health = manager.get_all_health()
        assert "gpt-4o" in all_health
        assert "gpt-4o-mini" in all_health
        assert "claude-sonnet" in all_health
