"""Per-channel message normalization.

Transforms raw platform-specific inbound payloads into the unified
``InboundTurn`` dataclass, and normalizes outbound ``OutboundPayload``
into platform-specific wire format.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pyclaw.channels.plugin_sdk.adapters import InboundTurn

logger = logging.getLogger(__name__)


@dataclass
class NormalizeSpec:
    """Per-channel normalization rules."""

    text_field: str = "text"
    sender_field: str = "from"
    chat_field: str = "chat.id"
    message_id_field: str = "message_id"
    thread_field: str = ""
    group_indicator: str = ""
    mention_regex: str = ""
    html_to_markdown: bool = False
    strip_bot_mention: bool = True
    max_text_length: int = 0
    media_types: list[str] = field(default_factory=lambda: ["photo", "video", "audio", "file"])


CHANNEL_NORMALIZE: dict[str, NormalizeSpec] = {
    "telegram": NormalizeSpec(
        sender_field="from.id",
        chat_field="chat.id",
        thread_field="message_thread_id",
        group_indicator="group",
        mention_regex=r"@(\w+)",
        media_types=["photo", "video", "audio", "voice", "document", "sticker"],
    ),
    "discord": NormalizeSpec(
        text_field="content",
        sender_field="author.id",
        chat_field="channel_id",
        message_id_field="id",
        thread_field="thread.id",
        mention_regex=r"<@!?(\d+)>",
        media_types=["attachments", "embeds"],
    ),
    "slack": NormalizeSpec(
        sender_field="user",
        chat_field="channel",
        message_id_field="ts",
        thread_field="thread_ts",
        mention_regex=r"<@(\w+)>",
        html_to_markdown=True,
    ),
    "matrix": NormalizeSpec(
        text_field="body",
        sender_field="sender",
        chat_field="room_id",
        message_id_field="event_id",
        thread_field="m.relates_to.event_id",
        mention_regex=r"@(\S+:\S+)",
    ),
    "feishu": NormalizeSpec(
        text_field="content",
        sender_field="sender.sender_id.open_id",
        chat_field="chat_id",
        message_id_field="message_id",
        thread_field="root_id",
        mention_regex=r"@_user_\d+",
    ),
    "msteams": NormalizeSpec(
        text_field="text",
        sender_field="from.aadObjectId",
        chat_field="conversation.id",
        message_id_field="id",
        thread_field="conversation.id",
        mention_regex=r"<at>(.*?)</at>",
        html_to_markdown=True,
    ),
    "whatsapp": NormalizeSpec(
        text_field="body",
        sender_field="from",
        chat_field="from",
        message_id_field="id",
        media_types=["image", "video", "audio", "document"],
    ),
    "signal": NormalizeSpec(
        text_field="message",
        sender_field="source",
        chat_field="source",
        message_id_field="timestamp",
    ),
    "dingtalk": NormalizeSpec(
        text_field="text.content",
        sender_field="senderId",
        chat_field="conversationId",
        message_id_field="msgId",
        mention_regex=r"@(\w+)",
    ),
    "irc": NormalizeSpec(
        text_field="message",
        sender_field="nick",
        chat_field="channel",
        message_id_field="",
        mention_regex=r"(\w+):",
    ),
    "mattermost": NormalizeSpec(
        text_field="message",
        sender_field="user_id",
        chat_field="channel_id",
        message_id_field="id",
        thread_field="root_id",
        mention_regex=r"@(\w+)",
    ),
    "googlechat": NormalizeSpec(
        text_field="argumentText",
        sender_field="user.name",
        chat_field="space.name",
        message_id_field="name",
        thread_field="thread.name",
        mention_regex=r"<users/(\d+)>",
    ),
    "line": NormalizeSpec(
        text_field="text",
        sender_field="source.userId",
        chat_field="source.groupId",
        message_id_field="id",
        media_types=["image", "video", "audio", "file"],
    ),
    "qq": NormalizeSpec(
        text_field="content",
        sender_field="author.id",
        chat_field="channel_id",
        message_id_field="id",
        mention_regex=r"<@!?(\d+)>",
    ),
    "twitch": NormalizeSpec(
        text_field="message",
        sender_field="user-id",
        chat_field="room-id",
        message_id_field="id",
        mention_regex=r"@(\w+)",
    ),
    "nostr": NormalizeSpec(
        text_field="content",
        sender_field="pubkey",
        chat_field="id",
        message_id_field="id",
    ),
}

NormalizeMiddleware = Callable[[InboundTurn], InboundTurn]


def _resolve_nested(data: dict[str, Any], path: str) -> Any:
    """Resolve a dotted path like 'from.id' in a nested dict."""
    parts = path.split(".")
    current: Any = data
    for p in parts:
        if isinstance(current, dict):
            current = current.get(p)
        else:
            return None
    return current


def normalize_inbound(
    channel_type: str,
    raw: dict[str, Any],
    *,
    middleware: list[NormalizeMiddleware] | None = None,
) -> InboundTurn:
    """Normalize a raw platform event into a unified InboundTurn."""
    spec = CHANNEL_NORMALIZE.get(channel_type, NormalizeSpec())

    text = str(_resolve_nested(raw, spec.text_field) or "")
    sender_id = str(_resolve_nested(raw, spec.sender_field) or "")
    chat_id = str(_resolve_nested(raw, spec.chat_field) or "")
    message_id = (
        str(_resolve_nested(raw, spec.message_id_field) or "") if spec.message_id_field else ""
    )
    thread_id = str(_resolve_nested(raw, spec.thread_field) or "") if spec.thread_field else ""

    is_group = bool(
        spec.group_indicator and spec.group_indicator in str(raw.get("chat", {}).get("type", ""))
    )
    is_mention = bool(spec.mention_regex and re.search(spec.mention_regex, text))

    if spec.strip_bot_mention and spec.mention_regex and is_mention:
        text = re.sub(spec.mention_regex, "", text).strip()

    media: list[dict[str, Any]] = []
    for mtype in spec.media_types:
        if mtype in raw and raw[mtype]:
            media.append({"type": mtype, "data": raw[mtype]})

    turn = InboundTurn(
        text=text,
        sender_id=sender_id,
        chat_id=chat_id,
        message_id=message_id,
        thread_id=thread_id,
        is_group=is_group,
        is_mention=is_mention,
        media=media,
        metadata={"channel_type": channel_type, "raw_keys": list(raw.keys())},
    )

    for mw in middleware or []:
        turn = mw(turn)

    return turn


def get_normalize_spec(channel_type: str) -> NormalizeSpec:
    return CHANNEL_NORMALIZE.get(channel_type, NormalizeSpec())
