"""Message queue — steer/interrupt/followup/collect modes with debounce.

Ported from ``src/auto-reply/reply/queue/`` in the TypeScript codebase.

Provides:
- Queue modes: steer, interrupt, followup, collect
- Debounce to batch rapid messages
- Queue cap and drop policy
- Enqueue/dequeue with normalization
- Queue lifecycle and cleanup
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class QueueMode(str, Enum):
    """How queued messages interact with an in-progress agent run."""

    STEER = "steer"  # Inject into current run
    INTERRUPT = "interrupt"  # Abort current run, start new
    FOLLOWUP = "followup"  # Wait for current run, then process
    COLLECT = "collect"  # Batch messages, process together


class DropPolicy(str, Enum):
    """What to do when queue is at capacity."""

    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    REJECT = "reject"


@dataclass
class QueueSettings:
    """Configuration for the message queue."""

    mode: QueueMode = QueueMode.FOLLOWUP
    max_size: int = 50
    drop_policy: DropPolicy = DropPolicy.DROP_OLDEST
    debounce_ms: int = 500
    collect_window_ms: int = 2000


@dataclass
class QueuedMessage:
    """A message waiting in the queue."""

    text: str
    sender_id: str = ""
    channel_id: str = ""
    session_id: str = ""
    enqueued_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.enqueued_at == 0.0:
            self.enqueued_at = time.time()


@dataclass
class DrainResult:
    """Result of draining the queue."""

    messages: list[QueuedMessage]
    mode: QueueMode
    dropped_count: int = 0


class MessageQueue:
    """Async message queue with modes, debounce, and capacity management."""

    def __init__(self, settings: QueueSettings | None = None) -> None:
        self._settings = settings or QueueSettings()
        self._queue: list[QueuedMessage] = []
        self._debounce_task: asyncio.Task[None] | None = None
        self._drain_event = asyncio.Event()
        self._running = False
        self._dropped_total = 0

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    @property
    def mode(self) -> QueueMode:
        return self._settings.mode

    @property
    def dropped_total(self) -> int:
        return self._dropped_total

    def enqueue(self, message: QueuedMessage) -> bool:
        """Add a message to the queue. Returns False if rejected."""
        if len(self._queue) >= self._settings.max_size:
            if self._settings.drop_policy == DropPolicy.REJECT:
                logger.debug("Queue full, rejecting message")
                return False
            if self._settings.drop_policy == DropPolicy.DROP_OLDEST:
                self._queue.pop(0)
                self._dropped_total += 1
            elif self._settings.drop_policy == DropPolicy.DROP_NEWEST:
                self._dropped_total += 1
                return False

        self._queue.append(message)
        self._drain_event.set()
        return True

    def drain(self) -> DrainResult:
        """Drain all messages from the queue."""
        messages = list(self._queue)
        dropped = self._dropped_total
        self._queue.clear()
        self._dropped_total = 0
        self._drain_event.clear()

        return DrainResult(
            messages=messages,
            mode=self._settings.mode,
            dropped_count=dropped,
        )

    def drain_for_steer(self) -> DrainResult:
        """Drain messages suitable for steering (latest message only for steer mode)."""
        if self._settings.mode == QueueMode.STEER and self._queue:
            msg = self._queue[-1]
            dropped = len(self._queue) - 1 + self._dropped_total
            self._queue.clear()
            self._dropped_total = 0
            self._drain_event.clear()
            return DrainResult(messages=[msg], mode=QueueMode.STEER, dropped_count=dropped)

        return self.drain()

    def peek(self) -> QueuedMessage | None:
        return self._queue[0] if self._queue else None

    def clear(self) -> int:
        """Clear the queue, return number of dropped messages."""
        count = len(self._queue)
        self._queue.clear()
        self._drain_event.clear()
        return count

    async def wait_for_messages(self, *, timeout: float | None = None) -> bool:
        """Wait until messages are available. Returns False on timeout."""
        if self._queue:
            return True
        try:
            await asyncio.wait_for(self._drain_event.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    def normalize(self) -> None:
        """Normalize queued messages (deduplicate exact duplicates within window)."""
        if len(self._queue) < 2:
            return

        seen: set[str] = set()
        unique: list[QueuedMessage] = []
        for msg in self._queue:
            key = f"{msg.sender_id}:{msg.text}"
            if key not in seen:
                seen.add(key)
                unique.append(msg)

        removed = len(self._queue) - len(unique)
        if removed > 0:
            self._queue = unique
            logger.debug("Normalized queue: removed %d duplicates", removed)

    def update_settings(self, settings: QueueSettings) -> None:
        self._settings = settings
