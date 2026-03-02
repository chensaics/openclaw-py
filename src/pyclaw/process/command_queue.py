"""Command queue — lane-based command queuing with drain/clear semantics.

Ported from ``src/process/command-queue*.ts``.

Provides:
- Lane-based command queue (each lane processes sequentially)
- Drain mode (stop accepting, finish pending)
- Clear with error notification
- CommandLaneClearedError / GatewayDrainingError
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class QueueState(str, Enum):
    ACTIVE = "active"
    DRAINING = "draining"
    STOPPED = "stopped"


class CommandLaneClearedError(Exception):
    """Raised when a command lane is cleared while a command is pending."""

    def __init__(self, lane: str) -> None:
        self.lane = lane
        super().__init__(f"Command lane '{lane}' was cleared")


class GatewayDrainingError(Exception):
    """Raised when the gateway is draining and new commands are rejected."""

    def __init__(self) -> None:
        super().__init__("Gateway is draining, new commands are not accepted")


@dataclass
class QueuedCommand:
    """A command waiting in a lane."""
    command_id: str
    lane: str
    payload: dict[str, Any] = field(default_factory=dict)
    enqueued_at: float = 0.0
    priority: int = 0

    def __post_init__(self) -> None:
        if self.enqueued_at == 0.0:
            self.enqueued_at = time.time()


@dataclass
class LaneStats:
    """Statistics for a command lane."""
    lane: str
    pending: int = 0
    completed: int = 0
    failed: int = 0
    cleared: int = 0


CommandHandler = Callable[[QueuedCommand], Coroutine[Any, Any, bool]]


class CommandLane:
    """A single command lane (FIFO queue with sequential execution)."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._queue: list[QueuedCommand] = []
        self._stats = LaneStats(lane=name)
        self._processing = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def stats(self) -> LaneStats:
        self._stats.pending = len(self._queue)
        return self._stats

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    def enqueue(self, command: QueuedCommand) -> None:
        self._queue.append(command)
        self._queue.sort(key=lambda c: c.priority, reverse=True)

    def dequeue(self) -> QueuedCommand | None:
        if not self._queue:
            return None
        return self._queue.pop(0)

    def clear(self) -> int:
        """Clear all pending commands. Returns count cleared."""
        count = len(self._queue)
        self._queue.clear()
        self._stats.cleared += count
        return count

    def peek(self) -> QueuedCommand | None:
        return self._queue[0] if self._queue else None

    def record_completed(self) -> None:
        self._stats.completed += 1

    def record_failed(self) -> None:
        self._stats.failed += 1


class CommandQueue:
    """Multi-lane command queue with drain/clear semantics."""

    def __init__(self) -> None:
        self._lanes: dict[str, CommandLane] = {}
        self._state = QueueState.ACTIVE
        self._handlers: dict[str, CommandHandler] = {}

    @property
    def state(self) -> QueueState:
        return self._state

    def register_handler(self, lane: str, handler: CommandHandler) -> None:
        self._handlers[lane] = handler

    def _get_or_create_lane(self, name: str) -> CommandLane:
        if name not in self._lanes:
            self._lanes[name] = CommandLane(name)
        return self._lanes[name]

    def enqueue(self, command: QueuedCommand) -> None:
        """Add a command to its lane."""
        if self._state == QueueState.DRAINING:
            raise GatewayDrainingError()
        if self._state == QueueState.STOPPED:
            raise GatewayDrainingError()

        lane = self._get_or_create_lane(command.lane)
        lane.enqueue(command)

    async def process_lane(self, lane_name: str) -> int:
        """Process all pending commands in a lane. Returns count processed."""
        lane = self._lanes.get(lane_name)
        if not lane:
            return 0

        handler = self._handlers.get(lane_name)
        if not handler:
            return 0

        processed = 0
        while True:
            cmd = lane.dequeue()
            if not cmd:
                break

            try:
                success = await handler(cmd)
                if success:
                    lane.record_completed()
                else:
                    lane.record_failed()
                processed += 1
            except CommandLaneClearedError:
                break
            except Exception as e:
                logger.error("Command %s failed: %s", cmd.command_id, e)
                lane.record_failed()
                processed += 1

        return processed

    def clear_lane(self, lane_name: str) -> int:
        """Clear all pending commands in a lane."""
        lane = self._lanes.get(lane_name)
        if not lane:
            return 0
        return lane.clear()

    def drain(self) -> None:
        """Enter drain mode — stop accepting, finish pending."""
        self._state = QueueState.DRAINING

    def stop(self) -> int:
        """Stop and clear all lanes."""
        self._state = QueueState.STOPPED
        total = 0
        for lane in self._lanes.values():
            total += lane.clear()
        return total

    def resume(self) -> None:
        """Resume accepting commands after drain."""
        self._state = QueueState.ACTIVE

    def get_stats(self) -> dict[str, LaneStats]:
        return {name: lane.stats for name, lane in self._lanes.items()}

    @property
    def total_pending(self) -> int:
        return sum(lane.pending_count for lane in self._lanes.values())

    @property
    def lane_count(self) -> int:
        return len(self._lanes)
