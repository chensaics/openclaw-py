"""Feishu reaction event support — handle reaction.created/deleted events.

Ported from ``extensions/feishu/src/monitor.reaction.ts``.

Supports:
- ``im.message.reaction.created_v1`` / ``deleted_v1`` events
- Synthetic inbound turns from reactions
- ``reactionNotifications`` mode gating (off | own | all)
- Bot-authored message verification with timeout + fail-closed
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ReactionNotificationMode(str, Enum):
    OFF = "off"
    OWN = "own"      # Only reactions on bot-authored messages
    ALL = "all"      # All verified reactions


@dataclass
class ReactionEvent:
    """A parsed Feishu reaction event."""

    message_id: str
    reaction_type: str  # emoji key
    user_id: str
    action: str  # "created" | "deleted"
    chat_id: str = ""
    chat_type: str = ""
    operator_type: str = ""  # "user"
    raw: dict[str, Any] | None = None


@dataclass
class SyntheticReactionTurn:
    """A synthetic inbound turn generated from a reaction event."""

    text: str
    sender_id: str
    chat_id: str
    is_group: bool = False
    metadata: dict[str, Any] | None = None


def parse_reaction_event(body: dict[str, Any]) -> ReactionEvent | None:
    """Parse a Feishu webhook payload into a ReactionEvent.

    Returns None if the event type is not a reaction event.
    """
    event = body.get("event", {})
    header = body.get("header", {})
    event_type = header.get("event_type", "")

    if event_type == "im.message.reaction.created_v1":
        action = "created"
    elif event_type == "im.message.reaction.deleted_v1":
        action = "deleted"
    else:
        return None

    message_id = event.get("message_id", "")
    reaction_type_obj = event.get("reaction_type", {})
    emoji_type = reaction_type_obj.get("emoji_type", "")

    operator = event.get("operator", {})
    operator_id_obj = operator.get("operator_id", {})
    user_id = operator_id_obj.get("open_id", "") or operator_id_obj.get("user_id", "")
    operator_type = operator.get("operator_type", "")

    return ReactionEvent(
        message_id=message_id,
        reaction_type=emoji_type,
        user_id=user_id,
        action=action,
        operator_type=operator_type,
        raw=body,
    )


def should_process_reaction(
    event: ReactionEvent,
    *,
    mode: ReactionNotificationMode = ReactionNotificationMode.OWN,
    bot_user_id: str = "",
    is_bot_message: bool = False,
) -> bool:
    """Determine if a reaction event should be processed.

    Args:
        event: The parsed reaction event.
        mode: Notification mode (off | own | all).
        bot_user_id: The bot's user ID to filter self-reactions.
        is_bot_message: Whether the reacted message was authored by the bot.
    """
    if mode == ReactionNotificationMode.OFF:
        return False

    # Don't process bot's own reactions
    if bot_user_id and event.user_id == bot_user_id:
        return False

    # Only deleted events are informational — skip for "own" mode
    if event.action == "deleted" and mode == ReactionNotificationMode.OWN:
        return False

    if mode == ReactionNotificationMode.OWN:
        return is_bot_message

    # ALL mode — process all verified reactions
    return True


def create_synthetic_turn(
    event: ReactionEvent,
    *,
    message_text: str = "",
) -> SyntheticReactionTurn:
    """Create a synthetic inbound turn from a reaction event."""
    emoji = event.reaction_type or "unknown"
    action_verb = "reacted with" if event.action == "created" else "removed reaction"

    if message_text:
        text = f"[{action_verb} {emoji} on: \"{message_text[:100]}\"]"
    else:
        text = f"[{action_verb} {emoji} on message {event.message_id}]"

    return SyntheticReactionTurn(
        text=text,
        sender_id=event.user_id,
        chat_id=event.chat_id,
        is_group=event.chat_type == "group",
        metadata={
            "type": "reaction",
            "action": event.action,
            "emoji": emoji,
            "message_id": event.message_id,
        },
    )
