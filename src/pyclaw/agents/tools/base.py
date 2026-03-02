"""Base class for agent tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pyclaw.agents.types import ToolResult


class BaseTool(ABC):
    """Convenience base class that satisfies the AgentTool protocol.

    Subclasses must implement ``name``, ``description``, ``parameters``,
    and ``execute``.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]: ...

    @abstractmethod
    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult: ...

    # Optional flag — when True the tool is restricted to the device owner
    owner_only: bool = False
