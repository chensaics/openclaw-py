"""ACP types — session metadata, agent info, events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AcpAgentInfo:
    name: str = "pyclaw"
    version: str = "1.0"
    capabilities: list[str] = field(default_factory=lambda: ["chat", "tools"])


@dataclass
class AcpSessionMeta:
    session_id: str = ""
    session_key: str = ""
    session_label: str = ""
    cwd: str = ""
    agent_id: str = "main"
    mode: str = "agent"  # "agent" | "edit" | "chat"
    created_at: float = 0.0


@dataclass
class AcpRequest:
    id: int = 0
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class AcpResponse:
    id: int = 0
    result: Any = None
    error: dict[str, Any] | None = None


@dataclass
class AcpEvent:
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)
