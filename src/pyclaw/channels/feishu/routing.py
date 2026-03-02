"""Feishu advanced routing — group session scopes and reply-in-thread.

Ported from ``extensions/feishu/src/session.ts`` and related files.

Supports:
- Group session scopes: ``group``, ``group_sender``, ``group_topic``, ``group_topic_sender``
- ``replyInThread`` configuration for group replies
- ``groupSenderAllowFrom`` for sender-level group access control
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class GroupSessionScope(str, Enum):
    GROUP = "group"
    GROUP_SENDER = "group_sender"
    GROUP_TOPIC = "group_topic"
    GROUP_TOPIC_SENDER = "group_topic_sender"


class ReplyInThread(str, Enum):
    DISABLED = "disabled"
    ENABLED = "enabled"


@dataclass
class FeishuRoutingConfig:
    """Routing configuration for Feishu channel."""

    group_session_scope: GroupSessionScope = GroupSessionScope.GROUP
    reply_in_thread: ReplyInThread = ReplyInThread.DISABLED
    group_sender_allow_from: list[str] | None = None
    # Per-group overrides
    groups: dict[str, dict[str, Any]] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeishuRoutingConfig:
        return cls(
            group_session_scope=GroupSessionScope(data.get("groupSessionScope", "group")),
            reply_in_thread=ReplyInThread(data.get("replyInThread", "disabled")),
            group_sender_allow_from=data.get("groupSenderAllowFrom"),
            groups=data.get("groups"),
        )


def resolve_feishu_session_key(
    *,
    chat_id: str,
    sender_id: str = "",
    root_id: str = "",
    chat_type: str = "",
    config: FeishuRoutingConfig | None = None,
    account_id: str = "default",
) -> str:
    """Resolve the session key for a Feishu message.

    DM sessions use ``feishu:<account>:dm:<sender>``.
    Group sessions depend on the configured scope.
    """
    cfg = config or FeishuRoutingConfig()
    prefix = f"feishu:{account_id}"

    if chat_type != "group":
        return f"{prefix}:dm:{sender_id or chat_id}"

    scope = cfg.group_session_scope
    topic = root_id or ""

    if scope == GroupSessionScope.GROUP:
        return f"{prefix}:group:{chat_id}"
    elif scope == GroupSessionScope.GROUP_SENDER:
        return f"{prefix}:group:{chat_id}:sender:{sender_id}"
    elif scope == GroupSessionScope.GROUP_TOPIC:
        if topic:
            return f"{prefix}:group:{chat_id}:topic:{topic}"
        return f"{prefix}:group:{chat_id}"
    elif scope == GroupSessionScope.GROUP_TOPIC_SENDER:
        parts = [f"{prefix}:group:{chat_id}"]
        if topic:
            parts.append(f"topic:{topic}")
        parts.append(f"sender:{sender_id}")
        return ":".join(parts)

    return f"{prefix}:group:{chat_id}"


def is_sender_allowed_in_group(
    sender_id: str,
    group_id: str,
    config: FeishuRoutingConfig,
) -> bool:
    """Check if a sender is allowed in a group chat.

    Priority: per-group allowFrom > global groupSenderAllowFrom > allow all.
    """
    # Per-group override
    if config.groups:
        group_config = config.groups.get(group_id, {})
        group_allow = group_config.get("allowFrom")
        if group_allow is not None:
            return sender_id in group_allow

    # Global sender allowlist
    if config.group_sender_allow_from is not None:
        return sender_id in config.group_sender_allow_from

    # No restriction
    return True


def resolve_reply_params(
    *,
    chat_id: str,
    root_id: str = "",
    message_id: str = "",
    config: FeishuRoutingConfig | None = None,
) -> dict[str, Any]:
    """Resolve reply parameters for outbound Feishu messages.

    When ``replyInThread`` is enabled for groups, set ``reply_in_thread``
    and propagate ``root_id`` so replies stay in the thread.
    """
    cfg = config or FeishuRoutingConfig()
    params: dict[str, Any] = {"chat_id": chat_id}

    if cfg.reply_in_thread == ReplyInThread.ENABLED and root_id:
        params["reply_in_thread"] = True
        params["root_id"] = root_id

    if message_id:
        params["message_id"] = message_id

    return params
