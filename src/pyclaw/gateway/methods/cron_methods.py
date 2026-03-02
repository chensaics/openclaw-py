"""Gateway methods: cron.list/add/remove — manage scheduled tasks."""

from __future__ import annotations

import uuid
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler


_scheduler: Any = None


def set_cron_scheduler(scheduler: Any) -> None:
    global _scheduler
    _scheduler = scheduler


def create_cron_handlers() -> dict[str, "MethodHandler"]:

    async def handle_cron_list(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        if not _scheduler:
            await conn.send_ok("cron.list", {"jobs": [], "note": "Scheduler not available"})
            return

        jobs = []
        for job in _scheduler.list_jobs():
            if hasattr(job, "to_dict"):
                jobs.append(job.to_dict())
            else:
                jobs.append({"id": str(job), "name": str(job)})

        await conn.send_ok("cron.list", {"jobs": jobs, "count": len(jobs)})

    async def handle_cron_add(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        if not _scheduler:
            await conn.send_error("cron.add", "unavailable", "Scheduler not available")
            return
        if not params:
            await conn.send_error("cron.add", "invalid_params", "Missing params")
            return

        from pyclaw.cron.scheduler import CronJob, ScheduleType

        name = params.get("name", "")
        schedule = params.get("schedule", "")
        message = params.get("message", params.get("command", ""))
        stype_str = params.get("scheduleType", "cron")

        try:
            stype = ScheduleType(stype_str)
        except ValueError:
            stype = ScheduleType.CRON

        job = CronJob(
            id=uuid.uuid4().hex[:8],
            name=name,
            schedule=schedule,
            schedule_type=stype,
            every_seconds=float(params.get("everySeconds", 0)),
            at=params.get("at", ""),
            message=message,
            enabled=params.get("enabled", True),
        )
        _scheduler.add_job(job)
        await conn.send_ok("cron.add", {"jobId": job.id, "ok": True})

    async def handle_cron_remove(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        if not _scheduler:
            await conn.send_error("cron.remove", "unavailable", "Scheduler not available")
            return
        if not params or "id" not in params:
            await conn.send_error("cron.remove", "invalid_params", "Missing job id")
            return

        removed = _scheduler.remove_job(params["id"])
        await conn.send_ok("cron.remove", {"ok": bool(removed)})

    return {
        "cron.list": handle_cron_list,
        "cron.add": handle_cron_add,
        "cron.remove": handle_cron_remove,
    }
