"""Orchestration manifest data structures for flexible agent management."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RoleStatus(str, Enum):
    """Status of a role in the orchestration manifest."""

    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETIRED = "retired"
    CANCELLED = "cancelled"


class ToolPolicy(BaseModel):
    """Tool access policy for roles."""

    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class RoleConfig(BaseModel):
    """Configuration for a single role in the orchestration manifest."""

    role_id: str = Field(...)
    name: str = Field(...)
    responsibility: str = Field(...)
    status: RoleStatus = RoleStatus.PLANNED
    tools_allowed: list[str] | None = Field(None)
    tools_denied: list[str] | None = Field(None)
    preferred_model: str | None = Field(None)
    dependencies: list[str] = Field(default_factory=list)


class SpawnPolicy(BaseModel):
    """Spawn policy for controlling subagent creation."""

    max_parallel: int = 4
    max_depth: int = 5
    timeout_seconds: int = 300


class OrchestrationManifest(BaseModel):
    """Complete orchestration manifest for task delegation."""

    version: str = "1.0"
    task_id: str
    goal: str
    roles: list[RoleConfig]
    spawn_policy: SpawnPolicy = Field(default_factory=SpawnPolicy)
    tool_policy: ToolPolicy | None = Field(None)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
