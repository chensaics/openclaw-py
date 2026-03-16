"""Advanced cron — isolated agents, skill snapshots, task staggering, timeout, reaper.

Ported from ``src/cron/isolated-agent/*.ts`` and ``src/cron/service/*.ts``.

Provides:
- Isolated agent runner (independent session per cron task)
- Skill snapshot capture for cron agents
- Task staggering within the hour
- Per-task timeout policy
- Session reaper for expired sessions
- Webhook URL trigger support
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyclaw.constants.runtime import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SKIPPED,
    STATUS_TIMEOUT,
)

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    PENDING = STATUS_PENDING
    RUNNING = STATUS_RUNNING
    COMPLETED = STATUS_COMPLETED
    TIMEOUT = STATUS_TIMEOUT
    FAILED = STATUS_FAILED
    SKIPPED = STATUS_SKIPPED


@dataclass
class TimeoutPolicy:
    """Per-task timeout configuration."""

    default_timeout_s: float = 300.0
    max_timeout_s: float = 3600.0
    kill_grace_s: float = 10.0


@dataclass
class CronTaskConfig:
    """Configuration for a single cron task."""

    task_id: str
    schedule: str  # cron expression
    command: str = ""
    prompt: str = ""
    timeout_s: float = 300.0
    isolated: bool = True
    skills: list[str] = field(default_factory=list)
    webhook_url: str = ""
    enabled: bool = True
    stagger_offset_s: float = 0.0


@dataclass
class TaskExecution:
    """Record of a single task execution."""

    task_id: str
    state: TaskState = TaskState.PENDING
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""
    result: str = ""
    session_id: str = ""

    @property
    def duration_s(self) -> float:
        if self.started_at == 0:
            return 0
        end = self.finished_at or time.time()
        return end - self.started_at


# ---------------------------------------------------------------------------
# Skill Snapshot
# ---------------------------------------------------------------------------


@dataclass
class SkillSnapshot:
    """Frozen snapshot of skills for a cron agent."""

    task_id: str
    skills: list[str]
    captured_at: float = 0.0
    checksum: str = ""

    def __post_init__(self) -> None:
        if self.captured_at == 0:
            self.captured_at = time.time()
        if not self.checksum:
            self.checksum = hashlib.sha256(",".join(sorted(self.skills)).encode()).hexdigest()[:12]


def capture_skill_snapshot(task_id: str, skills: list[str]) -> SkillSnapshot:
    return SkillSnapshot(task_id=task_id, skills=list(skills))


# ---------------------------------------------------------------------------
# Task Staggering
# ---------------------------------------------------------------------------


def compute_stagger_offsets(
    tasks: list[CronTaskConfig],
    *,
    window_s: float = 3600.0,
) -> list[float]:
    """Compute stagger offsets so tasks don't all fire at once."""
    count = len(tasks)
    if count <= 1:
        return [0.0] * count

    interval = window_s / count
    return [i * interval for i in range(count)]


def apply_stagger(tasks: list[CronTaskConfig], *, window_s: float = 3600.0) -> None:
    """Apply stagger offsets to a list of tasks in-place."""
    offsets = compute_stagger_offsets(tasks, window_s=window_s)
    for task, offset in zip(tasks, offsets, strict=False):
        task.stagger_offset_s = offset


# ---------------------------------------------------------------------------
# Isolated Agent Runner
# ---------------------------------------------------------------------------

TaskHandler = Callable[[CronTaskConfig], Coroutine[Any, Any, str]]


class IsolatedAgentRunner:
    """Run cron tasks in isolated agent sessions."""

    def __init__(self, *, timeout_policy: TimeoutPolicy | None = None) -> None:
        self._policy = timeout_policy or TimeoutPolicy()
        self._executions: list[TaskExecution] = []

    async def run_task(
        self,
        task: CronTaskConfig,
        handler: TaskHandler,
    ) -> TaskExecution:
        """Run a single task with timeout enforcement."""
        execution = TaskExecution(
            task_id=task.task_id,
            state=TaskState.RUNNING,
            started_at=time.time(),
            session_id=f"cron-{task.task_id}-{int(time.time())}",
        )

        timeout = min(task.timeout_s or self._policy.default_timeout_s, self._policy.max_timeout_s)

        try:
            result = await asyncio.wait_for(handler(task), timeout=timeout)
            execution.state = TaskState.COMPLETED
            execution.result = result
        except TimeoutError:
            execution.state = TaskState.TIMEOUT
            execution.error = f"Task timed out after {timeout}s"
        except Exception as e:
            execution.state = TaskState.FAILED
            execution.error = str(e)
        finally:
            execution.finished_at = time.time()

        self._executions.append(execution)
        return execution

    @property
    def history(self) -> list[TaskExecution]:
        return list(self._executions)

    def clear_history(self) -> None:
        self._executions.clear()


# ---------------------------------------------------------------------------
# Session Reaper
# ---------------------------------------------------------------------------


@dataclass
class ReaperConfig:
    """Configuration for the session reaper."""

    max_idle_s: float = 3600.0
    max_age_s: float = 86400.0
    check_interval_s: float = 300.0


@dataclass
class SessionEntry:
    """A session tracked by the reaper."""

    session_id: str
    created_at: float
    last_active_at: float
    task_id: str = ""


class SessionReaper:
    """Clean up expired cron sessions."""

    def __init__(self, config: ReaperConfig | None = None) -> None:
        self._config = config or ReaperConfig()
        self._sessions: dict[str, SessionEntry] = {}

    def track(self, entry: SessionEntry) -> None:
        self._sessions[entry.session_id] = entry

    def untrack(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def find_expired(self) -> list[SessionEntry]:
        """Find sessions that exceeded idle or age limits."""
        now = time.time()
        expired: list[SessionEntry] = []
        for entry in self._sessions.values():
            idle = now - entry.last_active_at
            age = now - entry.created_at
            if idle > self._config.max_idle_s or age > self._config.max_age_s:
                expired.append(entry)
        return expired

    def reap(self) -> list[str]:
        """Remove expired sessions. Returns list of reaped session IDs."""
        expired = self.find_expired()
        reaped: list[str] = []
        for entry in expired:
            self._sessions.pop(entry.session_id, None)
            reaped.append(entry.session_id)
        return reaped

    @property
    def tracked_count(self) -> int:
        return len(self._sessions)


# ---------------------------------------------------------------------------
# Webhook Trigger
# ---------------------------------------------------------------------------


@dataclass
class WebhookTriggerResult:
    """Result of a webhook trigger."""

    task_id: str
    url: str
    success: bool
    status_code: int = 0
    error: str = ""


def build_webhook_payload(task: CronTaskConfig, execution: TaskExecution) -> dict[str, Any]:
    """Build webhook payload for a completed task."""
    return {
        "task_id": task.task_id,
        "state": execution.state.value,
        "duration_s": execution.duration_s,
        "result": execution.result,
        "error": execution.error,
        "timestamp": time.time(),
    }
