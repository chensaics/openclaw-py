"""Subagent framework — spawn, steer, kill, and manage child agent sessions."""

from pyclaw.agents.subagents.types import (
    SubagentConfig,
    SubagentMeta,
    SubagentResult,
    SubagentState,
)
from pyclaw.agents.subagents.manager import SubagentManager
from pyclaw.agents.subagents.runner import run_subagent

__all__ = [
    "SubagentConfig",
    "SubagentManager",
    "SubagentMeta",
    "SubagentResult",
    "SubagentState",
    "run_subagent",
]
