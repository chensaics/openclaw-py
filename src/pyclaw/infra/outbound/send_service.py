"""Outbound send service — unified sending, envelope/identity, conversation-id.

Ported from ``src/infra/outbound/outbound-send-service.ts``.

Provides:
- Unified send interface for all channels
- Message envelope with identity and conversation tracking
- Conversation ID management
- Format selection (markdown/html/plain)
- Send result tracking
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class MessageFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN = "plain"


@dataclass
class SenderIdentity:
    """Identity of the message sender (bot/agent)."""
    name: str = ""
    avatar_url: str = ""
    agent_id: str = ""
    prefix: str = ""


@dataclass
class MessageEnvelope:
    """Envelope wrapping a message for delivery."""
    conversation_id: str
    text: str
    format: MessageFormat = MessageFormat.MARKDOWN
    identity: SenderIdentity = field(default_factory=SenderIdentity)
    reply_to: str = ""
    thread_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class SendResult:
    """Result of sending a message."""
    success: bool
    message_id: str = ""
    channel_id: str = ""
    error: str = ""
    sent_at: float = 0.0
    format_used: MessageFormat = MessageFormat.MARKDOWN

    def __post_init__(self) -> None:
        if self.sent_at == 0.0 and self.success:
            self.sent_at = time.time()


ChannelSender = Callable[[str, str, MessageEnvelope], Coroutine[Any, Any, SendResult]]


def generate_conversation_id(channel_id: str, chat_id: str) -> str:
    """Generate a deterministic conversation ID."""
    return f"{channel_id}:{chat_id}"


def generate_message_id() -> str:
    return str(uuid.uuid4())[:12]


class OutboundSendService:
    """Unified message sending service."""

    def __init__(self) -> None:
        self._senders: dict[str, ChannelSender] = {}
        self._send_count = 0
        self._error_count = 0

    def register_sender(self, channel_type: str, sender: ChannelSender) -> None:
        self._senders[channel_type] = sender

    async def send(
        self,
        channel_type: str,
        chat_id: str,
        envelope: MessageEnvelope,
    ) -> SendResult:
        """Send a message through the appropriate channel."""
        sender = self._senders.get(channel_type)
        if not sender:
            self._error_count += 1
            return SendResult(
                success=False,
                error=f"No sender registered for channel type: {channel_type}",
            )

        try:
            result = await sender(channel_type, chat_id, envelope)
            if result.success:
                self._send_count += 1
            else:
                self._error_count += 1
            return result
        except Exception as e:
            self._error_count += 1
            logger.error("Send error for %s: %s", channel_type, e)
            return SendResult(success=False, error=str(e))

    async def send_with_fallback(
        self,
        channel_type: str,
        chat_id: str,
        envelope: MessageEnvelope,
        *,
        fallback_formats: list[MessageFormat] | None = None,
    ) -> SendResult:
        """Send with format fallback (markdown -> html -> plain)."""
        result = await self.send(channel_type, chat_id, envelope)
        if result.success:
            return result

        formats = fallback_formats or [MessageFormat.HTML, MessageFormat.PLAIN]
        for fmt in formats:
            if fmt == envelope.format:
                continue
            envelope.format = fmt
            result = await self.send(channel_type, chat_id, envelope)
            if result.success:
                result.format_used = fmt
                return result

        return result

    @property
    def send_count(self) -> int:
        return self._send_count

    @property
    def error_count(self) -> int:
        return self._error_count
