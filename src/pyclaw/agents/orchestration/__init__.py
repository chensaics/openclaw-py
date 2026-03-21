"""Orchestration module for flexible agent management."""

from pyclaw.agents.orchestration.manifest import (
    OrchestrationManifest,
    RoleConfig,
    RoleStatus,
    SpawnPolicy,
    ToolPolicy,
)

__all__ = [
    "OrchestrationManifest",
    "RoleConfig",
    "RoleStatus",
    "SpawnPolicy",
    "ToolPolicy",
]
