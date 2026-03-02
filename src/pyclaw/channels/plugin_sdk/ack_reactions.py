"""Acknowledgment reactions — reaction scopes and status reactions.

Ported from ``src/channels/channel-plugin-sdk/ack-reactions*.ts``.

Provides:
- Reaction scope configuration (all, direct, group-all, group-mentions, off)
- Status reaction mapping (thinking, tool-use, error, done)
- Reaction application logic
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ReactionScope(str, Enum):
    """When to apply acknowledgment reactions."""

    ALL = "all"  # All messages
    DIRECT = "direct"  # DMs only
    GROUP_ALL = "group-all"  # All group messages
    GROUP_MENTIONS = "group-mentions"  # Group messages mentioning the bot
    OFF = "off"  # Disabled


class StatusType(str, Enum):
    """Status types for status reactions."""

    THINKING = "thinking"
    TOOL_USE = "tool-use"
    ERROR = "error"
    DONE = "done"
    QUEUED = "queued"


@dataclass
class ReactionConfig:
    """Configuration for acknowledgment reactions."""

    scope: ReactionScope = ReactionScope.ALL
    thinking_emoji: str = "🤔"
    tool_use_emoji: str = "⚙️"
    error_emoji: str = "❌"
    done_emoji: str = "✅"
    queued_emoji: str = "⏳"
    clear_on_done: bool = True
    clear_on_error: bool = False


@dataclass
class ReactionState:
    """Current reaction state for a message."""

    message_id: str
    chat_id: str
    current_emoji: str = ""
    status: StatusType | None = None
    applied: bool = False


def get_status_emoji(config: ReactionConfig, status: StatusType) -> str:
    """Get the emoji for a status type."""
    mapping = {
        StatusType.THINKING: config.thinking_emoji,
        StatusType.TOOL_USE: config.tool_use_emoji,
        StatusType.ERROR: config.error_emoji,
        StatusType.DONE: config.done_emoji,
        StatusType.QUEUED: config.queued_emoji,
    }
    return mapping.get(status, "")


def should_react(
    config: ReactionConfig,
    *,
    is_group: bool = False,
    is_mention: bool = False,
    is_dm: bool = False,
) -> bool:
    """Determine if a reaction should be applied based on scope."""
    if config.scope == ReactionScope.OFF:
        return False
    if config.scope == ReactionScope.ALL:
        return True
    if config.scope == ReactionScope.DIRECT:
        return is_dm or not is_group
    if config.scope == ReactionScope.GROUP_ALL:
        return is_group
    if config.scope == ReactionScope.GROUP_MENTIONS:
        return is_group and is_mention
    return False


def should_clear_reaction(config: ReactionConfig, status: StatusType) -> bool:
    """Determine if the reaction should be cleared for a given status."""
    if status == StatusType.DONE and config.clear_on_done:
        return True
    if status == StatusType.ERROR and config.clear_on_error:
        return True
    return False


class AckReactionManager:
    """Manage acknowledgment reactions for messages."""

    def __init__(self, config: ReactionConfig | None = None) -> None:
        self._config = config or ReactionConfig()
        self._states: dict[str, ReactionState] = {}

    @property
    def config(self) -> ReactionConfig:
        return self._config

    def track(self, message_id: str, chat_id: str) -> ReactionState:
        """Start tracking a message for reactions."""
        state = ReactionState(message_id=message_id, chat_id=chat_id)
        self._states[message_id] = state
        return state

    def get_state(self, message_id: str) -> ReactionState | None:
        return self._states.get(message_id)

    def update_status(self, message_id: str, status: StatusType) -> ReactionState | None:
        """Update the status of a tracked message.

        Returns the state if a reaction change is needed, None otherwise.
        """
        state = self._states.get(message_id)
        if not state:
            return None

        emoji = get_status_emoji(self._config, status)
        if emoji == state.current_emoji:
            return None

        state.status = status
        state.current_emoji = emoji
        state.applied = True

        if should_clear_reaction(self._config, status):
            state.current_emoji = ""
            state.applied = False

        return state

    def untrack(self, message_id: str) -> None:
        self._states.pop(message_id, None)

    def clear_all(self) -> int:
        count = len(self._states)
        self._states.clear()
        return count

    @property
    def tracked_count(self) -> int:
        return len(self._states)
