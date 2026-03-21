"""Subagent type definitions using Pydantic for consistency with orchestration module."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from pyclaw.constants.runtime import STATUS_ABORTED, STATUS_COMPLETED, STATUS_FAILED, STATUS_PENDING, STATUS_RUNNING


class SubagentState(str, Enum):
    """Status of a subagent."""

    PENDING = STATUS_PENDING
    RUNNING = STATUS_RUNNING
    COMPLETED = STATUS_COMPLETED
    FAILED = STATUS_FAILED
    ABORTED = STATUS_ABORTED


class SubagentConfig(BaseModel):
    """Configuration for spawning a subagent."""

    session_id: str = ""
    parent_session_id: str = ""
    agent_id: str = "main"
    prompt: str = ""
    provider: str = ""
    model: str = ""
    workspace_dir: str = ""
    max_depth: int = 3
    current_depth: int = 0
    tools_enabled: list[str] = Field(default_factory=list)
    tools_disabled: list[str] = Field(default_factory=list)
    notify_parent: bool = False
    channel: str = ""
    chat_id: str = ""
    label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str | None = Field(None)  # NEW: Custom system prompt override
    tool_context: dict[str, Any] = Field(default_factory=dict)  # NEW: Additional context for tools


class SubagentMeta(BaseModel):
    """Metadata about a subagent run."""

    session_id: str = ""
    agent_id: str = ""
    provider: str = ""
    model: str = ""
    duration_ms: int = 0
    depth: int = 0
    token_usage: dict[str, int] = Field(default_factory=dict)


class SubagentResult(BaseModel):
    """Result of a subagent execution."""

    state: SubagentState = SubagentState.COMPLETED
    output: str = ""
    meta: SubagentMeta = Field(default_factory=SubagentMeta)
    error: str | None = None
    payloads: list[dict[str, Any]] = Field(default_factory=list)
