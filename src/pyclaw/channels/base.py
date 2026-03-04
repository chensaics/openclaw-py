"""Channel plugin base — abstract interface for messaging channels.

Every channel (Telegram, Discord, Slack, ...) implements this interface
so the gateway can start/stop them uniformly and route messages through
the agent pipeline.

Optional capability protocols (``TypingCapable``, ``PlaceholderCapable``,
``ReactionCapable``, ``MediaSendCapable``) can be implemented by channels
that support the respective feature.  The manager and gateway detect these
at runtime via ``detect_capabilities()``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


@dataclass
class ChannelMessage:
    """An incoming message from a channel."""

    channel_id: str
    sender_id: str
    sender_name: str
    text: str
    chat_id: str
    message_id: str | None = None
    reply_to_message_id: str | None = None
    is_group: bool = False
    is_owner: bool = False
    raw: Any = None  # channel-specific raw payload
    media: list[dict[str, Any]] = field(default_factory=list)
    display_name: str | None = None
    group_id: str | None = None
    message_thread_id: int | None = None  # forum topic (Telegram)

    @property
    def channel(self) -> str:
        """Alias for channel_id (backward compat)."""
        return self.channel_id


@dataclass
class ChannelReply:
    """A reply to send back through a channel."""

    text: str
    chat_id: str
    reply_to_message_id: str | None = None
    parse_mode: str | None = None  # "markdown", "html", etc.
    recipient: str | None = None
    recipient_id: str | None = None
    raw: Any = None  # channel-specific raw payload
    media_url: str | None = None
    channel: str | None = None
    message_thread_id: int | None = None  # forum topic (Telegram)


# ---------------------------------------------------------------------------
# Optional capability protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class TypingCapable(Protocol):
    """Channel supports sending typing indicators."""

    async def send_typing(self, chat_id: str) -> None: ...
    async def stop_typing(self, chat_id: str) -> None: ...


@runtime_checkable
class PlaceholderCapable(Protocol):
    """Channel supports placeholder messages (edit-in-place streaming)."""

    async def send_placeholder(self, chat_id: str, text: str) -> str:
        """Send a placeholder message, return the message_id for later editing."""
        ...

    async def edit_placeholder(self, chat_id: str, message_id: str, text: str) -> None: ...
    async def remove_placeholder(self, chat_id: str, message_id: str) -> None: ...


@runtime_checkable
class ReactionCapable(Protocol):
    """Channel supports adding/removing reactions."""

    async def add_reaction(self, chat_id: str, message_id: str, emoji: str) -> None: ...
    async def remove_reaction(self, chat_id: str, message_id: str, emoji: str) -> None: ...


@runtime_checkable
class MediaSendCapable(Protocol):
    """Channel supports sending media (images, files, audio, video)."""

    async def send_media(
        self,
        chat_id: str,
        media_url: str,
        *,
        caption: str = "",
        media_type: str = "image",
    ) -> None: ...


@runtime_checkable
class MessageEditCapable(Protocol):
    """Channel supports editing previously sent messages."""

    async def edit_message(self, chat_id: str, message_id: str, new_text: str) -> None: ...


@runtime_checkable
class MessageDeleteCapable(Protocol):
    """Channel supports deleting messages."""

    async def delete_message(self, chat_id: str, message_id: str) -> None: ...


# ---------------------------------------------------------------------------
# Capability detection
# ---------------------------------------------------------------------------


@dataclass
class ChannelCapabilities:
    """Runtime-detected capabilities for a channel instance."""

    typing: bool = False
    placeholder: bool = False
    reactions: bool = False
    media_send: bool = False
    message_edit: bool = False
    message_delete: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "typing": self.typing,
            "placeholder": self.placeholder,
            "reactions": self.reactions,
            "media_send": self.media_send,
            "editing": self.message_edit,
            "deletion": self.message_delete,
        }


def detect_capabilities(plugin: Any) -> ChannelCapabilities:
    """Detect which optional capability protocols a channel plugin implements."""
    return ChannelCapabilities(
        typing=isinstance(plugin, TypingCapable),
        placeholder=isinstance(plugin, PlaceholderCapable),
        reactions=isinstance(plugin, ReactionCapable),
        media_send=isinstance(plugin, MediaSendCapable),
        message_edit=isinstance(plugin, MessageEditCapable),
        message_delete=isinstance(plugin, MessageDeleteCapable),
    )


# ---------------------------------------------------------------------------
# Base plugin class
# ---------------------------------------------------------------------------


class StabilityLevel(str, Enum):
    """Maturity / stability of a channel implementation."""

    STABLE = "stable"
    BETA = "beta"
    ALPHA = "alpha"
    EXPERIMENTAL = "experimental"


@dataclass
class ChannelMeta:
    """Structured metadata template for a channel plugin.

    Every channel should expose this through ``ChannelPlugin.meta`` so that
    the catalog, UI, and test harness can consume a single source of truth.
    """

    stability: StabilityLevel = StabilityLevel.ALPHA
    version: str = "0.0.0"
    author: str = ""
    homepage: str = ""
    requires: list[str] = field(default_factory=list)
    optional_deps: list[str] = field(default_factory=list)
    supports_webhook: bool = False
    supports_polling: bool = False
    supports_websocket: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "stability": self.stability.value,
            "version": self.version,
            "author": self.author,
            "homepage": self.homepage,
            "requires": self.requires,
            "optional_deps": self.optional_deps,
            "supports_webhook": self.supports_webhook,
            "supports_polling": self.supports_polling,
            "supports_websocket": self.supports_websocket,
        }


class ChannelPlugin(ABC):
    """Abstract base class for a messaging channel."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique channel identifier (e.g. 'telegram', 'discord')."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable channel name."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start the channel (connect, begin polling/listening)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel gracefully."""
        ...

    @abstractmethod
    async def send_reply(self, reply: ChannelReply) -> None:
        """Send a reply message through this channel."""
        ...

    @property
    def is_running(self) -> bool:
        """Whether the channel is currently running."""
        return False

    @property
    def meta(self) -> ChannelMeta:
        """Structured metadata about this channel plugin.

        Subclasses should override to provide accurate metadata.
        """
        return ChannelMeta()

    def on_message(self, callback: Any) -> None:
        """Register a callback for incoming messages.

        The callback signature: async def handler(msg: ChannelMessage) -> None
        """
        self._message_callback = callback

    @property
    def message_callback(self) -> Any:
        return getattr(self, "_message_callback", None)

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Runtime-detected capabilities for this channel instance."""
        return detect_capabilities(self)

    def dod_report(self) -> dict[str, Any]:
        """Generate a Definition-of-Done report for this channel.

        Useful for automated quality checks and onboarding new channels.
        """
        caps = self.capabilities
        m = self.meta
        catalog_entry = None
        try:
            from pyclaw.channels.plugins.catalog import BUILTIN_CATALOG

            catalog_entry = BUILTIN_CATALOG.get(self.id)
        except ImportError:
            pass

        return {
            "channel_id": self.id,
            "channel_name": self.name,
            "meta": m.to_dict(),
            "capabilities": caps.to_dict(),
            "has_catalog_entry": catalog_entry is not None,
            "has_typing": caps.typing,
            "has_placeholder": caps.placeholder,
            "has_reactions": caps.reactions,
            "has_media_send": caps.media_send,
            "has_message_edit": caps.message_edit,
            "has_message_delete": caps.message_delete,
        }
