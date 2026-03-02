"""Auto-reply engine — NO_REPLY suppression, streaming sentinel filtering, heartbeat detection.

Ported from ``src/auto-reply/`` in the TypeScript codebase.

Handles the post-processing of agent responses before they reach outbound
channels: suppresses ``NO_REPLY`` sentinels, filters partial streaming
fragments (``NO_``, ``NO_RE``, ``HEARTBEAT_``), and detects heartbeat
keepalive patterns.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReplyAction(str, Enum):
    SEND = "send"
    SUPPRESS = "suppress"
    HEARTBEAT = "heartbeat"


NO_REPLY_SENTINEL = "NO_REPLY"
HEARTBEAT_PREFIX = "HEARTBEAT_"

_STREAMING_SENTINEL_FRAGMENTS = [
    "NO_",
    "NO_R",
    "NO_RE",
    "NO_REP",
    "NO_REPL",
    "NO_REPLY",
    "HE",
    "HEA",
    "HEAR",
    "HEART",
    "HEARTB",
    "HEARTBE",
    "HEARTBEA",
    "HEARTBEAT",
    "HEARTBEAT_",
]

_HEARTBEAT_PATTERN = re.compile(r"^HEARTBEAT_\w+$", re.IGNORECASE)


@dataclass
class AutoReplyConfig:
    """Configuration for auto-reply behavior."""

    suppress_no_reply: bool = True
    suppress_heartbeat: bool = True
    filter_streaming_sentinels: bool = True
    heartbeat_keywords: list[str] = field(default_factory=lambda: [
        "HEARTBEAT_PING",
        "HEARTBEAT_KEEPALIVE",
        "HEARTBEAT_CHECK",
    ])


@dataclass
class ReplyDecision:
    """Result of evaluating a reply for auto-reply suppression."""

    action: ReplyAction
    text: str
    original_text: str
    reason: str = ""


def evaluate_reply(text: str, *, config: AutoReplyConfig | None = None) -> ReplyDecision:
    """Evaluate a final reply text and decide whether to send, suppress, or mark as heartbeat."""
    cfg = config or AutoReplyConfig()
    original = text
    stripped = text.strip()

    if not stripped:
        return ReplyDecision(
            action=ReplyAction.SUPPRESS,
            text="",
            original_text=original,
            reason="empty reply",
        )

    # Exact NO_REPLY match
    if cfg.suppress_no_reply and stripped == NO_REPLY_SENTINEL:
        return ReplyDecision(
            action=ReplyAction.SUPPRESS,
            text="",
            original_text=original,
            reason="NO_REPLY sentinel",
        )

    # Heartbeat detection
    if cfg.suppress_heartbeat and _HEARTBEAT_PATTERN.match(stripped):
        return ReplyDecision(
            action=ReplyAction.HEARTBEAT,
            text=stripped,
            original_text=original,
            reason=f"heartbeat: {stripped}",
        )

    # NO_REPLY embedded at end (e.g. "Some text NO_REPLY")
    if cfg.suppress_no_reply and stripped.endswith(NO_REPLY_SENTINEL):
        cleaned = stripped[: -len(NO_REPLY_SENTINEL)].rstrip()
        if cleaned:
            return ReplyDecision(
                action=ReplyAction.SEND,
                text=cleaned,
                original_text=original,
                reason="stripped trailing NO_REPLY",
            )
        return ReplyDecision(
            action=ReplyAction.SUPPRESS,
            text="",
            original_text=original,
            reason="only NO_REPLY sentinel",
        )

    return ReplyDecision(
        action=ReplyAction.SEND,
        text=stripped,
        original_text=original,
    )


# ---------------------------------------------------------------------------
# Streaming sentinel filter
# ---------------------------------------------------------------------------

class StreamingSentinelFilter:
    """Filters partial NO_REPLY / HEARTBEAT sentinels from streaming text.

    Buffers the tail of streaming output to detect sentinel prefixes
    that may be split across chunks. Emits clean text and holds back
    potential sentinel fragments until resolved.
    """

    def __init__(self, config: AutoReplyConfig | None = None) -> None:
        self._config = config or AutoReplyConfig()
        self._buffer = ""
        self._max_sentinel_len = max(len(s) for s in _STREAMING_SENTINEL_FRAGMENTS)

    def feed(self, chunk: str) -> str:
        """Feed a streaming chunk and return safe-to-emit text.

        Text that might be a partial sentinel is buffered.
        """
        if not self._config.filter_streaming_sentinels:
            return chunk

        self._buffer += chunk
        safe, held = self._split_safe()
        self._buffer = held
        return safe

    def flush(self) -> tuple[str, ReplyAction]:
        """Flush remaining buffer, returning text and action.

        Call this when streaming is complete.
        """
        remaining = self._buffer
        self._buffer = ""

        if not remaining:
            return "", ReplyAction.SEND

        stripped = remaining.strip()

        if stripped == NO_REPLY_SENTINEL:
            return "", ReplyAction.SUPPRESS

        if _HEARTBEAT_PATTERN.match(stripped):
            return stripped, ReplyAction.HEARTBEAT

        return remaining, ReplyAction.SEND

    def _split_safe(self) -> tuple[str, str]:
        """Split buffer into safe-to-emit and held-back portions."""
        buf = self._buffer

        if not buf:
            return "", ""

        # Hold back the entire buffer if it matches a complete sentinel/heartbeat
        stripped = buf.strip()
        if stripped == NO_REPLY_SENTINEL or _HEARTBEAT_PATTERN.match(stripped):
            return "", buf

        # Check if the tail of the buffer matches any sentinel prefix
        for length in range(min(len(buf), self._max_sentinel_len), 0, -1):
            tail = buf[-length:]
            if any(s.startswith(tail) for s in _STREAMING_SENTINEL_FRAGMENTS):
                return buf[:-length], tail

        return buf, ""


# ---------------------------------------------------------------------------
# Conversation timestamp helper
# ---------------------------------------------------------------------------

@dataclass
class ConversationTimestamp:
    """Readable timestamp for conversation info injection."""

    unix: float = 0.0

    def __post_init__(self) -> None:
        if self.unix == 0.0:
            self.unix = time.time()

    @property
    def iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.unix))

    @property
    def readable(self) -> str:
        return time.strftime("%B %d, %Y %H:%M UTC", time.gmtime(self.unix))

    @property
    def is_valid(self) -> bool:
        # Reject timestamps before 2020 or far future
        return 1577836800 < self.unix < 2524608000

    @classmethod
    def from_value(cls, value: Any) -> ConversationTimestamp | None:
        """Parse a timestamp from various formats, returning None for invalid values."""
        if value is None:
            return None
        try:
            ts = float(value)
            ct = cls(unix=ts)
            return ct if ct.is_valid else None
        except (ValueError, TypeError, OverflowError):
            return None
