"""Cron scheduler — APScheduler-based scheduled task execution.

Supports cron expressions for periodic agent tasks (e.g. daily summaries,
periodic checks, scheduled messages).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("pyclaw.cron")


@dataclass
class CronJob:
    """A scheduled job definition."""

    id: str
    name: str
    schedule: str  # cron expression (e.g. "0 9 * * *")
    agent_id: str = "main"
    message: str = ""
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "schedule": self.schedule,
            "agentId": self.agent_id,
            "message": self.message,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


class CronScheduler:
    """Manages scheduled jobs using APScheduler."""

    def __init__(self) -> None:
        self._scheduler: Any = None
        self._jobs: dict[str, CronJob] = {}
        self._handler: Callable[..., Coroutine[Any, Any, Any]] | None = None

    def set_handler(self, handler: Callable[..., Coroutine[Any, Any, Any]]) -> None:
        """Set the async handler called when a job fires.

        Signature: async def handler(job: CronJob) -> None
        """
        self._handler = handler

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

    def _add_apscheduler_job(self, job: CronJob) -> None:
        from apscheduler.triggers.cron import CronTrigger

        parts = job.schedule.split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        else:
            logger.warning("Invalid cron expression for job %s: %s", job.id, job.schedule)
            return

        self._scheduler.add_job(
            self._execute_job,
            trigger,
            id=job.id,
            args=[job],
            replace_existing=True,
        )

    async def _execute_job(self, job: CronJob) -> None:
        logger.info("Executing cron job: %s (%s)", job.name, job.id)
        if self._handler:
            try:
                await self._handler(job)
            except Exception:
                logger.exception("Cron job failed: %s", job.id)
