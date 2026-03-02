"""Convenience wrapper for running a subagent."""

from __future__ import annotations

from pyclaw.agents.subagents.manager import SubagentManager
from pyclaw.agents.subagents.types import SubagentConfig, SubagentResult


async def run_subagent(
    *,
    prompt: str,
    parent_session_id: str = "",
    agent_id: str = "main",
    provider: str = "",
    model: str = "",
    workspace_dir: str = "",
    current_depth: int = 0,
    manager: SubagentManager | None = None,
) -> SubagentResult:
    """Spawn and run a subagent, returning its result."""
    mgr = manager or SubagentManager()

    config = SubagentConfig(
        parent_session_id=parent_session_id,
        agent_id=agent_id,
        prompt=prompt,
        provider=provider,
        model=model,
        workspace_dir=workspace_dir,
        current_depth=current_depth,
    )

    return await mgr.spawn(config)
