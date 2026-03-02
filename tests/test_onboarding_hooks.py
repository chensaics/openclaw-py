"""Tests for plugin onboarding hooks."""

from __future__ import annotations

import pytest

from pyclaw.plugins.onboarding import (
    OnboardingConfigureContext,
    OnboardingInteractiveContext,
    OnboardingResult,
    OnboardingRunner,
    OnboardingStatus,
    OnboardingStatusContext,
)


class SimpleAdapter:
    """Minimal adapter with only configure()."""

    channel = "simple"

    async def get_status(self, ctx: OnboardingStatusContext) -> OnboardingStatus:
        has_token = bool(ctx.config.get("token"))
        return OnboardingStatus(configured=has_token, connected=has_token)

    async def configure(self, ctx: OnboardingConfigureContext) -> OnboardingResult:
        return OnboardingResult(config={"token": "test-token"}, account_id="simple-1")


class InteractiveAdapter:
    """Adapter with configure_interactive()."""

    channel = "interactive"

    async def get_status(self, ctx: OnboardingStatusContext) -> OnboardingStatus:
        return OnboardingStatus(configured=True)

    async def configure(self, ctx: OnboardingConfigureContext) -> OnboardingResult:
        return OnboardingResult(config={})

    async def configure_interactive(
        self, ctx: OnboardingInteractiveContext
    ) -> OnboardingResult:
        return OnboardingResult(
            config={"interactive": True, "was_configured": ctx.configured},
            account_id="interactive-1",
        )


class WhenConfiguredAdapter:
    """Adapter with configure_when_configured()."""

    channel = "when-configured"

    async def get_status(self, ctx: OnboardingStatusContext) -> OnboardingStatus:
        return OnboardingStatus(configured=ctx.config.get("configured", False))

    async def configure(self, ctx: OnboardingConfigureContext) -> OnboardingResult:
        return OnboardingResult(config={"basic": True})

    async def configure_when_configured(
        self, ctx: OnboardingInteractiveContext
    ) -> OnboardingResult:
        return OnboardingResult(config={"reconfigured": True})


class TestOnboardingRunner:
    @pytest.fixture
    def runner(self) -> OnboardingRunner:
        r = OnboardingRunner()
        r.register(SimpleAdapter())
        r.register(InteractiveAdapter())
        r.register(WhenConfiguredAdapter())
        return r

    def test_register_and_list(self, runner: OnboardingRunner) -> None:
        channels = runner.list_channels()
        assert "simple" in channels
        assert "interactive" in channels
        assert "when-configured" in channels

    def test_get_adapter(self, runner: OnboardingRunner) -> None:
        assert runner.get_adapter("simple") is not None
        assert runner.get_adapter("nonexistent") is None

    @pytest.mark.asyncio
    async def test_simple_configure(self, runner: OnboardingRunner) -> None:
        result = await runner.run_onboarding("simple", {})
        assert isinstance(result, OnboardingResult)
        assert result.config["token"] == "test-token"
        assert result.account_id == "simple-1"

    @pytest.mark.asyncio
    async def test_interactive_takes_priority(self, runner: OnboardingRunner) -> None:
        result = await runner.run_onboarding("interactive", {})
        assert isinstance(result, OnboardingResult)
        assert result.config.get("interactive") is True

    @pytest.mark.asyncio
    async def test_when_configured_used_only_if_configured(self, runner: OnboardingRunner) -> None:
        # Not configured → falls through to basic configure
        result = await runner.run_onboarding("when-configured", {})
        assert isinstance(result, OnboardingResult)
        assert result.config.get("basic") is True

        # Configured → uses configure_when_configured
        result = await runner.run_onboarding("when-configured", {"configured": True})
        assert isinstance(result, OnboardingResult)
        assert result.config.get("reconfigured") is True

    @pytest.mark.asyncio
    async def test_unknown_channel_raises(self, runner: OnboardingRunner) -> None:
        with pytest.raises(ValueError, match="No onboarding adapter"):
            await runner.run_onboarding("nonexistent", {})

    @pytest.mark.asyncio
    async def test_get_all_statuses(self, runner: OnboardingRunner) -> None:
        statuses = await runner.get_all_statuses({"token": "x", "configured": True})
        assert "simple" in statuses
        assert statuses["simple"].configured is True
        assert "interactive" in statuses
        assert "when-configured" in statuses


class TestOnboardingStatus:
    def test_default_values(self) -> None:
        s = OnboardingStatus()
        assert s.configured is False
        assert s.connected is False
        assert s.account_id is None
        assert s.message == ""

    def test_custom_values(self) -> None:
        s = OnboardingStatus(configured=True, connected=True, account_id="a1", message="OK")
        assert s.configured is True
        assert s.account_id == "a1"
