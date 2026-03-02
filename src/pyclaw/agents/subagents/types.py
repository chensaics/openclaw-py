"""Subagent type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SubagentState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class SubagentConfig:
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
    tools_enabled: list[str] = field(default_factory=list)
    tools_disabled: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubagentMeta:
    """Metadata about a subagent run."""

    session_id: str = ""
    agent_id: str = ""
    provider: str = ""
    model: str = ""
    duration_ms: int = 0
    depth: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)


@dataclass
class SubagentResult:
    """Result of a subagent execution."""

    state: SubagentState = SubagentState.COMPLETED
    output: str = ""
    meta: SubagentMeta = field(default_factory=SubagentMeta)
    error: str | None = None
    payloads: list[dict[str, Any]] = field(default_factory=list)
