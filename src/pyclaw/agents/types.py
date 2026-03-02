"""Agent runtime types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class AgentEvent:
    """An event emitted during an agent run."""

    type: str
    # "agent_start" | "agent_end"
    # "message_start" | "message_update" | "message_end"
    # "tool_start" | "tool_update" | "tool_end"
    # "error"
    delta: str | None = None
    name: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    tool_call_id: str | None = None
    usage: dict[str, int] | None = None


@dataclass
class ToolCall:
    """A tool call extracted from an LLM response."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool."""

    content: list[dict[str, Any]]
    is_error: bool = False

    @classmethod
    def text(cls, text: str, is_error: bool = False) -> ToolResult:
        return cls(content=[{"type": "text", "text": text}], is_error=is_error)


@dataclass
class ModelConfig:
    """Configuration for a specific LLM model."""

    provider: str  # "openai" | "anthropic" | "google" | "ollama" | ...
    model_id: str
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None


@runtime_checkable
class AgentTool(Protocol):
    """Interface for agent tools."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def parameters(self) -> dict[str, Any]: ...

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult: ...
