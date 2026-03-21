"""Task decomposition interface for breaking down complex tasks into subtasks."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskPriority(int, Enum):
    """Priority levels for tasks."""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


class Subtask(BaseModel):
    """A single executable subtask in a decomposition."""

    id: str = Field(...)
    description: str = Field(...)
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_duration_seconds: int = 60
    required_role: str | None = Field(None)
    dependencies: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


def decompose_task(
    task_description: str,
    context: dict[str, Any] | None = None,
    manifest: Any = None,
) -> list[Subtask]:
    """Decompose a complex task into executable subtasks.

    This is a keyword-based decomposition implementation. Future versions
    may use LLM-based decomposition or pattern matching for more
    intelligent breakdown.

    Args:
        task_description: The main task to decompose.
        context: Additional context for decomposition (e.g., domain, constraints).
        manifest: Optional orchestration manifest for role-based decomposition.

    Returns:
        List of Subtask objects with dependencies and priorities.
    """
    subtasks: list[Subtask] = []

    # Extract action verbs and entities
    task_lower = task_description.lower()

    # Search-related tasks
    if "search" in task_lower or "find" in task_lower:
        subtasks.append(
            Subtask(
                id="search-info",
                description=f"Search for information about {task_description}",
                priority=TaskPriority.HIGH,
                required_role="researcher",
            )
        )

    # Analysis-related tasks
    if "analyze" in task_lower or "review" in task_lower:
        subtasks.append(
            Subtask(
                id="analyze-data",
                description="Analyze found data",
                priority=TaskPriority.MEDIUM,
                required_role="analyst",
                dependencies=["search-info"],
            )
        )

    # Documentation-related tasks
    if "report" in task_lower or "document" in task_lower:
        subtasks.append(
            Subtask(
                id="create-report",
                description="Create a report with findings",
                priority=TaskPriority.MEDIUM,
                required_role="writer",
                dependencies=["analyze-data"],
            )
        )

    # Default: single task if no patterns matched
    if not subtasks:
        subtasks.append(
            Subtask(
                id="execute-task",
                description=task_description,
                priority=TaskPriority.MEDIUM,
                required_role="generalist",
            )
        )

    return subtasks
