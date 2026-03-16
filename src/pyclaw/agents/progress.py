"""Progress streaming — structured progress events for long-running operations.

Emits ``ProgressEvent`` objects that Gateway can broadcast to connected
clients, enabling UI progress bars and status updates.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyclaw.constants.runtime import STATUS_COMPLETED, STATUS_FAILED

logger = logging.getLogger(__name__)


class ProgressStatus(str, Enum):
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = STATUS_COMPLETED
    FAILED = STATUS_FAILED


@dataclass
class ProgressEvent:
    """A single progress update for a tracked operation."""

    task_id: str
    status: ProgressStatus
    progress: float = 0.0  # 0.0 – 1.0
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "taskId": self.task_id,
            "status": self.status.value,
            "progress": round(self.progress, 3),
            "timestamp": self.timestamp,
        }
        if self.message:
            d["message"] = self.message
        if self.detail:
            d["detail"] = self.detail
        return d


ProgressCallback = Callable[[ProgressEvent], None]

_global_listeners: list[ProgressCallback] = []


def add_progress_listener(cb: ProgressCallback) -> None:
    _global_listeners.append(cb)


def remove_progress_listener(cb: ProgressCallback) -> None:
    try:
        _global_listeners.remove(cb)
    except ValueError:
        pass


def emit_progress(event: ProgressEvent) -> None:
    """Broadcast a progress event to all registered listeners."""
    for cb in _global_listeners:
        try:
            cb(event)
        except Exception:
            logger.debug("Progress listener error", exc_info=True)


class ProgressTracker:
    """Context-manager helper for tracking a multi-step operation.

    Usage::

        async with ProgressTracker("install-skill", total=4) as t:
            t.step("Downloading...")
            await download()
            t.step("Extracting...")
            await extract()
    """

    def __init__(self, task_id: str, total: int = 1) -> None:
        self.task_id = task_id
        self.total = max(total, 1)
        self._current = 0

    async def __aenter__(self) -> ProgressTracker:
        emit_progress(
            ProgressEvent(
                task_id=self.task_id,
                status=ProgressStatus.STARTED,
                message="Starting...",
            )
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            emit_progress(
                ProgressEvent(
                    task_id=self.task_id,
                    status=ProgressStatus.FAILED,
                    progress=self._current / self.total,
                    message=str(exc_val) if exc_val else "Failed",
                )
            )
        else:
            emit_progress(
                ProgressEvent(
                    task_id=self.task_id,
                    status=ProgressStatus.COMPLETED,
                    progress=1.0,
                    message="Done",
                )
            )

    def step(self, message: str = "", **detail: Any) -> None:
        self._current += 1
        emit_progress(
            ProgressEvent(
                task_id=self.task_id,
                status=ProgressStatus.PROGRESS,
                progress=min(self._current / self.total, 1.0),
                message=message,
                detail=detail,
            )
        )
