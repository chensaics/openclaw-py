"""Interrupt system — cancel/append dual-mode interruption for agent runs.

Allows users to interrupt a running agent in two ways:

- **cancel**: Immediately stop the current LLM generation and restart.
- **append**: Keep the current generation running but inject additional
  context into the next turn.

Works in concert with :mod:`pyclaw.agents.intent` (intent classification)
and :mod:`pyclaw.gateway.message_bus` (session-level message peek).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class InterruptMode(str, Enum):
    CANCEL = "cancel"
    APPEND = "append"


@dataclass
class InterruptRequest:
    """A single interrupt request from a user."""

    message: str
    mode: InterruptMode
    timestamp: float = 0.0


class InterruptibleContext:
    """Context wrapper that supports cancel and append interruptions.

    Create one per agent run.  The runner should periodically call
    :meth:`check_interrupts` (typically every ~500 ms or between tool
    calls) and react accordingly.
    """

    def __init__(self) -> None:
        self._cancel_event = asyncio.Event()
        self._append_queue: asyncio.Queue[str] = asyncio.Queue()
        self._interrupt_log: list[InterruptRequest] = []

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def request_cancel(self, message: str = "") -> None:
        """Request a cancel-mode interruption."""
        import time

        req = InterruptRequest(message=message, mode=InterruptMode.CANCEL, timestamp=time.time())
        self._interrupt_log.append(req)
        self._cancel_event.set()
        logger.info("Interrupt: cancel requested")

    def request_append(self, message: str) -> None:
        """Request an append-mode interruption (additional context)."""
        import time

        req = InterruptRequest(message=message, mode=InterruptMode.APPEND, timestamp=time.time())
        self._interrupt_log.append(req)
        self._append_queue.put_nowait(message)
        logger.info("Interrupt: append requested")

    def drain_appended(self) -> list[str]:
        """Drain all pending appended messages (non-blocking)."""
        messages: list[str] = []
        while True:
            try:
                messages.append(self._append_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return messages

    @property
    def has_appended(self) -> bool:
        return not self._append_queue.empty()

    @property
    def history(self) -> list[InterruptRequest]:
        return list(self._interrupt_log)


async def check_incoming_messages(
    session_key: str,
    ictx: InterruptibleContext,
    *,
    poll_interval: float = 0.5,
) -> None:
    """Background task that polls the message bus for new messages
    directed at ``session_key`` and dispatches them as interrupts.

    Runs until the interrupt context is cancelled or the caller cancels
    this coroutine.
    """
    from pyclaw.agents.intent import IntentAnalyzer, UserIntent
    from pyclaw.gateway.message_bus import get_message_bus

    analyzer = IntentAnalyzer()
    bus = get_message_bus()

    while not ictx.is_cancelled:
        msg = bus.peek_inbound_for_session(session_key)
        if msg:
            result = analyzer.analyze(msg.content, is_agent_running=True)
            if result.intent == UserIntent.STOP or result.is_interrupt:
                ictx.request_cancel(msg.content)
            else:
                ictx.request_append(msg.content)

        await asyncio.sleep(poll_interval)
