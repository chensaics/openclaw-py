"""Outbound target resolver — multi-channel targets, channel selection, session binding.

Ported from ``src/infra/outbound/target-resolver.ts``.

Provides:
- Target resolution from session context
- Multi-channel target support
- Channel selection based on availability and preference
- Session binding for delivery routing
- Agent binding integration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DeliveryTarget:
    """A resolved delivery target."""

    channel_id: str
    chat_id: str
    sender_id: str = ""
    thread_id: str = ""
    reply_to_message_id: str = ""
    channel_type: str = ""  # "telegram" | "discord" | "slack" | ...
    account_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TargetResolutionContext:
    """Context for resolving delivery targets."""

    session_id: str
    agent_id: str = ""
    channel_id: str = ""
    sender_id: str = ""
    account_id: str = ""
    bindings: list[dict[str, Any]] = field(default_factory=list)
    available_channels: list[str] = field(default_factory=list)


@dataclass
class TargetResolutionResult:
    """Result of target resolution."""

    targets: list[DeliveryTarget]
    errors: list[str] = field(default_factory=list)

    @property
    def has_targets(self) -> bool:
        return len(self.targets) > 0

    @property
    def primary(self) -> DeliveryTarget | None:
        return self.targets[0] if self.targets else None


class TargetResolver:
    """Resolve delivery targets from session context and bindings."""

    def __init__(self) -> None:
        self._channel_registry: dict[str, dict[str, Any]] = {}

    def register_channel(self, channel_id: str, info: dict[str, Any]) -> None:
        self._channel_registry[channel_id] = info

    def resolve(self, context: TargetResolutionContext) -> TargetResolutionResult:
        """Resolve delivery targets for a message.

        Priority:
        1. Agent bindings (if any match)
        2. Session origin channel
        3. Available channels (fallback)
        """
        targets: list[DeliveryTarget] = []
        errors: list[str] = []

        # Agent binding route
        for binding in context.bindings:
            bound_channel = binding.get("channel_id")
            bound_chat = binding.get("chat_id")
            if bound_channel and bound_chat:
                targets.append(
                    DeliveryTarget(
                        channel_id=bound_channel,
                        chat_id=bound_chat,
                        sender_id=binding.get("sender_id", ""),
                        channel_type=binding.get("channel_type", ""),
                        account_id=context.account_id,
                    )
                )

        if targets:
            return TargetResolutionResult(targets=targets)

        # Session origin
        if context.channel_id:
            targets.append(
                DeliveryTarget(
                    channel_id=context.channel_id,
                    chat_id=context.sender_id,
                    sender_id=context.sender_id,
                    account_id=context.account_id,
                )
            )
            return TargetResolutionResult(targets=targets)

        # Fallback
        if context.available_channels:
            for ch in context.available_channels:
                targets.append(
                    DeliveryTarget(
                        channel_id=ch,
                        chat_id=context.sender_id,
                        sender_id=context.sender_id,
                        account_id=context.account_id,
                    )
                )
            return TargetResolutionResult(targets=targets)

        errors.append("No delivery targets found")
        return TargetResolutionResult(targets=[], errors=errors)

    def select_channel(
        self,
        targets: list[DeliveryTarget],
        *,
        preferred: str = "",
    ) -> DeliveryTarget | None:
        """Select the best channel from multiple targets."""
        if not targets:
            return None

        if preferred:
            for t in targets:
                if t.channel_id == preferred or t.channel_type == preferred:
                    return t

        return targets[0]
