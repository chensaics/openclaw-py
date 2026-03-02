"""Outbound pipeline — shared chunking, formatting, and retry for channel sends.

Ported from ``src/channels/plugins/outbound/`` in the TypeScript codebase.

Provides a unified outbound processing pipeline that:
- Splits oversized messages into safe chunks
- Retries failed sends with format fallback (Markdown → HTML → plain)
- Preserves boundary whitespace during re-splitting
- Handles sub-channel dispatch for multi-account channels
"""

from __future__ import annotations

import html
import logging
import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Telegram limit is 4096 chars, Discord 2000, Slack 40000
DEFAULT_MAX_CHUNK_SIZE = 4000
TELEGRAM_MAX_SIZE = 4096
DISCORD_MAX_SIZE = 2000
SLACK_MAX_SIZE = 40000


class MessageFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN = "plain"


@dataclass
class OutboundMessage:
    """A message ready for outbound delivery."""

    text: str
    chat_id: str
    channel_id: str = ""
    reply_to_message_id: str | None = None
    format: MessageFormat = MessageFormat.MARKDOWN
    parse_mode: str | None = None
    media: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundChunk:
    """A single chunk after splitting."""

    text: str
    index: int
    total: int
    is_last: bool
    format: MessageFormat = MessageFormat.MARKDOWN


SendCallback = Callable[[OutboundChunk], Coroutine[Any, Any, bool]]


def get_channel_max_size(channel_id: str) -> int:
    """Get the maximum message size for a channel."""
    channel_lower = channel_id.lower()
    if "telegram" in channel_lower:
        return TELEGRAM_MAX_SIZE
    if "discord" in channel_lower:
        return DISCORD_MAX_SIZE
    if "slack" in channel_lower:
        return SLACK_MAX_SIZE
    return DEFAULT_MAX_CHUNK_SIZE


def split_message(
    text: str,
    *,
    max_size: int = DEFAULT_MAX_CHUNK_SIZE,
    preserve_code_blocks: bool = True,
) -> list[str]:
    """Split a message into chunks that fit within max_size.

    Splitting strategy (in priority order):
    1. Double newline (paragraph boundary)
    2. Single newline
    3. Sentence boundary (. ! ?)
    4. Space
    5. Hard split at max_size
    """
    if len(text) <= max_size:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_size:
            chunks.append(remaining)
            break

        # Find the best split point
        split_at = _find_split_point(remaining, max_size)
        chunk = remaining[:split_at].rstrip()
        remaining = remaining[split_at:].lstrip()

        if chunk:
            chunks.append(chunk)

        if not remaining:
            break

    return chunks if chunks else [text]


def _find_split_point(text: str, max_size: int) -> int:
    """Find the best split point within max_size characters."""
    window = text[:max_size]

    # Priority 1: Double newline (paragraph)
    pos = window.rfind("\n\n")
    if pos > max_size // 4:
        return pos + 2

    # Priority 2: Single newline
    pos = window.rfind("\n")
    if pos > max_size // 4:
        return pos + 1

    # Priority 3: Sentence boundary
    for pattern in [". ", "! ", "? ", "。", "！", "？"]:
        pos = window.rfind(pattern)
        if pos > max_size // 4:
            return pos + len(pattern)

    # Priority 4: Space
    pos = window.rfind(" ")
    if pos > max_size // 4:
        return pos + 1

    # Priority 5: Hard split
    return max_size


def escape_html_entities(text: str) -> str:
    """Escape HTML entities in text for HTML-format channels."""
    return html.escape(text, quote=False)


def markdown_to_html_simple(text: str) -> str:
    """Simple Markdown to HTML conversion for retry fallback.

    Handles bold, italic, code, code blocks, and links.
    """
    result = text

    # Code blocks first (preserve content)
    result = re.sub(
        r"```(\w*)\n(.*?)```",
        lambda m: f"<pre><code>{escape_html_entities(m.group(2))}</code></pre>",
        result,
        flags=re.DOTALL,
    )

    # Inline code
    result = re.sub(
        r"`([^`]+)`",
        lambda m: f"<code>{escape_html_entities(m.group(1))}</code>",
        result,
    )

    # Bold
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result)
    result = re.sub(r"__(.+?)__", r"<b>\1</b>", result)

    # Italic
    result = re.sub(r"\*(.+?)\*", r"<i>\1</i>", result)
    result = re.sub(r"_(.+?)_", r"<i>\1</i>", result)

    # Links
    result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', result)

    return result


def strip_markdown(text: str) -> str:
    """Strip Markdown formatting to produce plain text."""
    result = text
    result = re.sub(r"```\w*\n?", "", result)
    result = re.sub(r"`([^`]+)`", r"\1", result)
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)
    result = re.sub(r"__(.+?)__", r"\1", result)
    result = re.sub(r"\*(.+?)\*", r"\1", result)
    result = re.sub(r"_(.+?)_", r"\1", result)
    result = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", result)
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)
    return result


async def send_with_retry(
    message: OutboundMessage,
    send_fn: SendCallback,
    *,
    max_size: int | None = None,
) -> bool:
    """Send a message with chunking and format fallback.

    Tries Markdown first, falls back to HTML, then plain text.
    """
    effective_max = max_size or get_channel_max_size(message.channel_id)
    chunks = split_message(message.text, max_size=effective_max)

    total = len(chunks)
    all_sent = True

    for i, chunk_text in enumerate(chunks):
        chunk = OutboundChunk(
            text=chunk_text,
            index=i,
            total=total,
            is_last=(i == total - 1),
            format=message.format,
        )

        success = await send_fn(chunk)
        if not success:
            # Retry with HTML
            if message.format == MessageFormat.MARKDOWN:
                html_chunk = OutboundChunk(
                    text=markdown_to_html_simple(chunk_text),
                    index=i,
                    total=total,
                    is_last=(i == total - 1),
                    format=MessageFormat.HTML,
                )
                success = await send_fn(html_chunk)

            # Retry with plain text
            if not success:
                plain_chunk = OutboundChunk(
                    text=strip_markdown(chunk_text),
                    index=i,
                    total=total,
                    is_last=(i == total - 1),
                    format=MessageFormat.PLAIN,
                )
                success = await send_fn(plain_chunk)

            if not success:
                all_sent = False
                logger.warning(
                    "Failed to send chunk %d/%d to %s:%s",
                    i + 1,
                    total,
                    message.channel_id,
                    message.chat_id,
                )

    return all_sent
