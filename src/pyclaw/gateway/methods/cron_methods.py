"""Gateway methods: cron.list/add/remove — manage scheduled tasks."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection


# Module-level scheduler reference (set during registration)
_scheduler: Any = None


def set_cron_scheduler(scheduler: Any) -> None:
    global _scheduler
    _scheduler = scheduler


async def _handle_cron_list(
    params: dict[str, Any] | None,
    conn: GatewayConnection,
) -> dict[str, Any]:
    if not _scheduler:
        return {"jobs": [], "error": "Scheduler not available"}

    jobs = []
    for job in _scheduler.list_jobs():
        jobs.append({
            "id": job.get("id", ""),
            "name": job.get("name", ""),
            "schedule": job.get("schedule", ""),
            "nextRun": job.get("next_run", ""),
            "enabled": job.get("enabled", True),
        })
    return {"jobs": jobs}


async def _handle_cron_add(
    params: dict[str, Any] | None,
    conn: GatewayConnection,
) -> dict[str, Any]:
    if not _scheduler:
        return {"error": "Scheduler not available"}
    if not params:
        return {"error": "Missing params"}

    name = params.get("name", "")
    schedule = params.get("schedule", "")
    command = params.get("command", "")

    if not schedule or not command:
        return {"error": "schedule and command are required"}

    job_id = _scheduler.add_job(name=name, schedule=schedule, command=command)
    return {"jobId": job_id, "ok": True}


async def _handle_cron_remove(
    params: dict[str, Any] | None,
    conn: GatewayConnection,
) -> dict[str, Any]:
    if not _scheduler:
        return {"error": "Scheduler not available"}
    if not params or "id" not in params:
        return {"error": "Missing job id"}

    _scheduler.remove_job(params["id"])
    return {"ok": True}


def create_cron_handlers() -> dict[str, Any]:
    return {
        "cron.list": _handle_cron_list,
        "cron.add": _handle_cron_add,
        "cron.remove": _handle_cron_remove,
    }
