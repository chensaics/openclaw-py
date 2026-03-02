"""Mention gating — @mention detection, text command bypass, group mention handling.

Ported from ``src/channels/channel-plugin-sdk/mention-gating*.ts``.

Provides:
- Bot @mention detection with configurable patterns
- Text command bypass (process /commands even without mention)
- Group mention filtering
- Mention stripping from message text
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MentionConfig:
    """Configuration for mention gating."""

    require_mention_in_groups: bool = True
    bot_names: list[str] = field(default_factory=list)
    bot_user_id: str = ""
    command_prefix: str = "/"
    bypass_commands: bool = True  # Process /commands without @mention
    strip_mention: bool = True  # Remove @mention from text before processing
    case_sensitive: bool = False


@dataclass
class MentionResult:
    """Result of mention detection."""

    is_mentioned: bool = False
    mention_type: str = ""  # "direct" | "name" | "pattern" | ""
    cleaned_text: str = ""  # Text with mention removed
    original_text: str = ""
    is_command: bool = False  # Text starts with command prefix


class MentionDetector:
    """Detect and process bot @mentions in messages."""

    def __init__(self, config: MentionConfig) -> None:
        self._config = config
        self._patterns: list[re.Pattern[str]] = []
        self._build_patterns()

    def _build_patterns(self) -> None:
        """Build regex patterns for mention detection."""
        flags = 0 if self._config.case_sensitive else re.IGNORECASE

        # @username patterns
        for name in self._config.bot_names:
            escaped = re.escape(name)
            self._patterns.append(re.compile(rf"@{escaped}\b", flags))
            self._patterns.append(re.compile(rf"\b{escaped}\b", flags))

        # User ID mention (platform-specific, e.g. <@U123>)
        if self._config.bot_user_id:
            uid = re.escape(self._config.bot_user_id)
            self._patterns.append(re.compile(rf"<@!?{uid}>"))

    def detect(self, text: str, *, is_group: bool = False) -> MentionResult:
        """Detect if the bot is mentioned in the text.

        In DMs, always returns is_mentioned=True.
        In groups, checks for @mention patterns.
        """
        original = text
        is_command = text.strip().startswith(self._config.command_prefix)

        # DMs always match
        if not is_group:
            return MentionResult(
                is_mentioned=True,
                mention_type="direct",
                cleaned_text=text,
                original_text=original,
                is_command=is_command,
            )

        # Commands bypass mention requirement
        if is_command and self._config.bypass_commands:
            return MentionResult(
                is_mentioned=True,
                mention_type="",
                cleaned_text=text,
                original_text=original,
                is_command=True,
            )

        # Check patterns
        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                cleaned = text
                if self._config.strip_mention:
                    cleaned = pattern.sub("", text).strip()
                    cleaned = re.sub(r"\s{2,}", " ", cleaned)
                return MentionResult(
                    is_mentioned=True,
                    mention_type="pattern",
                    cleaned_text=cleaned,
                    original_text=original,
                    is_command=is_command,
                )

        return MentionResult(
            is_mentioned=False,
            cleaned_text=text,
            original_text=original,
            is_command=is_command,
        )

    def should_process(self, text: str, *, is_group: bool = False) -> bool:
        """Quick check: should this message be processed?"""
        if not is_group:
            return True
        if not self._config.require_mention_in_groups:
            return True

        result = self.detect(text, is_group=is_group)
        return result.is_mentioned

    def strip_mention(self, text: str) -> str:
        """Remove all bot mentions from text."""
        result = text
        for pattern in self._patterns:
            result = pattern.sub("", result)
        return re.sub(r"\s{2,}", " ", result).strip()

    def add_bot_name(self, name: str) -> None:
        """Add a bot name to detect."""
        self._config.bot_names.append(name)
        self._build_patterns()
