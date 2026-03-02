"""Channel catalog — UI directory, account helpers, media limits, action specs.

Ported from ``src/channels/*/catalog.ts`` and ``src/channels/channel-catalog.ts``.

Provides:
- Channel catalog entries with display metadata
- Account setup helpers (token/webhook URLs)
- Per-channel media limits and payload constraints
- Message action name mapping
- Per-channel action spec (reactions, buttons, pins, threads)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ChannelCategory(str, Enum):
    MESSAGING = "messaging"
    SOCIAL = "social"
    TEAM = "team"
    EMAIL = "email"
    VOICE = "voice"
    OTHER = "other"


@dataclass
class MediaLimits:
    """Media upload constraints for a channel."""
    max_file_size_mb: float = 50.0
    max_image_size_mb: float = 10.0
    max_video_size_mb: float = 50.0
    max_audio_size_mb: float = 25.0
    supported_image_types: list[str] = field(
        default_factory=lambda: ["image/png", "image/jpeg", "image/gif", "image/webp"]
    )
    supported_audio_types: list[str] = field(
        default_factory=lambda: ["audio/mp3", "audio/ogg", "audio/wav"]
    )
    max_message_length: int = 4096


@dataclass
class ActionSpec:
    """Per-channel action capabilities."""
    supports_reactions: bool = False
    supports_buttons: bool = False
    supports_pins: bool = False
    supports_threads: bool = False
    supports_editing: bool = False
    supports_deletion: bool = False
    supports_typing: bool = False
    supports_read_receipts: bool = False
    reaction_style: str = "emoji"  # "emoji" | "custom" | "none"
    max_buttons: int = 0
    button_styles: list[str] = field(default_factory=list)


@dataclass
class AccountHelper:
    """Setup instructions for a channel account."""
    steps: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    docs_url: str = ""
    token_label: str = "API Token"
    webhook_url_template: str = ""


@dataclass
class CatalogEntry:
    """A channel entry in the catalog."""
    channel_type: str
    display_name: str
    description: str = ""
    category: ChannelCategory = ChannelCategory.MESSAGING
    icon: str = ""
    color: str = ""
    media_limits: MediaLimits = field(default_factory=MediaLimits)
    action_spec: ActionSpec = field(default_factory=ActionSpec)
    account_helper: AccountHelper = field(default_factory=AccountHelper)
    is_extension: bool = False
    requires_webhook: bool = False
    supports_groups: bool = True
    supports_dm: bool = True


# Built-in channel catalog entries
BUILTIN_CATALOG: dict[str, CatalogEntry] = {
    "telegram": CatalogEntry(
        channel_type="telegram",
        display_name="Telegram",
        description="Telegram Bot API channel",
        category=ChannelCategory.MESSAGING,
        icon="telegram",
        color="#0088cc",
        media_limits=MediaLimits(max_message_length=4096, max_file_size_mb=50),
        action_spec=ActionSpec(
            supports_reactions=True, supports_buttons=True, supports_pins=True,
            supports_threads=True, supports_editing=True, supports_deletion=True,
            supports_typing=True, max_buttons=8, button_styles=["inline", "reply"],
        ),
        account_helper=AccountHelper(
            steps=["Create bot via @BotFather", "Copy the bot token", "Set bot token in config"],
            required_fields=["token"],
            docs_url="https://docs.openclaw.ai/channels/telegram",
            token_label="Bot Token",
        ),
    ),
    "discord": CatalogEntry(
        channel_type="discord",
        display_name="Discord",
        description="Discord Bot channel",
        category=ChannelCategory.SOCIAL,
        icon="discord",
        color="#5865F2",
        media_limits=MediaLimits(max_message_length=2000, max_file_size_mb=25),
        action_spec=ActionSpec(
            supports_reactions=True, supports_buttons=True, supports_threads=True,
            supports_editing=True, supports_deletion=True, supports_typing=True,
            max_buttons=5, button_styles=["primary", "secondary", "danger", "link"],
        ),
        account_helper=AccountHelper(
            steps=["Create app at Discord Developer Portal", "Add bot to app", "Copy bot token"],
            required_fields=["token"],
            docs_url="https://docs.openclaw.ai/channels/discord",
            token_label="Bot Token",
        ),
    ),
    "slack": CatalogEntry(
        channel_type="slack",
        display_name="Slack",
        description="Slack Bot channel",
        category=ChannelCategory.TEAM,
        icon="slack",
        color="#4A154B",
        media_limits=MediaLimits(max_message_length=40000, max_file_size_mb=1000),
        action_spec=ActionSpec(
            supports_reactions=True, supports_buttons=True, supports_threads=True,
            supports_editing=True, supports_deletion=True, supports_typing=True,
            max_buttons=5, reaction_style="emoji",
        ),
        account_helper=AccountHelper(
            steps=["Create Slack App", "Install to workspace", "Copy Bot Token + App Token"],
            required_fields=["bot_token", "app_token"],
            docs_url="https://docs.openclaw.ai/channels/slack",
        ),
    ),
    "whatsapp": CatalogEntry(
        channel_type="whatsapp",
        display_name="WhatsApp",
        description="WhatsApp Web channel",
        category=ChannelCategory.MESSAGING,
        icon="whatsapp",
        color="#25D366",
        media_limits=MediaLimits(max_message_length=65536, max_file_size_mb=64),
        action_spec=ActionSpec(
            supports_reactions=True, supports_typing=True,
            supports_read_receipts=True,
        ),
        account_helper=AccountHelper(
            steps=["Scan QR code from WhatsApp mobile app"],
            docs_url="https://docs.openclaw.ai/channels/whatsapp",
        ),
        requires_webhook=False,
    ),
    "signal": CatalogEntry(
        channel_type="signal",
        display_name="Signal",
        description="Signal Messenger channel",
        category=ChannelCategory.MESSAGING,
        icon="signal",
        color="#3A76F0",
        media_limits=MediaLimits(max_message_length=65536, max_file_size_mb=100),
        action_spec=ActionSpec(supports_reactions=True, supports_typing=True),
        account_helper=AccountHelper(
            steps=["Install signal-cli", "Register or link a phone number"],
            required_fields=["phone_number"],
            docs_url="https://docs.openclaw.ai/channels/signal",
        ),
    ),
    "imessage": CatalogEntry(
        channel_type="imessage",
        display_name="iMessage",
        description="Apple iMessage channel",
        category=ChannelCategory.MESSAGING,
        icon="apple",
        color="#34C759",
        media_limits=MediaLimits(max_message_length=20000),
        action_spec=ActionSpec(supports_reactions=True, supports_typing=True),
        account_helper=AccountHelper(
            steps=["Enable iMessage on macOS", "Install imsg bridge"],
            docs_url="https://docs.openclaw.ai/channels/imessage",
        ),
        supports_groups=True,
    ),
}


class ChannelCatalog:
    """Registry of all available channel catalog entries."""

    def __init__(self) -> None:
        self._entries: dict[str, CatalogEntry] = dict(BUILTIN_CATALOG)

    def register(self, entry: CatalogEntry) -> None:
        self._entries[entry.channel_type] = entry

    def get(self, channel_type: str) -> CatalogEntry | None:
        return self._entries.get(channel_type)

    def list_all(self) -> list[CatalogEntry]:
        return list(self._entries.values())

    def list_by_category(self, category: ChannelCategory) -> list[CatalogEntry]:
        return [e for e in self._entries.values() if e.category == category]

    def get_media_limits(self, channel_type: str) -> MediaLimits:
        entry = self._entries.get(channel_type)
        return entry.media_limits if entry else MediaLimits()

    def get_action_spec(self, channel_type: str) -> ActionSpec:
        entry = self._entries.get(channel_type)
        return entry.action_spec if entry else ActionSpec()

    def get_account_helper(self, channel_type: str) -> AccountHelper:
        entry = self._entries.get(channel_type)
        return entry.account_helper if entry else AccountHelper()

    @property
    def count(self) -> int:
        return len(self._entries)

    def summarize(self) -> list[dict[str, Any]]:
        """Return a summary for UI display."""
        return [
            {
                "type": e.channel_type,
                "name": e.display_name,
                "category": e.category.value,
                "dm": e.supports_dm,
                "groups": e.supports_groups,
                "reactions": e.action_spec.supports_reactions,
                "threads": e.action_spec.supports_threads,
            }
            for e in self._entries.values()
        ]
