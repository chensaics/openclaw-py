"""Hook system types."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class HookEventType(str, Enum):
    COMMAND = "command"
    SESSION = "session"
    AGENT = "agent"
    GATEWAY = "gateway"
    MESSAGE = "message"
    CHANNEL = "channel"


@dataclass
class HookEvent:
    """Payload passed to hook handlers."""

    type: HookEventType
    action: str
    session_key: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    messages: list[dict[str, Any]] = field(default_factory=list)
    channel_id: str = ""
    trigger: str = ""
    agent_id: str = ""


class HookHandler(Protocol):
    """A callable that processes a HookEvent — sync or async."""

    def __call__(self, event: HookEvent) -> Awaitable[None] | None: ...


@dataclass
class HookEntryMeta:
    """Metadata parsed from HOOK.md frontmatter."""

    name: str = ""
    events: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    description: str = ""
    module: str = ""


@dataclass
class HookEntry:
    """A loaded hook with its metadata and handler."""

    meta: HookEntryMeta
    handler: HookHandler | None = None
