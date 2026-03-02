"""Telegram enhanced features — reply media context, outbound chunking, chat action backoff.

Ported from ``src/telegram/`` enhancements in the TypeScript codebase.

Provides:
- Reply media context extraction (photo, document, audio, video in replied messages)
- Outbound message chunking with Telegram's 4096-char limit
- sendChatAction backoff with circuit breaker for rate-limit errors
- Message formatting helpers (MarkdownV2 escaping, HTML fallback)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_MAX_CAPTION_LENGTH = 1024


class ChatAction(str, Enum):
    TYPING = "typing"
    UPLOAD_PHOTO = "upload_photo"
    UPLOAD_DOCUMENT = "upload_document"
    UPLOAD_VIDEO = "upload_video"
    RECORD_VOICE = "record_voice"
    RECORD_VIDEO_NOTE = "record_video_note"


@dataclass
class ReplyMediaContext:
    """Media context extracted from a replied-to message."""

    media_type: str = ""  # "photo" | "document" | "audio" | "video" | "voice" | "sticker"
    file_id: str = ""
    file_unique_id: str = ""
    file_name: str = ""
    mime_type: str = ""
    file_size: int = 0
    caption: str = ""
    thumbnail_file_id: str = ""
    duration: int = 0  # for audio/video
    width: int = 0  # for photo/video
    height: int = 0


def extract_reply_media_context(reply_message: dict[str, Any]) -> ReplyMediaContext | None:
    """Extract media context from a Telegram reply_to_message payload.

    Inspects photo, document, audio, video, voice, video_note, and sticker
    fields in priority order.
    """
    if not reply_message:
        return None

    caption = reply_message.get("caption", "")

    # Photo (array of PhotoSize, pick largest)
    photos = reply_message.get("photo")
    if photos and isinstance(photos, list):
        largest = max(photos, key=lambda p: p.get("file_size", 0))
        return ReplyMediaContext(
            media_type="photo",
            file_id=largest.get("file_id", ""),
            file_unique_id=largest.get("file_unique_id", ""),
            file_size=largest.get("file_size", 0),
            width=largest.get("width", 0),
            height=largest.get("height", 0),
            caption=caption,
        )

    # Document
    doc = reply_message.get("document")
    if doc:
        thumb = doc.get("thumbnail", doc.get("thumb", {}))
        return ReplyMediaContext(
            media_type="document",
            file_id=doc.get("file_id", ""),
            file_unique_id=doc.get("file_unique_id", ""),
            file_name=doc.get("file_name", ""),
            mime_type=doc.get("mime_type", ""),
            file_size=doc.get("file_size", 0),
            caption=caption,
            thumbnail_file_id=thumb.get("file_id", "") if thumb else "",
        )

    # Audio
    audio = reply_message.get("audio")
    if audio:
        return ReplyMediaContext(
            media_type="audio",
            file_id=audio.get("file_id", ""),
            file_unique_id=audio.get("file_unique_id", ""),
            file_name=audio.get("file_name", ""),
            mime_type=audio.get("mime_type", ""),
            file_size=audio.get("file_size", 0),
            duration=audio.get("duration", 0),
            caption=caption,
        )

    # Video
    video = reply_message.get("video")
    if video:
        return ReplyMediaContext(
            media_type="video",
            file_id=video.get("file_id", ""),
            file_unique_id=video.get("file_unique_id", ""),
            file_name=video.get("file_name", ""),
            mime_type=video.get("mime_type", ""),
            file_size=video.get("file_size", 0),
            duration=video.get("duration", 0),
            width=video.get("width", 0),
            height=video.get("height", 0),
            caption=caption,
        )

    # Voice
    voice = reply_message.get("voice")
    if voice:
        return ReplyMediaContext(
            media_type="voice",
            file_id=voice.get("file_id", ""),
            file_unique_id=voice.get("file_unique_id", ""),
            mime_type=voice.get("mime_type", ""),
            file_size=voice.get("file_size", 0),
            duration=voice.get("duration", 0),
        )

    # Sticker
    sticker = reply_message.get("sticker")
    if sticker:
        return ReplyMediaContext(
            media_type="sticker",
            file_id=sticker.get("file_id", ""),
            file_unique_id=sticker.get("file_unique_id", ""),
            file_size=sticker.get("file_size", 0),
            width=sticker.get("width", 0),
            height=sticker.get("height", 0),
        )

    return None


# ---------------------------------------------------------------------------
# Outbound chunking
# ---------------------------------------------------------------------------


def chunk_telegram_message(
    text: str,
    *,
    max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH,
) -> list[str]:
    """Split a message into Telegram-safe chunks.

    Splitting priorities:
    1. Double newline (paragraph)
    2. Single newline
    3. Sentence boundary
    4. Space
    5. Hard split
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        split_at = _find_telegram_split(remaining, max_length)
        chunk = remaining[:split_at].rstrip()
        remaining = remaining[split_at:].lstrip()

        if chunk:
            chunks.append(chunk)

    return chunks if chunks else [text]


