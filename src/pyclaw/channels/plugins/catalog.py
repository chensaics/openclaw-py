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
    supported_audio_types: list[str] = field(default_factory=lambda: ["audio/mp3", "audio/ogg", "audio/wav"])
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
            supports_reactions=True,
            supports_buttons=True,
            supports_pins=True,
            supports_threads=True,
            supports_editing=True,
            supports_deletion=True,
            supports_typing=True,
            max_buttons=8,
            button_styles=["inline", "reply"],
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
            supports_reactions=True,
            supports_buttons=True,
            supports_threads=True,
            supports_editing=True,
            supports_deletion=True,
            supports_typing=True,
            max_buttons=5,
            button_styles=["primary", "secondary", "danger", "link"],
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
            supports_reactions=True,
            supports_buttons=True,
            supports_threads=True,
            supports_editing=True,
            supports_deletion=True,
            supports_typing=True,
            max_buttons=5,
            reaction_style="emoji",
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
            supports_reactions=True,
            supports_typing=True,
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
    "feishu": CatalogEntry(
        channel_type="feishu",
        display_name="Feishu / Lark",
        description="Feishu (Lark) Bot channel",
        category=ChannelCategory.TEAM,
        icon="business",
        color="#3370FF",
        media_limits=MediaLimits(max_message_length=30000, max_file_size_mb=25),
        action_spec=ActionSpec(
            supports_typing=True,
            supports_threads=True,
            supports_editing=True,
            supports_deletion=True,
        ),
        account_helper=AccountHelper(
            steps=["Create app at Feishu Open Platform", "Enable Bot capability", "Copy App ID and Secret"],
            required_fields=["app_id", "app_secret"],
            docs_url="https://docs.openclaw.ai/channels/feishu",
        ),
    ),
    "matrix": CatalogEntry(
        channel_type="matrix",
        display_name="Matrix",
        description="Matrix protocol channel",
        category=ChannelCategory.MESSAGING,
        icon="grid_view",
        color="#0DBD8B",
        media_limits=MediaLimits(max_message_length=65536, max_file_size_mb=100),
        action_spec=ActionSpec(
            supports_reactions=True,
            supports_threads=True,
            supports_typing=True,
            supports_editing=True,
            supports_deletion=True,
        ),
        account_helper=AccountHelper(
            steps=["Create Matrix account", "Generate access token"],
            required_fields=["homeserver", "access_token"],
        ),
    ),
    "irc": CatalogEntry(
        channel_type="irc",
        display_name="IRC",
        description="Internet Relay Chat",
        category=ChannelCategory.SOCIAL,
        icon="terminal",
        color="#5B9BD5",
        media_limits=MediaLimits(max_message_length=512),
        action_spec=ActionSpec(supports_typing=False),
        account_helper=AccountHelper(
            steps=["Configure IRC server and channel"],
            required_fields=["server", "channel", "nick"],
        ),
    ),
    "msteams": CatalogEntry(
        channel_type="msteams",
        display_name="Microsoft Teams",
        description="MS Teams Bot channel",
        category=ChannelCategory.TEAM,
        icon="groups",
        color="#6264A7",
        media_limits=MediaLimits(max_message_length=28000, max_file_size_mb=250),
        action_spec=ActionSpec(
            supports_reactions=True,
            supports_typing=True,
            supports_threads=True,
            supports_editing=True,
            supports_deletion=True,
        ),
        account_helper=AccountHelper(
            steps=["Register app in Azure AD", "Create Teams Bot", "Copy credentials"],
            required_fields=["app_id", "app_password", "tenant_id"],
        ),
    ),
    "googlechat": CatalogEntry(
        channel_type="googlechat",
        display_name="Google Chat",
        description="Google Workspace Chat channel",
        category=ChannelCategory.TEAM,
        icon="chat_bubble",
        color="#00AC47",
        media_limits=MediaLimits(max_message_length=4096),
        action_spec=ActionSpec(
            supports_threads=True,
            supports_typing=True,
        ),
        account_helper=AccountHelper(
            steps=["Create Google Cloud project", "Enable Chat API", "Configure OAuth"],
            required_fields=["credentials_json"],
        ),
    ),
    "dingtalk": CatalogEntry(
        channel_type="dingtalk",
        display_name="DingTalk",
        description="DingTalk Bot channel",
        category=ChannelCategory.TEAM,
        icon="notifications",
        color="#0089FF",
        media_limits=MediaLimits(max_message_length=20000),
        action_spec=ActionSpec(supports_typing=False),
        account_helper=AccountHelper(
            steps=["Create DingTalk robot", "Copy webhook URL and secret"],
            required_fields=["app_key", "app_secret"],
        ),
    ),
    "qq": CatalogEntry(
        channel_type="qq",
        display_name="QQ",
        description="QQ Bot channel",
        category=ChannelCategory.SOCIAL,
        icon="question_answer",
        color="#12B7F5",
        media_limits=MediaLimits(max_message_length=4500),
        action_spec=ActionSpec(supports_reactions=True),
        account_helper=AccountHelper(
            steps=["Register QQ Bot at open.qq.com", "Copy Bot AppID and Token"],
            required_fields=["app_id", "token"],
        ),
    ),
    "twitch": CatalogEntry(
        channel_type="twitch",
        display_name="Twitch",
        description="Twitch IRC chat channel",
        category=ChannelCategory.SOCIAL,
        icon="live_tv",
        color="#9146FF",
        media_limits=MediaLimits(max_message_length=500),
        action_spec=ActionSpec(supports_typing=False),
        account_helper=AccountHelper(
            steps=["Register Twitch app", "Generate OAuth token"],
            required_fields=["oauth_token", "channel"],
        ),
    ),
    "bluebubbles": CatalogEntry(
        channel_type="bluebubbles",
        display_name="BlueBubbles",
        description="iMessage via BlueBubbles server",
        category=ChannelCategory.MESSAGING,
        icon="bubble_chart",
        color="#1E90FF",
        media_limits=MediaLimits(max_message_length=20000),
        action_spec=ActionSpec(supports_reactions=True, supports_typing=True),
        account_helper=AccountHelper(
            steps=["Install BlueBubbles server on macOS", "Copy server URL and password"],
            required_fields=["server_url", "password"],
        ),
    ),
    "voice_call": CatalogEntry(
        channel_type="voice_call",
        display_name="Voice Call",
        description="Telephony voice channel (Twilio, etc.)",
        category=ChannelCategory.VOICE,
        icon="phone",
        color="#F22F46",
        media_limits=MediaLimits(max_message_length=1600),
        action_spec=ActionSpec(supports_typing=False),
        account_helper=AccountHelper(
            steps=["Configure Twilio account", "Set webhook URL"],
            required_fields=["account_sid", "auth_token", "phone_number"],
        ),
        supports_dm=True,
        supports_groups=False,
    ),
    "line": CatalogEntry(
        channel_type="line",
        display_name="LINE",
        description="LINE Messaging API channel",
        category=ChannelCategory.MESSAGING,
        icon="forum",
        color="#00B900",
        media_limits=MediaLimits(max_message_length=5000, max_file_size_mb=200),
        action_spec=ActionSpec(
            supports_reactions=True,
            supports_typing=True,
        ),
        account_helper=AccountHelper(
            steps=["Create LINE channel", "Copy channel access token and secret"],
            required_fields=["channel_access_token", "channel_secret"],
        ),
    ),
    "mattermost": CatalogEntry(
        channel_type="mattermost",
        display_name="Mattermost",
        description="Mattermost Bot channel",
        category=ChannelCategory.TEAM,
        icon="developer_board",
        color="#0058CC",
        media_limits=MediaLimits(max_message_length=16383, max_file_size_mb=50),
        action_spec=ActionSpec(
            supports_reactions=True,
            supports_threads=True,
            supports_typing=True,
            supports_editing=True,
            supports_deletion=True,
        ),
        account_helper=AccountHelper(
            steps=["Create Mattermost bot account", "Copy access token"],
            required_fields=["url", "token"],
        ),
    ),
    "nostr": CatalogEntry(
        channel_type="nostr",
        display_name="Nostr",
        description="Nostr protocol channel",
        category=ChannelCategory.SOCIAL,
        icon="public",
        color="#8B5CF6",
        media_limits=MediaLimits(max_message_length=65536),
        action_spec=ActionSpec(supports_reactions=True),
        account_helper=AccountHelper(
            steps=["Generate Nostr keypair", "Configure relay URLs"],
            required_fields=["private_key"],
        ),
    ),
    "nextcloud": CatalogEntry(
        channel_type="nextcloud",
        display_name="Nextcloud Talk",
        description="Nextcloud Talk channel via REST API polling",
        category=ChannelCategory.TEAM,
        icon="cloud",
        color="#0082C9",
        media_limits=MediaLimits(max_message_length=32000),
        action_spec=ActionSpec(supports_typing=False),
        account_helper=AccountHelper(
            steps=["Set up Nextcloud instance", "Create Talk room", "Configure URL and credentials"],
            required_fields=["server_url", "username", "password", "room_token"],
        ),
    ),
    "synology": CatalogEntry(
        channel_type="synology",
        display_name="Synology Chat",
        description="Synology Chat channel via webhooks",
        category=ChannelCategory.TEAM,
        icon="dns",
        color="#4B4B4B",
        media_limits=MediaLimits(max_message_length=4096),
        action_spec=ActionSpec(supports_typing=False),
        account_helper=AccountHelper(
            steps=["Enable Synology Chat", "Create incoming and outgoing webhooks"],
            required_fields=["incoming_url", "outgoing_token"],
        ),
        requires_webhook=True,
    ),
    "tlon": CatalogEntry(
        channel_type="tlon",
        display_name="Tlon / Urbit",
        description="Urbit ship chat via SSE + REST",
        category=ChannelCategory.SOCIAL,
        icon="language",
        color="#1A1A1A",
        media_limits=MediaLimits(max_message_length=4096),
        action_spec=ActionSpec(supports_typing=False),
        account_helper=AccountHelper(
            steps=["Set up Urbit ship", "Obtain ship URL and code"],
            required_fields=["ship_url", "ship_code"],
        ),
    ),
    "zalo": CatalogEntry(
        channel_type="zalo",
        display_name="Zalo OA",
        description="Zalo Official Account channel via webhook",
        category=ChannelCategory.MESSAGING,
        icon="storefront",
        color="#0068FF",
        media_limits=MediaLimits(max_message_length=2000),
        action_spec=ActionSpec(supports_typing=False),
        account_helper=AccountHelper(
            steps=["Register Zalo OA at oa.zalo.me", "Generate OA access token", "Configure webhook"],
            required_fields=["oa_access_token"],
        ),
        requires_webhook=True,
    ),
    "zalouser": CatalogEntry(
        channel_type="zalouser",
        display_name="Zalo User",
        description="Personal Zalo account via zca-cli subprocess",
        category=ChannelCategory.MESSAGING,
        icon="person",
        color="#0068FF",
        media_limits=MediaLimits(max_message_length=2000),
        action_spec=ActionSpec(supports_typing=False),
        account_helper=AccountHelper(
            steps=["Install zca-cli", "Login with personal Zalo account"],
            required_fields=["zca_cli_path"],
        ),
    ),
    "webchat": CatalogEntry(
        channel_type="webchat",
        display_name="Web Chat",
        description="Built-in web chat widget",
        category=ChannelCategory.OTHER,
        icon="web",
        color="#607D8B",
        media_limits=MediaLimits(max_message_length=10000),
        action_spec=ActionSpec(supports_typing=True),
    ),
    "onebot": CatalogEntry(
        channel_type="onebot",
        display_name="OneBot",
        description="OneBot v11/v12 protocol (QQ ecosystem)",
        category=ChannelCategory.SOCIAL,
        icon="smart_toy",
        color="#12B7F5",
        media_limits=MediaLimits(max_message_length=4500),
        action_spec=ActionSpec(supports_reactions=True),
        account_helper=AccountHelper(
            steps=["Set up OneBot implementation (e.g. go-cqhttp)", "Configure WebSocket or HTTP endpoint"],
            required_fields=["endpoint"],
        ),
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

    # ------------------------------------------------------------------
    # Single-source-of-truth validation
    # ------------------------------------------------------------------

    def channel_types(self) -> set[str]:
        """Return the set of all registered channel type identifiers."""
        return set(self._entries.keys())

    def validate_against_schema(self) -> dict[str, list[str]]:
        """Check catalog ↔ ChannelsConfig alignment.

        Returns a dict with two keys:
        - ``in_catalog_not_schema``: types in catalog but missing from
          ChannelsConfig explicit fields.
        - ``in_schema_not_catalog``: fields on ChannelsConfig with no
          matching catalog entry.
        """
        from pyclaw.config.schema import ChannelsConfig

        schema_fields = _schema_channel_fields(ChannelsConfig)
        catalog_types = self.channel_types()

        return {
            "in_catalog_not_schema": sorted(catalog_types - schema_fields),
            "in_schema_not_catalog": sorted(schema_fields - catalog_types),
        }

    def validate_against_implementations(
        self,
        implementations_dir: str | None = None,
    ) -> dict[str, list[str]]:
        """Check catalog ↔ on-disk channel implementations alignment.

        Scans ``src/pyclaw/channels/*/channel.py`` to discover implemented
        channels and compares against catalog entries.
        """
        import pathlib

        if implementations_dir is None:
            implementations_dir = str(pathlib.Path(__file__).resolve().parent.parent)
        impl_path = pathlib.Path(implementations_dir)
        implemented: set[str] = set()
        for child in impl_path.iterdir():
            if child.is_dir() and (child / "channel.py").exists():
                implemented.add(child.name)

        # "plugins" dir itself is not a channel
        implemented.discard("plugins")

        catalog_types = self.channel_types()
        return {
            "in_catalog_not_implemented": sorted(catalog_types - implemented),
            "implemented_not_in_catalog": sorted(implemented - catalog_types),
        }


def _schema_channel_fields(config_cls: type) -> set[str]:
    """Extract channel field names from a ChannelsConfig Pydantic model."""
    skip = {"defaults"}
    fields: set[str] = set()
    for name, _info in config_cls.model_fields.items():
        if name in skip:
            continue
        fields.add(name)
    return fields
