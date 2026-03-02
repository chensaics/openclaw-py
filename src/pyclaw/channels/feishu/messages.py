"""Feishu message parsing — merge_forward, rich-text, media type mapping.

Ported from ``extensions/feishu/src/inbound.ts`` and related files.

Handles:
- ``merge_forward`` message expansion
- Rich-text parsing (code/code_block/pre, share_chat)
- Media type mapping (opus → audio, video → media, image → image)
- Inbound message metadata (message_id line)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ParsedFeishuMessage:
    """A parsed Feishu inbound message with extracted content."""

    text: str
    message_id: str = ""
    message_type: str = ""
    chat_id: str = ""
    chat_type: str = ""
    sender_id: str = ""
    sender_name: str = ""
    root_id: str = ""
    media_keys: list[str] = field(default_factory=list)
    media_type: str = ""  # "image" | "audio" | "file" | "video"
    is_merge_forward: bool = False
    raw: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Media type mapping
# ---------------------------------------------------------------------------


def resolve_media_type(message_type: str, *, filename: str = "") -> str:
    """Map Feishu message_type to a normalized media type.

    Feishu quirks:
    - opus files should be msg_type "audio" (not "media")
    - mobile video shows as message_type "media" → treat as video
    - documents are msg_type "file"
    """
    mt = message_type.lower()

    if mt == "image":
        return "image"
    if mt == "audio":
        return "audio"
    if mt == "file":
        return "file"
    if mt == "media":
        return "video"
    if mt == "sticker":
        return "image"

    return "file"


def resolve_send_msg_type(filename: str) -> str:
    """Resolve the correct msg_type for outbound sends based on file extension."""
    lower = filename.lower()

    if lower.endswith(".opus") or lower.endswith(".ogg"):
        return "audio"
    if lower.endswith(".mp4") or lower.endswith(".mov") or lower.endswith(".avi"):
        return "media"
    if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
        return "image"

    return "file"


# ---------------------------------------------------------------------------
# Rich-text parsing
# ---------------------------------------------------------------------------


def parse_rich_text(content: dict[str, Any]) -> str:
    """Parse Feishu rich-text (post) content into plain text.

    Handles:
    - Text runs (text, a, at)
    - Code blocks (code_block, pre)
    - Inline code
    - share_chat with summary
    """
    lines: list[str] = []

    post = content.get("post", content)
    # The post might be wrapped in a locale key
    if isinstance(post, dict):
        for locale_key in ["zh_cn", "en_us", "ja_jp", ""]:
            if locale_key in post:
                post = post[locale_key]
                break

    title = ""
    if isinstance(post, dict):
        title = post.get("title", "")
        content_list = post.get("content", [])
    elif isinstance(post, list):
        content_list = post
    else:
        return str(post)

    if title:
        lines.append(f"**{title}**")

    for paragraph in content_list:
        if not isinstance(paragraph, list):
            continue
        parts: list[str] = []
        for element in paragraph:
            tag = element.get("tag", "")
            if tag == "text":
                parts.append(element.get("text", ""))
            elif tag == "a":
                text = element.get("text", "")
                href = element.get("href", "")
                parts.append(f"[{text}]({href})" if href else text)
            elif tag == "at":
                parts.append(f"@{element.get('user_name', element.get('user_id', ''))}")
            elif tag == "code":
                parts.append(f"`{element.get('text', '')}`")
            elif tag in ("code_block", "pre"):
                lang = element.get("language", "")
                code = element.get("text", "")
                parts.append(f"\n```{lang}\n{code}\n```\n")
            elif tag == "img":
                parts.append("[image]")
            elif tag == "media":
                parts.append("[media]")

        lines.append("".join(parts))

    return "\n".join(lines)


def parse_share_chat(content: dict[str, Any]) -> str:
    """Parse a share_chat message content."""
    chat_id = content.get("chat_id", "")
    # summary is sometimes available in newer API versions
    summary = content.get("summary", "")
    if summary:
        return f"[Shared chat: {summary}]"
    return f"[Shared chat: {chat_id}]"


# ---------------------------------------------------------------------------
# Merge forward parsing
# ---------------------------------------------------------------------------


def parse_merge_forward(content: dict[str, Any]) -> str:
    """Parse a merge_forward message by expanding sub-messages.

    Merge forwards contain a list of forwarded messages that should
    be formatted in order for the agent.
    """
    messages = content.get("messages", [])
    if not messages:
        return "[Merged forward message (empty)]"

    parts: list[str] = ["[Merged forward messages:]"]
    for i, msg in enumerate(messages, 1):
        sender = msg.get("sender_name", msg.get("sender_id", f"User {i}"))
        msg_type = msg.get("message_type", "text")
        msg_content = msg.get("content", {})

        if isinstance(msg_content, str):
            try:
                msg_content = json.loads(msg_content)
            except json.JSONDecodeError:
                msg_content = {"text": msg_content}

        if msg_type == "text":
            text = msg_content.get("text", "")
        elif msg_type == "post":
            text = parse_rich_text(msg_content)
        elif msg_type == "share_chat":
            text = parse_share_chat(msg_content)
        else:
            text = f"[{msg_type}]"

        parts.append(f"  {sender}: {text}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Full message parsing
# ---------------------------------------------------------------------------


def parse_feishu_message(body: dict[str, Any]) -> ParsedFeishuMessage:
    """Parse a full Feishu webhook event into a structured message."""
    event = body.get("event", {})
    message = event.get("message", {})

    message_id = message.get("message_id", "")
    message_type = message.get("message_type", "text")
    chat_id = message.get("chat_id", "")
    chat_type = message.get("chat_type", "")
    root_id = message.get("root_id", "") or message.get("parent_id", "")

    sender = event.get("sender", {})
    sender_id_obj = sender.get("sender_id", {})
    sender_id = sender_id_obj.get("open_id", "") or sender_id_obj.get("user_id", "")
    sender_name = sender_id_obj.get("name", "")

    raw_content = message.get("content", "{}")
    try:
        content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
    except json.JSONDecodeError:
        content = {"text": raw_content}

    # Parse based on message type
    text = ""
    media_keys: list[str] = []
    media_type = ""
    is_merge_forward = False

    if message_type == "text":
        text = content.get("text", "")
    elif message_type == "post":
        text = parse_rich_text(content)
    elif message_type == "share_chat":
        text = parse_share_chat(content)
    elif message_type == "merge_forward":
        text = parse_merge_forward(content)
        is_merge_forward = True
    elif message_type in ("image", "audio", "media", "file", "sticker"):
        media_type = resolve_media_type(message_type)
        image_key = content.get("image_key", "")
        file_key = content.get("file_key", "")
        if image_key:
            media_keys.append(image_key)
        if file_key:
            media_keys.append(file_key)
        text = f"[{media_type}]"
    else:
        text = f"[{message_type} message]"

    # Append message_id metadata line
    if message_id:
        text = f"{text}\n[message_id: {message_id}]"

    return ParsedFeishuMessage(
        text=text.strip(),
        message_id=message_id,
        message_type=message_type,
        chat_id=chat_id,
        chat_type=chat_type,
        sender_id=sender_id,
        sender_name=sender_name,
        root_id=root_id,
        media_keys=media_keys,
        media_type=media_type,
        is_merge_forward=is_merge_forward,
        raw=body,
    )
