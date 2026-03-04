"""Per-channel outbound adapters — format, chunk, retry logic per channel.

Ported from ``src/channels/*/outbound.ts`` and ``src/channels/channel-outbound.ts``.

Provides:
- Per-channel outbound send adapters with format preferences
- Message chunking per channel constraints
- Retry strategies per channel
- Target normalization (chat ID formatting)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MessageFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN = "plain"
    SLACK_MRKDWN = "slack_mrkdwn"
    WHATSAPP = "whatsapp"


class RetryStrategy(str, Enum):
    NONE = "none"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    IMMEDIATE = "immediate"


@dataclass
class OutboundConfig:
    """Per-channel outbound configuration."""

    channel_type: str
    max_message_length: int = 4096
    preferred_format: MessageFormat = MessageFormat.MARKDOWN
    fallback_formats: list[MessageFormat] = field(default_factory=lambda: [MessageFormat.HTML, MessageFormat.PLAIN])
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    max_retries: int = 3
    supports_media: bool = True
    chunk_separator: str = ""
    preserve_code_blocks: bool = True


@dataclass
class ChunkedMessage:
    """A message split into chunks respecting channel limits."""

    chunks: list[str] = field(default_factory=list)
    total_length: int = 0
    was_chunked: bool = False


def chunk_message(
    text: str,
    max_length: int,
    *,
    preserve_code_blocks: bool = True,
    separator: str = "",
) -> ChunkedMessage:
    """Split a message into chunks respecting max length.

    Tries to split at paragraph boundaries, then sentence boundaries,
    then word boundaries. Preserves code blocks when possible.
    """
    if len(text) <= max_length:
        return ChunkedMessage(chunks=[text], total_length=len(text))

    chunks: list[str] = []

    if preserve_code_blocks:
        # Try splitting outside code blocks
        parts = re.split(r"(```[\s\S]*?```)", text)
        buffer = ""
        for part in parts:
            if len(buffer) + len(part) <= max_length:
                buffer += part
            else:
                if buffer:
                    chunks.append(buffer.strip())
                if len(part) <= max_length:
                    buffer = part
                else:
                    # Force-split oversized part
                    for sub in _force_split(part, max_length):
                        chunks.append(sub)
                    buffer = ""
        if buffer.strip():
            chunks.append(buffer.strip())
    else:
        chunks = _force_split(text, max_length)

    sep = separator
    if sep:
        chunks = [c + sep for c in chunks[:-1]] + chunks[-1:]

    return ChunkedMessage(
        chunks=chunks,
        total_length=sum(len(c) for c in chunks),
        was_chunked=len(chunks) > 1,
    )


def _force_split(text: str, max_length: int) -> list[str]:
    """Force-split text at paragraph/line boundaries."""
    result: list[str] = []
    lines = text.split("\n")
    buffer = ""

    for line in lines:
        if len(buffer) + len(line) + 1 <= max_length:
            buffer += ("" if not buffer else "\n") + line
        else:
            if buffer:
                result.append(buffer)
            if len(line) <= max_length:
                buffer = line
            else:
                # Hard split at max_length
                while len(line) > max_length:
                    result.append(line[:max_length])
                    line = line[max_length:]
                buffer = line

    if buffer:
        result.append(buffer)

    return result


def normalize_target(channel_type: str, target: str) -> str:
    """Normalize a chat target ID for a specific channel."""
    target = target.strip()

    if channel_type == "telegram":
        if target.startswith("@"):
            return target
        try:
            return str(int(target))
        except ValueError:
            return target

    if channel_type == "discord":
        return target.strip("<>#@!")

    if channel_type == "signal":
        if target.startswith("+"):
            return target
        return target

    return target


# Per-channel outbound configs
CHANNEL_OUTBOUND_CONFIGS: dict[str, OutboundConfig] = {
    "telegram": OutboundConfig(
        channel_type="telegram",
        max_message_length=4096,
        preferred_format=MessageFormat.HTML,
        fallback_formats=[MessageFormat.MARKDOWN, MessageFormat.PLAIN],
    ),
    "discord": OutboundConfig(
        channel_type="discord",
        max_message_length=2000,
        preferred_format=MessageFormat.MARKDOWN,
    ),
    "slack": OutboundConfig(
        channel_type="slack",
        max_message_length=40000,
        preferred_format=MessageFormat.SLACK_MRKDWN,
        fallback_formats=[MessageFormat.PLAIN],
    ),
    "whatsapp": OutboundConfig(
        channel_type="whatsapp",
        max_message_length=65536,
        preferred_format=MessageFormat.WHATSAPP,
        fallback_formats=[MessageFormat.PLAIN],
    ),
    "signal": OutboundConfig(
        channel_type="signal",
        max_message_length=65536,
        preferred_format=MessageFormat.PLAIN,
    ),
    "imessage": OutboundConfig(
        channel_type="imessage",
        max_message_length=20000,
        preferred_format=MessageFormat.PLAIN,
    ),
    "matrix": OutboundConfig(
        channel_type="matrix",
        max_message_length=65536,
        preferred_format=MessageFormat.HTML,
        fallback_formats=[MessageFormat.MARKDOWN, MessageFormat.PLAIN],
    ),
    "feishu": OutboundConfig(
        channel_type="feishu",
        max_message_length=30000,
        preferred_format=MessageFormat.MARKDOWN,
        fallback_formats=[MessageFormat.PLAIN],
    ),
    "msteams": OutboundConfig(
        channel_type="msteams",
        max_message_length=28000,
        preferred_format=MessageFormat.HTML,
        fallback_formats=[MessageFormat.MARKDOWN, MessageFormat.PLAIN],
    ),
    "dingtalk": OutboundConfig(
        channel_type="dingtalk",
        max_message_length=20000,
        preferred_format=MessageFormat.MARKDOWN,
        fallback_formats=[MessageFormat.PLAIN],
    ),
    "irc": OutboundConfig(
        channel_type="irc",
        max_message_length=512,
        preferred_format=MessageFormat.PLAIN,
        supports_media=False,
        preserve_code_blocks=False,
    ),
    "mattermost": OutboundConfig(
        channel_type="mattermost",
        max_message_length=16383,
        preferred_format=MessageFormat.MARKDOWN,
    ),
    "googlechat": OutboundConfig(
        channel_type="googlechat",
        max_message_length=4096,
        preferred_format=MessageFormat.PLAIN,
    ),
    "line": OutboundConfig(
        channel_type="line",
        max_message_length=5000,
        preferred_format=MessageFormat.PLAIN,
    ),
    "qq": OutboundConfig(
        channel_type="qq",
        max_message_length=4500,
        preferred_format=MessageFormat.MARKDOWN,
        fallback_formats=[MessageFormat.PLAIN],
    ),
    "twitch": OutboundConfig(
        channel_type="twitch",
        max_message_length=500,
        preferred_format=MessageFormat.PLAIN,
        supports_media=False,
    ),
    "nostr": OutboundConfig(
        channel_type="nostr",
        max_message_length=65536,
        preferred_format=MessageFormat.PLAIN,
    ),
}


def get_outbound_config(channel_type: str) -> OutboundConfig:
    """Get the outbound config for a channel type."""
    return CHANNEL_OUTBOUND_CONFIGS.get(
        channel_type,
        OutboundConfig(channel_type=channel_type),
    )


class OutboundAdapter:
    """Per-channel outbound adapter for formatting and sending."""

    def __init__(self, config: OutboundConfig) -> None:
        self._config = config

    def prepare(self, text: str) -> ChunkedMessage:
        """Chunk and format a message for this channel."""
        return chunk_message(
            text,
            self._config.max_message_length,
            preserve_code_blocks=self._config.preserve_code_blocks,
        )

    def format_text(self, text: str, fmt: MessageFormat | None = None) -> str:
        """Apply format-specific transformations."""
        fmt = fmt or self._config.preferred_format
        if fmt == MessageFormat.PLAIN:
            return re.sub(r"[*_~`]", "", text)
        return text

    @property
    def config(self) -> OutboundConfig:
        return self._config
