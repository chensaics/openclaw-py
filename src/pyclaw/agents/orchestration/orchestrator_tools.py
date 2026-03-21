"""Orchestration tools for flexible agent management."""

from __future__ import annotations

import uuid
from typing import Any

from pyclaw.agents.orchestration.decomposer import decompose_task
from pyclaw.agents.orchestration.manifest import (
    OrchestrationManifest,
    RoleStatus,
    SpawnPolicy,
)
from pyclaw.agents.orchestration.storage import save_manifest
from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import ToolResult


class OrchestrateTool(BaseTool):
    """Create an orchestration manifest to plan task delegation."""

    def __init__(self, *, manifest_storage: Any = None) -> None:
        self._storage = manifest_storage

    @property
    def name(self) -> str:
        return "orchestrate_manifest"

    @property
    def description(self) -> str:
        return (
            "Create an orchestration manifest to plan task delegation. "
            "Define roles, responsibilities, and spawn policy for the task."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Unique identifier for this task.",
                },
                "goal": {
                    "type": "string",
                    "description": "One-sentence goal of the task.",
                },
                "subtasks": {
                    "type": "array",
                    "description": "List of subtasks with descriptions and priorities.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "priority": {
                                "type": "string",
                                "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "BACKGROUND"],
                            },
                        },
                    },
                },
                "max_parallel": {
                    "type": "integer",
                    "description": "Maximum concurrent subagents.",
                },
            },
            "required": ["goal", "subtasks"],
        }

    async def execute(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        task_id = arguments.get("task_id", str(uuid.uuid4()))
        goal = arguments.get("goal", "")
        subtasks_input = arguments.get("subtasks", [])
        max_parallel = arguments.get("max_parallel", 4)

        if not goal:
            return ToolResult.text("Error: goal is required.", is_error=True)

        subtasks = subtasks_input or decompose_task(goal)

        # Build manifest
        manifest = OrchestrationManifest(
            version="1.0",
            task_id=task_id,
            goal=goal,
            roles=[
                {
                    "role_id": f"role-{i}",
                    "name": f"Subtask {i + 1}",
                    "responsibility": (
                        task.get("description", "")
                        if isinstance(task, dict)
                        else (task.description if hasattr(task, "description") else str(task))
                    ),
                    "status": RoleStatus.PLANNED,
                    "tools_allowed": None,  # Default: inherit from global
                    "preferred_model": None,
                }
                for i, task in enumerate(subtasks)
            ],
            spawn_policy=SpawnPolicy(max_parallel=max_parallel),
            tool_policy=None,
        )

        # Save manifest
        # For now, save to session-side storage
        # In a real implementation, this would be associated with current session
        save_manifest(manifest, session_id="current")  # Placeholder session ID

        return ToolResult.json(
            {
                "status": "created",
                "manifest_id": task_id,
                "roles_count": len(manifest.roles),
                "message": f"Created manifest with {len(manifest.roles)} roles.",
            }
        )
