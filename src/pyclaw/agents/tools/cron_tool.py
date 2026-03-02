"""Cron tool — manage scheduled jobs and reminders."""

from __future__ import annotations

import json
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class CronTool(BaseTool):
    """Manage cron jobs and wake events."""

    owner_only = True

    def __init__(self, *, scheduler: Any = None) -> None:
        self._scheduler = scheduler

    @property
    def name(self) -> str:
        return "cron"

    @property
    def description(self) -> str:
        return (
            "Manage cron jobs and scheduled wake events. Use for setting reminders. "
            "Supports three schedule types: 'cron' (cron expression), 'every' "
            "(interval in seconds), and 'once' (one-time at a specific time). "
            "When scheduling a reminder, write the message text as something "
            "that will read like a reminder when it fires."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: 'add', 'remove', 'list'.",
                },
                "name": {
                    "type": "string",
                    "description": "Job name (for add/remove).",
                },
                "schedule": {
                    "type": "string",
                    "description": "Cron expression for 'add' (e.g. '0 9 * * *').",
                },
                "schedule_type": {
                    "type": "string",
                    "description": "Schedule type: 'cron' (default), 'every', or 'once'.",
                },
                "every_seconds": {
                    "type": "number",
                    "description": "Interval in seconds (for schedule_type='every').",
                },
                "at": {
                    "type": "string",
                    "description": "Run time for schedule_type='once' (ISO 8601 or HH:MM).",
                },
                "message": {
                    "type": "string",
                    "description": "Text that will be delivered when the job fires.",
                },
            },
            "required": ["action"],
        }

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        action = arguments.get("action", "")

        if not self._scheduler:
            return ToolResult.text("Cron scheduler is not configured.", is_error=True)

        if action == "list":
            jobs = self._scheduler.list_jobs()
            items = [j.to_dict() if hasattr(j, "to_dict") else str(j) for j in jobs]
            return ToolResult.text(json.dumps(items, indent=2))

        if action == "add":
            import uuid
            from pyclaw.cron.scheduler import CronJob, ScheduleType

            name = arguments.get("name", "")
            schedule = arguments.get("schedule", arguments.get("cron_expr", ""))
            message = arguments.get("message", arguments.get("system_event", ""))
            stype_str = arguments.get("schedule_type", "cron")
            every_seconds = float(arguments.get("every_seconds", 0))
            at = arguments.get("at", "")

            try:
                stype = ScheduleType(stype_str)
            except ValueError:
                stype = ScheduleType.CRON

            if stype == ScheduleType.CRON and not schedule:
                return ToolResult.text(
                    "Error: name and schedule are required for cron jobs.", is_error=True
                )
            if stype == ScheduleType.EVERY and not every_seconds:
                return ToolResult.text(
                    "Error: every_seconds is required for interval jobs.", is_error=True
                )
            if stype == ScheduleType.ONCE and not at:
                return ToolResult.text(
                    "Error: at is required for one-time jobs.", is_error=True
                )
            if not name:
                return ToolResult.text("Error: name is required.", is_error=True)

            job = CronJob(
                id=uuid.uuid4().hex[:8],
                name=name,
                schedule=schedule,
                schedule_type=stype,
                every_seconds=every_seconds,
                at=at,
                message=message,
            )
            self._scheduler.add_job(job)

            desc = schedule or f"every {every_seconds}s" if stype != ScheduleType.ONCE else f"at {at}"
            return ToolResult.text(f"Cron job '{name}' added ({stype.value}): {desc}")

        if action == "remove":
            name = arguments.get("name", "")
            if not name:
                return ToolResult.text("Error: name is required for remove.", is_error=True)
            self._scheduler.remove_job(name)
            return ToolResult.text(f"Cron job '{name}' removed.")

        return ToolResult.text(f"Unknown action: {action}", is_error=True)
