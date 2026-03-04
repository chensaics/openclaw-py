"""Channel adapters — channel selection, direct text/media, resolution.

Ported from ``src/infra/outbound/channel-adapters.ts``.

Provides:
- Channel adapter protocol for outbound sending
- Channel capability detection
- Direct text and media sending helpers
- Channel resolution from ID or type
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class MediaType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    VOICE = "voice"
    STICKER = "sticker"


@dataclass
class ChannelCapabilities:
    """What a channel supports for outbound messages."""

    markdown: bool = True
    html: bool = False
    buttons: bool = False
    reactions: bool = False
    threads: bool = False
    media: bool = True
    voice: bool = False
    max_text_length: int = 4096
    max_caption_length: int = 1024
    supported_media: list[MediaType] = field(default_factory=lambda: [MediaType.IMAGE, MediaType.DOCUMENT])


@dataclass
class OutboundMedia:
    """Media attachment for outbound messages."""

    type: MediaType
    url: str = ""
    data: bytes = b""
    filename: str = ""
    mime_type: str = ""
    caption: str = ""


@dataclass
class OutboundPayload:
    """Payload for channel adapter sending."""

    chat_id: str
    text: str = ""
    media: list[OutboundMedia] = field(default_factory=list)
    reply_to: str = ""
    thread_id: str = ""
    parse_mode: str = ""  # "markdown" | "html" | ""
    buttons: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundResult:
    """Result from a channel adapter send."""

    success: bool
    message_id: str = ""
    error: str = ""


class ChannelAdapter(Protocol):
    """Protocol for channel outbound adapters."""

    @property
    def channel_type(self) -> str: ...

    @property
    def capabilities(self) -> ChannelCapabilities: ...

    async def send_text(self, payload: OutboundPayload) -> OutboundResult: ...

    async def send_media(self, payload: OutboundPayload) -> OutboundResult: ...


class ChannelAdapterRegistry:
    """Registry for channel outbound adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.channel_type] = adapter

    def get(self, channel_type: str) -> ChannelAdapter | None:
        return self._adapters.get(channel_type)

    def list_channels(self) -> list[str]:
        return sorted(self._adapters.keys())

    def get_capabilities(self, channel_type: str) -> ChannelCapabilities | None:
        adapter = self._adapters.get(channel_type)
        return adapter.capabilities if adapter else None

    async def send(self, channel_type: str, payload: OutboundPayload) -> OutboundResult:
        """Send via the appropriate channel adapter."""
        adapter = self._adapters.get(channel_type)
        if not adapter:
            return OutboundResult(success=False, error=f"No adapter for {channel_type}")

        if payload.media:
            return await adapter.send_media(payload)
        return await adapter.send_text(payload)

    def select_best_channel(
        self,
        candidates: list[str],
        *,
        needs_media: bool = False,
        needs_buttons: bool = False,
        needs_threads: bool = False,
    ) -> str | None:
        """Select the best channel from candidates based on requirements."""
        for ch in candidates:
            adapter = self._adapters.get(ch)
            if not adapter:
                continue
            caps = adapter.capabilities
            if needs_media and not caps.media:
                continue
            if needs_buttons and not caps.buttons:
                continue
            if needs_threads and not caps.threads:
                continue
            return ch

        # Fallback to first available
        for ch in candidates:
            if ch in self._adapters:
                return ch
        return None
