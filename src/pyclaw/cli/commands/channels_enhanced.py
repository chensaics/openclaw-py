"""Enhanced channels CLI — capabilities, add/remove, transformers, shared helpers.

Ported from ``src/commands/configure-channels*.ts``.

Provides:
- Channel capabilities listing
- Channel add/remove with validation
- Channel configuration transformers
- Shared channel helpers for CLI
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChannelCapability(str, Enum):
    TEXT = "text"
    MEDIA = "media"
    REACTIONS = "reactions"
    THREADS = "threads"
    BUTTONS = "buttons"
    TYPING = "typing"
    STREAMING = "streaming"
    GROUPS = "groups"
    DM = "dm"
    VOICE = "voice"
    VIDEO = "video"
    FILE_UPLOAD = "file_upload"
    MENTIONS = "mentions"
    SLASH_COMMANDS = "slash_commands"


@dataclass
class ChannelSpec:
    """Specification for a channel type."""
    channel_id: str
    display_name: str
    capabilities: list[ChannelCapability] = field(default_factory=list)
    required_config: list[str] = field(default_factory=list)
    optional_config: list[str] = field(default_factory=list)
    docs_url: str = ""
    category: str = "core"


@dataclass
class ChannelConfigValidation:
    """Result of validating a channel configuration."""
    valid: bool
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in Channel Specs
# ---------------------------------------------------------------------------

CHANNEL_SPECS: dict[str, ChannelSpec] = {
    "telegram": ChannelSpec(
        channel_id="telegram", display_name="Telegram",
        capabilities=[ChannelCapability.TEXT, ChannelCapability.MEDIA, ChannelCapability.REACTIONS,
                      ChannelCapability.GROUPS, ChannelCapability.DM, ChannelCapability.TYPING,
                      ChannelCapability.BUTTONS, ChannelCapability.MENTIONS, ChannelCapability.SLASH_COMMANDS],
        required_config=["token"],
        docs_url="https://docs.openclaw.ai/channels/telegram",
    ),
    "discord": ChannelSpec(
        channel_id="discord", display_name="Discord",
        capabilities=[ChannelCapability.TEXT, ChannelCapability.MEDIA, ChannelCapability.REACTIONS,
                      ChannelCapability.THREADS, ChannelCapability.GROUPS, ChannelCapability.DM,
                      ChannelCapability.TYPING, ChannelCapability.MENTIONS, ChannelCapability.SLASH_COMMANDS],
        required_config=["token"],
        docs_url="https://docs.openclaw.ai/channels/discord",
    ),
    "slack": ChannelSpec(
        channel_id="slack", display_name="Slack",
        capabilities=[ChannelCapability.TEXT, ChannelCapability.MEDIA, ChannelCapability.REACTIONS,
                      ChannelCapability.THREADS, ChannelCapability.GROUPS, ChannelCapability.DM,
                      ChannelCapability.TYPING, ChannelCapability.MENTIONS, ChannelCapability.SLASH_COMMANDS],
        required_config=["bot_token", "app_token"],
        docs_url="https://docs.openclaw.ai/channels/slack",
    ),
    "whatsapp": ChannelSpec(
        channel_id="whatsapp", display_name="WhatsApp",
        capabilities=[ChannelCapability.TEXT, ChannelCapability.MEDIA, ChannelCapability.REACTIONS,
                      ChannelCapability.GROUPS, ChannelCapability.DM],
        required_config=[],
        docs_url="https://docs.openclaw.ai/channels/whatsapp",
    ),
    "signal": ChannelSpec(
        channel_id="signal", display_name="Signal",
        capabilities=[ChannelCapability.TEXT, ChannelCapability.MEDIA, ChannelCapability.REACTIONS,
                      ChannelCapability.GROUPS, ChannelCapability.DM],
        required_config=["phone_number"],
        docs_url="https://docs.openclaw.ai/channels/signal",
    ),
    "imessage": ChannelSpec(
        channel_id="imessage", display_name="iMessage",
        capabilities=[ChannelCapability.TEXT, ChannelCapability.MEDIA, ChannelCapability.DM],
        required_config=[],
        category="core",
    ),
    "feishu": ChannelSpec(
        channel_id="feishu", display_name="Feishu / Lark",
        capabilities=[ChannelCapability.TEXT, ChannelCapability.MEDIA, ChannelCapability.REACTIONS,
                      ChannelCapability.GROUPS, ChannelCapability.THREADS, ChannelCapability.MENTIONS],
        required_config=["app_id", "app_secret"],
        category="extension",
    ),
    "matrix": ChannelSpec(
        channel_id="matrix", display_name="Matrix",
        capabilities=[ChannelCapability.TEXT, ChannelCapability.MEDIA, ChannelCapability.REACTIONS,
                      ChannelCapability.GROUPS, ChannelCapability.DM, ChannelCapability.THREADS],
        required_config=["homeserver", "user_id", "access_token"],
        category="extension",
    ),
    "msteams": ChannelSpec(
        channel_id="msteams", display_name="Microsoft Teams",
        capabilities=[ChannelCapability.TEXT, ChannelCapability.MEDIA, ChannelCapability.GROUPS,
                      ChannelCapability.DM, ChannelCapability.TYPING],
        required_config=["app_id", "app_password"],
        category="extension",
    ),
}


def validate_channel_config(channel_id: str, config: dict[str, Any]) -> ChannelConfigValidation:
    """Validate a channel configuration against its spec."""
    spec = CHANNEL_SPECS.get(channel_id)
    if not spec:
        return ChannelConfigValidation(
            valid=False,
            errors=[f"Unknown channel: {channel_id}"],
        )

    missing = [f for f in spec.required_config if f not in config or not config[f]]
    warnings: list[str] = []

    if config.get("enabled") is False:
        warnings.append("Channel is disabled")

    return ChannelConfigValidation(
        valid=len(missing) == 0,
        missing_fields=missing,
        warnings=warnings,
    )


def get_channel_capabilities(channel_id: str) -> list[ChannelCapability]:
    """Get capabilities for a channel."""
    spec = CHANNEL_SPECS.get(channel_id)
    return spec.capabilities if spec else []


def list_channels(*, category: str = "") -> list[ChannelSpec]:
    """List all available channels."""
    specs = list(CHANNEL_SPECS.values())
    if category:
        specs = [s for s in specs if s.category == category]
    return specs


def transform_channel_config(channel_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Apply transformations to channel config (normalize keys, set defaults)."""
    result = dict(config)

    result.setdefault("enabled", True)

    if channel_id == "telegram":
        if "bot_token" in result and "token" not in result:
            result["token"] = result.pop("bot_token")
    elif channel_id == "discord":
        if "bot_token" in result and "token" not in result:
            result["token"] = result.pop("bot_token")

    return result


def channel_summary(channel_id: str, config: dict[str, Any]) -> str:
    """Generate a short summary string for a channel config."""
    spec = CHANNEL_SPECS.get(channel_id)
    name = spec.display_name if spec else channel_id
    enabled = config.get("enabled", True)
    status = "enabled" if enabled else "disabled"
    caps = len(spec.capabilities) if spec else 0
    return f"{name} ({status}, {caps} capabilities)"
