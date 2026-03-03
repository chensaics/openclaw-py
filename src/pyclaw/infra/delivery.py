"""Delivery queue — async message delivery with retry, backoff, and recovery.

Ported from ``src/infra/delivery/`` in the TypeScript codebase.

Provides a persistent-friendly delivery queue with:
- Per-entry exponential backoff
- Recovery with ``lastAttemptAt`` deferred eligibility
- Priority-based ordering
- Lane-based draining for graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, cast

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY_S = 1.0
DEFAULT_MAX_DELAY_S = 60.0
DEFAULT_JITTER_FACTOR = 0.25
DEFAULT_QUEUE_SIZE = 1000


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEFERRED = "deferred"


class DeliveryPriority(int, Enum):
    HIGH = 0
    NORMAL = 1
    LOW = 2


@dataclass
class DeliveryEntry:
    """A single delivery queue entry."""

    id: str
    channel_id: str
    chat_id: str
    payload: dict[str, Any]
    status: DeliveryStatus = DeliveryStatus.PENDING
    priority: DeliveryPriority = DeliveryPriority.NORMAL
    attempts: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES
    created_at: float = 0.0
    last_attempt_at: float = 0.0
    next_eligible_at: float = 0.0
    error: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())[:12]
        if self.created_at == 0.0:
            self.created_at = time.time()


DeliveryCallback = Callable[[DeliveryEntry], Coroutine[Any, Any, bool]]


def compute_backoff(
    attempt: int,
    *,
    base_delay: float = DEFAULT_BASE_DELAY_S,
    max_delay: float = DEFAULT_MAX_DELAY_S,
    jitter_factor: float = DEFAULT_JITTER_FACTOR,
) -> float:
    """Compute exponential backoff delay with jitter."""
    import random

    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = delay * jitter_factor * (2 * random.random() - 1)
    return cast(float, max(0.1, delay + jitter))


class DeliveryQueue:
    """Async delivery queue with retry and backoff."""

    def __init__(
        self,
        callback: DeliveryCallback,
        *,
        max_size: int = DEFAULT_QUEUE_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY_S,
        max_delay: float = DEFAULT_MAX_DELAY_S,
    ) -> None:
        self._callback = callback
        self._max_size = max_size
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._entries: dict[str, DeliveryEntry] = {}
        self._queue: asyncio.PriorityQueue[tuple[int, float, str]] = asyncio.PriorityQueue(maxsize=max_size)
        self._worker_task: asyncio.Task[None] | None = None
        self._draining = False
        self._stopped = False

    async def enqueue(
        self,
        channel_id: str,
        chat_id: str,
        payload: dict[str, Any],
        *,
        priority: DeliveryPriority = DeliveryPriority.NORMAL,
    ) -> DeliveryEntry:
        """Add a delivery to the queue."""
        if self._draining:
            raise RuntimeError("Queue is draining, cannot accept new entries")

        entry = DeliveryEntry(
            id="",
            channel_id=channel_id,
            chat_id=chat_id,
            payload=payload,
            priority=priority,
            max_retries=self._max_retries,
        )
        self._entries[entry.id] = entry

        await self._queue.put((priority.value, entry.created_at, entry.id))
        return entry

    async def start(self) -> None:
        """Start the delivery worker."""
        if self._worker_task and not self._worker_task.done():
            return
        self._stopped = False
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self, *, drain: bool = True) -> None:
        """Stop the delivery worker.

        If drain=True, processes remaining entries before stopping.
        """
        self._stopped = True
        if drain:
            self._draining = True
            # Wait for queue to empty
            while not self._queue.empty():
                await asyncio.sleep(0.1)
            self._draining = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    def get_entry(self, entry_id: str) -> DeliveryEntry | None:
        return self._entries.get(entry_id)

    def get_pending_count(self) -> int:
        return sum(
            1 for e in self._entries.values()
            if e.status in (DeliveryStatus.PENDING, DeliveryStatus.DEFERRED)
        )

    def get_stats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for entry in self._entries.values():
            key = entry.status.value
            stats[key] = stats.get(key, 0) + 1
        return stats

    async def _worker_loop(self) -> None:
        """Main worker loop — processes entries from the queue."""
        try:
            while not self._stopped or not self._queue.empty():
                try:
                    _, _, entry_id = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Check deferred entries
                    await self._recover_deferred()
                    continue

                entry = self._entries.get(entry_id)
                if not entry:
                    continue

                # Check deferred eligibility
                now = time.time()
                if entry.next_eligible_at > now:
                    wait = entry.next_eligible_at - now
                    await asyncio.sleep(min(wait, 5.0))
                    if entry.next_eligible_at > time.time():
                        # Re-enqueue
                        await self._queue.put((entry.priority.value, entry.created_at, entry.id))
                        continue

                await self._attempt_delivery(entry)

        except asyncio.CancelledError:
            pass

    async def _attempt_delivery(self, entry: DeliveryEntry) -> None:
        """Attempt to deliver a single entry."""
        entry.status = DeliveryStatus.IN_FLIGHT
        entry.attempts += 1
        entry.last_attempt_at = time.time()

        try:
            success = await self._callback(entry)
            if success:
                entry.status = DeliveryStatus.DELIVERED
                logger.debug("Delivered %s to %s:%s", entry.id, entry.channel_id, entry.chat_id)
            else:
                await self._handle_failure(entry, "delivery returned false")
        except Exception as exc:
            await self._handle_failure(entry, str(exc))

    async def _handle_failure(self, entry: DeliveryEntry, error: str) -> None:
        """Handle a delivery failure with backoff."""
        entry.error = error

        if entry.attempts >= entry.max_retries:
            entry.status = DeliveryStatus.FAILED
            logger.warning(
                "Delivery %s failed after %d attempts: %s",
                entry.id, entry.attempts, error,
            )
            return

        # Defer with backoff
        delay = compute_backoff(
            entry.attempts,
            base_delay=self._base_delay,
            max_delay=self._max_delay,
        )
        entry.status = DeliveryStatus.DEFERRED
        entry.next_eligible_at = time.time() + delay

        logger.debug(
            "Deferring delivery %s (attempt %d, retry in %.1fs)",
            entry.id, entry.attempts, delay,
        )

        await self._queue.put((entry.priority.value, entry.created_at, entry.id))

    async def _recover_deferred(self) -> None:
        """Check for deferred entries that are now eligible."""
        now = time.time()
        for entry in self._entries.values():
            if entry.status == DeliveryStatus.DEFERRED and entry.next_eligible_at <= now:
                entry.status = DeliveryStatus.PENDING
                await self._queue.put((entry.priority.value, entry.created_at, entry.id))
