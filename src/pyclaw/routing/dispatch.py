"""Message dispatch pipeline — context building, reply scheduling, and command parsing.

Ported from ``src/auto-reply/dispatch.ts`` and ``src/auto-reply/reply/``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from pyclaw.channels.base import ChannelMessage, ChannelReply
from pyclaw.routing.session_key import build_peer_session_key, normalize_agent_id


# ---------------------------------------------------------------------------
# Slash command parsing
# ---------------------------------------------------------------------------

@dataclass
class ParsedCommand:
    """A parsed slash command from user input."""
    name: str
    args: list[str]
    raw: str


_COMMAND_RE = re.compile(r"^/(\w+)(?:\s+(.*))?$", re.DOTALL)

KNOWN_COMMANDS = frozenset({
    "compact", "reset", "model", "status", "help",
    "new", "history", "export", "memory", "remind",
    "verbose", "quiet", "thinking",
})


def parse_command(text: str) -> ParsedCommand | None:
    """Parse a slash command from message text.

    Returns None if the text is not a command.
    """
    text = text.strip()
    m = _COMMAND_RE.match(text)
    if not m:
        return None
    name = m.group(1).lower()
    if name not in KNOWN_COMMANDS:
        return None
    args_str = m.group(2) or ""
    args = args_str.split() if args_str.strip() else []
    return ParsedCommand(name=name, args=args, raw=text)


# ---------------------------------------------------------------------------
# Message context builder
# ---------------------------------------------------------------------------

@dataclass
class MessageContext:
    """Enriched inbound message context for dispatch."""
    message: ChannelMessage
    agent_id: str = "main"
    session_key: str = ""
    is_owner: bool = False
    is_allowed: bool = False
    command: ParsedCommand | None = None
    received_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.session_key:
            self.session_key = build_peer_session_key(
                agent_id=self.agent_id,
                channel=self.message.channel,
                peer_id=self.message.sender_id,
            )
        self.command = parse_command(self.message.text)


def build_message_context(
    msg: ChannelMessage,
    *,
    agent_id: str = "main",
    owner_ids: set[str] | None = None,
    allowed_ids: set[str] | None = None,
) -> MessageContext:
    """Build a ``MessageContext`` from a raw channel message."""
    sender = msg.sender_id
    is_owner = sender in (owner_ids or set())
    is_allowed = is_owner or sender in (allowed_ids or set())

    return MessageContext(
        message=msg,
        agent_id=normalize_agent_id(agent_id),
        is_owner=is_owner,
        is_allowed=is_allowed,
    )


# ---------------------------------------------------------------------------
# Reply dispatcher
# ---------------------------------------------------------------------------

ReplyHandler = Callable[[MessageContext], Coroutine[Any, Any, str | None]]
CommandHandler = Callable[[MessageContext, ParsedCommand], Coroutine[Any, Any, str | None]]


class MessageDispatcher:
    """Routes inbound messages to agent or command handlers.

    Flow:
    1. Build context (session key, owner/allow check, command parse)
    2. If slash command, route to command handler
    3. Otherwise, route to reply handler (agent)
    4. Send reply back through the channel
    """

    def __init__(
        self,
        *,
        reply_handler: ReplyHandler | None = None,
        command_handlers: dict[str, CommandHandler] | None = None,
        owner_ids: set[str] | None = None,
        allowed_ids: set[str] | None = None,
        agent_id: str = "main",
    ) -> None:
        self._reply_handler = reply_handler
        self._command_handlers = command_handlers or {}
        self._owner_ids = owner_ids or set()
        self._allowed_ids = allowed_ids or set()
        self._agent_id = agent_id
        self._active_dispatches: dict[str, float] = {}

    async def dispatch(
        self,
        msg: ChannelMessage,
        *,
        send_reply: Callable[[ChannelReply], Coroutine[Any, Any, None]] | None = None,
    ) -> str | None:
        """Dispatch an inbound message. Returns the reply text or None."""
        ctx = build_message_context(
            msg,
            agent_id=self._agent_id,
            owner_ids=self._owner_ids,
            allowed_ids=self._allowed_ids,
        )

        if not ctx.is_allowed:
            return None

        # Reserve — prevent concurrent dispatch for same session
        if ctx.session_key in self._active_dispatches:
            return None
        self._active_dispatches[ctx.session_key] = time.time()

        try:
            reply_text: str | None = None

            if ctx.command:
                handler = self._command_handlers.get(ctx.command.name)
                if handler:
                    reply_text = await handler(ctx, ctx.command)
                elif self._reply_handler:
                    reply_text = await self._reply_handler(ctx)
            elif self._reply_handler:
                reply_text = await self._reply_handler(ctx)

            if reply_text and send_reply:
                reply = ChannelReply(
                    channel=msg.channel,
                    recipient_id=msg.sender_id,
                    text=reply_text,
                    reply_to_message_id=msg.message_id,
                )
                await send_reply(reply)

            return reply_text
        finally:
            self._active_dispatches.pop(ctx.session_key, None)

    @property
    def active_count(self) -> int:
        return len(self._active_dispatches)


# ---------------------------------------------------------------------------
# Built-in command handlers
# ---------------------------------------------------------------------------

async def handle_help(ctx: MessageContext, cmd: ParsedCommand) -> str:
    """Handle /help command."""
    lines = ["Available commands:"]
    for name in sorted(KNOWN_COMMANDS):
        lines.append(f"  /{name}")
    return "\n".join(lines)


async def handle_status(ctx: MessageContext, cmd: ParsedCommand) -> str:
    """Handle /status command."""
    return (
        f"Agent: {ctx.agent_id}\n"
        f"Session: {ctx.session_key}\n"
        f"Channel: {ctx.message.channel}\n"
        f"Owner: {ctx.is_owner}"
    )


def create_default_command_handlers() -> dict[str, CommandHandler]:
    """Create the default set of slash command handlers."""
    return {
        "help": handle_help,
        "status": handle_status,
    }
