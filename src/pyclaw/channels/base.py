"""Channel plugin base — abstract interface for messaging channels.

Every channel (Telegram, Discord, Slack, ...) implements this interface
so the gateway can start/stop them uniformly and route messages through
the agent pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class ChannelReply:
    """A reply to send back through a channel."""

    text: str
    chat_id: str
    reply_to_message_id: str | None = None
    parse_mode: str | None = None  # "markdown", "html", etc.


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

    def on_message(self, callback: Any) -> None:
        """Register a callback for incoming messages.

        The callback signature: async def handler(msg: ChannelMessage) -> None
        """
        self._message_callback = callback

    @property
    def message_callback(self) -> Any:
        return getattr(self, "_message_callback", None)
