"""Orchestration module for flexible agent management."""

from pyclaw.agents.orchestration.decomposer import (
    Subtask,
    TaskPriority,
    decompose_task,
)
from pyclaw.agents.orchestration.manifest import (
    OrchestrationManifest,
    RoleConfig,
    RoleStatus,
    SpawnPolicy,
    ToolPolicy,
)
from pyclaw.agents.orchestration.orchestrator_tools import OrchestrateTool
from pyclaw.agents.orchestration.polling import (
    SubagentJoinTool,
    SubagentPollTool,
)
from pyclaw.agents.orchestration.storage import (
    load_manifest,
    save_manifest,
    update_manifest_status,
)

__all__ = [
    "OrchestrationManifest",
    "RoleConfig",
    "RoleStatus",
    "SpawnPolicy",
    "ToolPolicy",
    "save_manifest",
    "load_manifest",
    "update_manifest_status",
    "decompose_task",
    "TaskPriority",
    "Subtask",
    "SubagentPollTool",
    "SubagentJoinTool",
    "OrchestrateTool",
]
