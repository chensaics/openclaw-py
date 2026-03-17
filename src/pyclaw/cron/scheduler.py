"""Cron scheduler — APScheduler-based scheduled task execution.

Supports three schedule types:
- **cron**: Standard cron expressions (e.g. "0 9 * * *")
- **every**: Periodic interval in seconds (e.g. every_seconds=300)
- **once**: One-time execution at a specific datetime (ISO 8601 or HH:MM)

Also integrates with :mod:`pyclaw.cron.history` for execution recording and
optional channel notification on completion.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from pyclaw.constants.runtime import STATUS_OK

logger = logging.getLogger("pyclaw.cron")


class ScheduleType(str, Enum):
    CRON = "cron"
    EVERY = "every"
    ONCE = "once"


@dataclass
class CronJob:
    """A scheduled job definition."""

    id: str
    name: str
    schedule: str  # cron expression (e.g. "0 9 * * *")
    schedule_type: ScheduleType = ScheduleType.CRON
    every_seconds: float = 0.0
    at: str = ""  # ISO 8601 or "HH:MM" for once-type
    agent_id: str = "main"
    handler_id: str = ""
    message: str = ""
    enabled: bool = True
    channel: str = ""
    chat_id: str = ""
    deliver: bool = False
    failure_destination: str = ""
    failure_channel: str = ""
    execution_mode: str = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "schedule": self.schedule,
            "scheduleType": self.schedule_type.value,
            "everySeconds": self.every_seconds,
            "at": self.at,
            "agentId": self.agent_id,
            "handlerId": self.handler_id,
            "message": self.message,
            "enabled": self.enabled,
            "channel": self.channel,
            "chatId": self.chat_id,
            "deliver": self.deliver,
            "failureDestination": self.failure_destination,
            "failureChannel": self.failure_channel,
            "executionMode": self.execution_mode,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CronJob:
        from pyclaw.cron.history import _legacy_schedule_to_cron

        schedule = data.get("schedule", "")
        if schedule and len(schedule.split()) != 5 and schedule not in ("every", "once"):
            try:
                schedule = _legacy_schedule_to_cron(schedule)
            except ValueError:
                pass
        handler_id = data.get("handlerId", data.get("handler_id", data.get("command", "")))
        message = data.get("message", "")
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            schedule=schedule,
            schedule_type=ScheduleType(data.get("scheduleType", "cron")),
            every_seconds=float(data.get("everySeconds", 0)),
            at=data.get("at", ""),
            agent_id=data.get("agentId", "main"),
            handler_id=handler_id,
            message=message,
            enabled=data.get("enabled", True),
            channel=data.get("channel", ""),
            chat_id=data.get("chatId", ""),
            deliver=data.get("deliver", False),
            failure_destination=data.get("failureDestination", data.get("failure_destination", "")),
            failure_channel=data.get("failureChannel", data.get("failure_channel", "")),
            execution_mode=data.get("executionMode", "auto"),
            metadata=data.get("metadata", {}),
        )


class CronScheduler:
    """Manages scheduled jobs using APScheduler with cron/every/once support."""

    def __init__(self) -> None:
        self._scheduler: Any = None
        self._jobs: dict[str, CronJob] = {}
        self._handler: Callable[..., Coroutine[Any, Any, Any]] | None = None
        self._notify_handler: Callable[..., Coroutine[Any, Any, Any]] | None = None
        self._history: Any = None

    def set_handler(self, handler: Callable[..., Coroutine[Any, Any, Any]]) -> None:
        """Set the async handler called when a job fires.

        Signature: async def handler(job: CronJob) -> None
        """
        self._handler = handler

    def set_notify_handler(self, handler: Callable[..., Coroutine[Any, Any, Any]]) -> None:
        """Set the handler for delivering job results to channels."""
        self._notify_handler = handler

    def set_history(self, history: Any) -> None:
        """Attach a HistoryStore for execution recording."""
        self._history = history

    def start(self) -> None:
        """Start the APScheduler background scheduler."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._scheduler = AsyncIOScheduler()

        for job in self._jobs.values():
            if job.enabled:
                self._add_apscheduler_job(job)

        self._scheduler.start()
        logger.info("Cron scheduler started with %d jobs", len(self._jobs))

    def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("Cron scheduler stopped")

    def add_job(self, job: CronJob) -> None:
        """Add a new scheduled job."""
        self._jobs[job.id] = job
        if self._scheduler and job.enabled:
            self._add_apscheduler_job(job)

    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        if self._scheduler:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
        return True

    def list_jobs(self) -> list[CronJob]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> CronJob | None:
        return self._jobs.get(job_id)

    def toggle_job(self, job_id: str, enabled: bool) -> bool:
        """Enable or disable a job by ID. Returns True if job was found and toggled."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.enabled = enabled
        if self._scheduler:
            if enabled:
                self._add_apscheduler_job(job)
            else:
                try:
                    self._scheduler.remove_job(job_id)
                except Exception:
                    pass
        return True

    def _add_apscheduler_job(self, job: CronJob) -> None:
        trigger = self._build_trigger(job)
        if trigger is None:
            return

        self._scheduler.add_job(
            self._execute_job,
            trigger,
            id=job.id,
            args=[job],
            replace_existing=True,
        )

    def _build_trigger(self, job: CronJob) -> Any:
        """Build an APScheduler trigger based on schedule type."""
        if job.schedule_type == ScheduleType.EVERY:
            from apscheduler.triggers.interval import IntervalTrigger

            seconds = job.every_seconds or 60.0
            return IntervalTrigger(seconds=seconds)

        if job.schedule_type == ScheduleType.ONCE:
            from apscheduler.triggers.date import DateTrigger

            run_date = parse_at_time(job.at)
            if run_date is None:
                logger.warning("Invalid 'at' time for job %s: %s", job.id, job.at)
                return None
            return DateTrigger(run_date=run_date)

        # Default: cron expression
        from apscheduler.triggers.cron import CronTrigger

        parts = job.schedule.split()
        if len(parts) == 5:
            return CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )

        logger.warning("Invalid cron expression for job %s: %s", job.id, job.schedule)
        return None

    async def _execute_job(self, job: CronJob) -> None:
        logger.info("Executing cron job: %s (%s)", job.name, job.id)

        record = None
        if self._history:
            from pyclaw.cron.history import ExecutionRecord, ExecutionStatus

            record = ExecutionRecord(
                id=uuid.uuid4().hex[:12],
                job_id=job.id,
                job_title=job.name,
                status=ExecutionStatus.RUNNING,
                started_at=time.time(),
            )
            self._history.add(record)

        result_text = ""
        error_text = ""
        try:
            if self._handler:
                handler_result = await self._handler(job)
                result_text = str(handler_result) if handler_result is not None else STATUS_OK
        except Exception as e:
            logger.exception("Cron job failed: %s", job.id)
            error_text = str(e)

        if record and self._history:
            from pyclaw.cron.history import ExecutionStatus

            record.ended_at = time.time()
            record.status = ExecutionStatus.FAILED if error_text else ExecutionStatus.COMPLETED
            record.output = result_text
            record.error = error_text
            self._history.update(
                record.id, ended_at=record.ended_at, status=record.status, output=result_text, error=error_text
            )

        if job.deliver and self._notify_handler:
            if "HEARTBEAT_OK" in result_text or "HEARTBEAT_OK" in error_text:
                pass
            else:
                try:
                    msg = f"[Cron] {job.name}: {'OK' if not error_text else f'FAILED: {error_text}'}"
                    if error_text and (job.failure_destination or job.failure_channel):
                        ch = job.failure_destination or job.channel
                        chat = job.failure_channel or job.chat_id
                        await self._notify_handler(ch, chat, msg)
                    else:
                        await self._notify_handler(job.channel, job.chat_id, msg)
                except Exception:
                    logger.debug("Failed to deliver cron notification for %s", job.id)


# ---------------------------------------------------------------------------
# Time parsing for "at" / "once" schedules
# ---------------------------------------------------------------------------


def parse_at_time(at: str) -> datetime | None:
    """Parse an 'at' time string into a datetime.

    Supported formats:
    - ISO 8601: ``2026-03-02T14:30:00``
    - Date + time: ``2026-03-02 14:30``
    - Time only: ``14:30`` (next occurrence, today or tomorrow)
    """
    if not at:
        return None

    at = at.strip()

    # ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(at, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    # Time-only (HH:MM)
    import re

    m = re.match(r"^(\d{1,2}):(\d{2})$", at)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        now = datetime.now(timezone.utc)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    return None