def _find_telegram_split(text: str, max_len: int) -> int:
    """Find the best split point within max_len chars."""
    window = text[:max_len]

    for sep in ["\n\n", "\n"]:
        pos = window.rfind(sep)
        if pos > max_len // 4:
            return pos + len(sep)

    for punct in [". ", "! ", "? ", "。", "！", "？"]:
        pos = window.rfind(punct)
        if pos > max_len // 4:
            return pos + len(punct)

    pos = window.rfind(" ")
    if pos > max_len // 4:
        return pos + 1

    return max_len


# ---------------------------------------------------------------------------
# MarkdownV2 escaping
# ---------------------------------------------------------------------------

_MARKDOWN_V2_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2 parse mode."""
    return _MARKDOWN_V2_SPECIAL.sub(r"\\\1", text)


def markdown_to_telegram_html(text: str) -> str:
    """Convert basic Markdown to Telegram-compatible HTML.

    Handles bold, italic, code, code blocks, and links.
    """
    result = text

    # Code blocks first
    result = re.sub(
        r"```(\w*)\n(.*?)```",
        lambda m: (
            f'<pre><code class="language-{m.group(1)}">{_html_escape(m.group(2))}</code></pre>'
        ),
        result,
        flags=re.DOTALL,
    )

    # Inline code
    result = re.sub(
        r"`([^`]+)`",
        lambda m: f"<code>{_html_escape(m.group(1))}</code>",
        result,
    )

    # Bold
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result)
    # Italic
    result = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", result)
    # Links
    result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', result)

    return result


def _html_escape(text: str) -> str:
    """Minimal HTML escape for Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# sendChatAction backoff
# ---------------------------------------------------------------------------


@dataclass
class ChatActionBackoffState:
    """Per-chat backoff state for sendChatAction."""

    consecutive_failures: int = 0
    suppressed_until: float = 0.0

    @property
    def is_suppressed(self) -> bool:
        return time.time() < self.suppressed_until


class ChatActionBackoff:
    """Circuit breaker for Telegram sendChatAction API calls.

    Stops calling sendChatAction after consecutive 429 / rate-limit errors
    and applies exponential backoff before resuming.
    """

    def __init__(
        self,
        *,
        max_consecutive: int = 3,
        base_delay_s: float = 15.0,
        max_delay_s: float = 120.0,
    ) -> None:
        self._max_consecutive = max_consecutive
        self._base_delay = base_delay_s
        self._max_delay = max_delay_s
        self._states: dict[str, ChatActionBackoffState] = {}

    def should_send(self, chat_id: str) -> bool:
        state = self._states.get(chat_id)
        if state is None:
            return True
        return not state.is_suppressed

    def record_success(self, chat_id: str) -> None:
        state = self._states.get(chat_id)
        if state:
            state.consecutive_failures = 0

    def record_failure(self, chat_id: str, *, status_code: int = 0) -> None:
        if chat_id not in self._states:
            self._states[chat_id] = ChatActionBackoffState()

        state = self._states[chat_id]
        state.consecutive_failures += 1

        if status_code == 429 or state.consecutive_failures >= self._max_consecutive:
            delay = min(
                self._base_delay * (2 ** (state.consecutive_failures - 1)),
                self._max_delay,
            )
            state.suppressed_until = time.time() + delay
            logger.info(
                "Telegram chatAction suppressed for %s (%.0fs, code=%d)",
                chat_id,
                delay,
                status_code,
            )

    def reset(self, chat_id: str) -> None:
        self._states.pop(chat_id, None)

    def reset_all(self) -> None:
        self._states.clear()
