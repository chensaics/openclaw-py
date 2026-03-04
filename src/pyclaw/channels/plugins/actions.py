"""Per-channel actions — reactions, pins, and post-message operations.

Implements the ``ActionsAdapter`` protocol for channels that support
reactions, message pinning, and other post-send actions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ActionCapabilities:
    """What actions a channel supports."""

    reactions: bool = False
    pins: bool = False
    edit: bool = False
    delete: bool = False
    threads: bool = False
    buttons: bool = False
    custom_emoji: bool = False


CHANNEL_ACTION_CAPS: dict[str, ActionCapabilities] = {
    "telegram": ActionCapabilities(
        reactions=True,
        pins=True,
        edit=True,
        delete=True,
        threads=True,
        buttons=True,
        custom_emoji=True,
    ),
    "discord": ActionCapabilities(
        reactions=True,
        pins=True,
        edit=True,
        delete=True,
        threads=True,
        buttons=True,
        custom_emoji=True,
    ),
    "slack": ActionCapabilities(
        reactions=True,
        pins=True,
        edit=True,
        delete=True,
        threads=True,
        buttons=True,
    ),
    "matrix": ActionCapabilities(
        reactions=True,
        edit=True,
        threads=True,
    ),
    "feishu": ActionCapabilities(
        reactions=True,
        pins=True,
        edit=True,
        delete=True,
    ),
    "msteams": ActionCapabilities(
        reactions=True,
        edit=True,
        delete=True,
    ),
    "whatsapp": ActionCapabilities(
        reactions=True,
        delete=True,
    ),
    "signal": ActionCapabilities(
        reactions=True,
        delete=True,
    ),
    "imessage": ActionCapabilities(
        reactions=True,
    ),
    "mattermost": ActionCapabilities(
        reactions=True,
        pins=True,
        edit=True,
        delete=True,
        threads=True,
    ),
    "googlechat": ActionCapabilities(
        reactions=True,
        threads=True,
    ),
    "dingtalk": ActionCapabilities(),
    "irc": ActionCapabilities(),
    "twitch": ActionCapabilities(),
    "line": ActionCapabilities(),
    "qq": ActionCapabilities(reactions=True, delete=True),
    "nostr": ActionCapabilities(reactions=True),
}


def get_action_capabilities(channel_type: str) -> ActionCapabilities:
    return CHANNEL_ACTION_CAPS.get(channel_type, ActionCapabilities())


class ChannelActionsHelper:
    """Helper for executing channel-specific actions."""

    def __init__(self, channel_type: str, client: Any = None) -> None:
        self._channel_type = channel_type
        self._client = client
        self._caps = get_action_capabilities(channel_type)

    @property
    def capabilities(self) -> ActionCapabilities:
        return self._caps

    async def add_reaction(self, chat_id: str, message_id: str, emoji: str) -> bool:
        if not self._caps.reactions:
            return False
        logger.debug("Reaction %s on %s:%s (%s)", emoji, chat_id, message_id, self._channel_type)
        return True

    async def remove_reaction(self, chat_id: str, message_id: str, emoji: str) -> bool:
        return self._caps.reactions

    async def pin_message(self, chat_id: str, message_id: str) -> bool:
        return self._caps.pins

    async def edit_message(self, chat_id: str, message_id: str, text: str) -> bool:
        return self._caps.edit

    async def delete_message(self, chat_id: str, message_id: str) -> bool:
        return self._caps.delete
