"""Message bus — async dual-channel message routing with session-level peek.

Provides an inbound/outbound message bus that decouples channels from the
agent runtime.  The key feature is ``peek_inbound_for_session()`` which
allows the interrupt system to non-blocking check for new messages targeted
at a specific session without consuming messages for other sessions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InboundMessage:
    """A message arriving from a channel towards the agent."""

    channel: str
    sender_id: str
    chat_id: str
    content: str
    session_key: str = ""
    media: list[dict[str, Any]] = field(default_factory=list)
    selected_skills: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundMessage:
    """A message going from the agent out to a channel."""

    channel: str
    chat_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageBus:
    """Async dual-channel message bus with session-level peek.

    Inbound: channel → agent (user messages)
    Outbound: agent → channel (replies, notifications)
    """

    def __init__(self, *, buffer_size: int = 256) -> None:
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=buffer_size)
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=buffer_size)
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    # ---- Publish ----

    def publish_inbound(self, msg: InboundMessage) -> bool:
        """Publish a message to the inbound queue.  Returns False if full."""
        if self._closed:
            return False
        try:
            self._inbound.put_nowait(msg)
            return True
        except asyncio.QueueFull:
            logger.warning("Inbound buffer full, dropping message from %s", msg.sender_id)
            return False

    def publish_outbound(self, msg: OutboundMessage) -> bool:
        """Publish a message to the outbound queue.  Returns False if full."""
        if self._closed:
            return False
        try:
            self._outbound.put_nowait(msg)
            return True
        except asyncio.QueueFull:
            logger.warning("Outbound buffer full, dropping message for %s", msg.chat_id)
            return False

    # ---- Consume ----

    async def consume_inbound(self) -> InboundMessage:
        """Block until an inbound message is available."""
        return await self._inbound.get()

    def try_consume_inbound(self) -> InboundMessage | None:
        """Non-blocking consume from the inbound queue."""
        try:
            return self._inbound.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def consume_outbound(self) -> OutboundMessage:
        """Block until an outbound message is available."""
        return await self._outbound.get()

    # ---- Session Peek (for interrupt system) ----

    def peek_inbound_for_session(self, session_key: str) -> InboundMessage | None:
        """Non-blocking peek for the next inbound message matching ``session_key``.

        Messages not matching are put back into the queue.  This is the
        core mechanism enabling the interrupt system to detect new user
        messages for a running session without blocking other sessions.
        """
        others: list[InboundMessage] = []
        found: InboundMessage | None = None

        while True:
            try:
                msg = self._inbound.get_nowait()
            except asyncio.QueueEmpty:
                break

            if found is None and msg.session_key == session_key:
                found = msg
            else:
                others.append(msg)

        for msg in others:
            try:
                self._inbound.put_nowait(msg)
            except asyncio.QueueFull:
                logger.warning("Lost message during peek put-back: %s", msg.sender_id)

        return found

    # ---- Info ----

    @property
    def inbound_size(self) -> int:
        return self._inbound.qsize()

    @property
    def outbound_size(self) -> int:
        return self._outbound.qsize()


_global_bus: MessageBus | None = None


def get_message_bus() -> MessageBus:
    """Get or create the global MessageBus singleton."""
    global _global_bus
    if _global_bus is None or _global_bus.closed:
        _global_bus = MessageBus()
    return _global_bus
