"""Plugin onboarding hooks — interactive channel configuration.

Ported from ``src/channels/plugins/onboarding-types.ts`` and
``src/commands/onboard-channels.ts``.

Plugins can provide ``configureInteractive`` and ``configureWhenConfigured``
hooks that drive interactive onboarding for channel setup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class OnboardingStatusContext:
    """Context passed to ``get_status``."""

    config: dict[str, Any]
    channel_id: str


@dataclass
class OnboardingStatus:
    """Status returned from ``get_status``."""

    configured: bool = False
    connected: bool = False
    account_id: str | None = None
    message: str = ""


@dataclass
class OnboardingConfigureContext:
    """Context passed to ``configure`` and interactive hooks."""

    config: dict[str, Any]
    channel_id: str
    prompter: Any = None  # interactive prompter (typer/rich)
    account_overrides: dict[str, str] = field(default_factory=dict)
    should_prompt_account_ids: bool = False
    force_allow_from: bool = False


@dataclass
class OnboardingInteractiveContext(OnboardingConfigureContext):
    """Extended context for interactive hooks."""

    configured: bool = False
    label: str = ""


@dataclass
class OnboardingResult:
    """Result from configure or interactive hooks."""

    config: dict[str, Any] = field(default_factory=dict)
    account_id: str | None = None


OnboardingConfiguredResult = OnboardingResult | Literal["skip"]


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ChannelOnboardingAdapter(Protocol):
    """Protocol for channel onboarding plugins."""

    channel: str

    async def get_status(self, ctx: OnboardingStatusContext) -> OnboardingStatus: ...

    async def configure(self, ctx: OnboardingConfigureContext) -> OnboardingResult: ...

    async def configure_interactive(
        self, ctx: OnboardingInteractiveContext
    ) -> OnboardingConfiguredResult:
        """Optional: handles both unconfigured and configured states interactively."""
        ...

    async def configure_when_configured(
        self, ctx: OnboardingInteractiveContext
    ) -> OnboardingConfiguredResult:
        """Optional: called only when the channel is already configured."""
        ...


# ---------------------------------------------------------------------------
# Onboarding runner
# ---------------------------------------------------------------------------

class OnboardingRunner:
    """Runs onboarding for channels using plugin adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelOnboardingAdapter] = {}

    def register(self, adapter: ChannelOnboardingAdapter) -> None:
        self._adapters[adapter.channel] = adapter
        logger.debug("Registered onboarding adapter: %s", adapter.channel)

    def get_adapter(self, channel: str) -> ChannelOnboardingAdapter | None:
        return self._adapters.get(channel)

    def list_channels(self) -> list[str]:
        return sorted(self._adapters.keys())

    async def run_onboarding(
        self,
        channel: str,
        config: dict[str, Any],
        *,
        prompter: Any = None,
        account_overrides: dict[str, str] | None = None,
    ) -> OnboardingResult | Literal["skip"]:
        """Run onboarding for a single channel.

        Precedence:
        1. ``configure_interactive`` (if present) — handles both states
        2. ``configure_when_configured`` (if already configured + present)
        3. ``configure`` (fallback)
        """
        adapter = self._adapters.get(channel)
        if not adapter:
            raise ValueError(f"No onboarding adapter for channel: {channel}")

        status_ctx = OnboardingStatusContext(config=config, channel_id=channel)
        status = await adapter.get_status(status_ctx)

        base_ctx = OnboardingConfigureContext(
            config=config,
            channel_id=channel,
            prompter=prompter,
            account_overrides=account_overrides or {},
        )

        interactive_ctx = OnboardingInteractiveContext(
            config=base_ctx.config,
            channel_id=base_ctx.channel_id,
            prompter=base_ctx.prompter,
            account_overrides=base_ctx.account_overrides,
            configured=status.configured,
            label=adapter.channel,
        )

        # Priority 1: configureInteractive (handles both configured and unconfigured)
        if _has_method(adapter, "configure_interactive"):
            return await adapter.configure_interactive(interactive_ctx)

        # Priority 2: configureWhenConfigured (only when already configured)
        if status.configured and _has_method(adapter, "configure_when_configured"):
            return await adapter.configure_when_configured(interactive_ctx)

        # Priority 3: standard configure
        return await adapter.configure(base_ctx)

    async def get_all_statuses(
        self, config: dict[str, Any]
    ) -> dict[str, OnboardingStatus]:
        """Get onboarding status for all registered channels."""
        statuses: dict[str, OnboardingStatus] = {}
        for channel, adapter in self._adapters.items():
            try:
                ctx = OnboardingStatusContext(config=config, channel_id=channel)
                statuses[channel] = await adapter.get_status(ctx)
            except Exception:
                logger.warning("Failed to get status for %s", channel)
                statuses[channel] = OnboardingStatus(message="Error checking status")
        return statuses


def _has_method(obj: Any, name: str) -> bool:
    """Check if an object has a callable method (not just the Protocol stub)."""
    method = getattr(obj, name, None)
    if method is None:
        return False
    # Check it's not the Protocol's default (which just has `...`)
    if hasattr(method, "__func__"):
        # Bound method — check if it's overridden from the Protocol
        declaring_class = getattr(method.__func__, "__qualname__", "").split(".")[0]
        return declaring_class != "ChannelOnboardingAdapter"
    return callable(method)
