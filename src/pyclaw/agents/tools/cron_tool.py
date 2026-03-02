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
            "When scheduling a reminder, write the systemEvent text as something "
            "that will read like a reminder when it fires. Include recent context "
            "in reminder text if appropriate."
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
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression for 'add' (e.g. '0 9 * * *').",
                },
                "system_event": {
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
            name = arguments.get("name", "")
            cron_expr = arguments.get("cron_expr", "")
            event = arguments.get("system_event", "")
            if not name or not cron_expr:
                return ToolResult.text(
                    "Error: name and cron_expr are required for add.", is_error=True
                )

            from pyclaw.cron.scheduler import CronJob

            job = CronJob(name=name, cron_expr=cron_expr, system_event=event)
            self._scheduler.add_job(job)
            return ToolResult.text(f"Cron job '{name}' added: {cron_expr}")

        if action == "remove":
            name = arguments.get("name", "")
            if not name:
                return ToolResult.text("Error: name is required for remove.", is_error=True)
            self._scheduler.remove_job(name)
            return ToolResult.text(f"Cron job '{name}' removed.")

        return ToolResult.text(f"Unknown action: {action}", is_error=True)
