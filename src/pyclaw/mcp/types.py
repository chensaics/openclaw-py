"""MCP protocol types — JSON-RPC 2.0 messages and tool definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class McpServerConfig:
    """Configuration for a single MCP server."""

    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    tool_timeout: int = 30

    @property
    def is_stdio(self) -> bool:
        return self.command is not None

    @property
    def is_http(self) -> bool:
        return self.url is not None


@dataclass
class McpToolInfo:
    """Discovered tool from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str


@dataclass
class JsonRpcRequest:
    """JSON-RPC 2.0 request."""

    method: str
    params: dict[str, Any] | None = None
    id: int | str | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        if self.id is not None:
            d["id"] = self.id
        return d


@dataclass
class JsonRpcResponse:
    """JSON-RPC 2.0 response."""

    id: int | str | None = None
    result: Any = None
    error: dict[str, Any] | None = None
    jsonrpc: str = "2.0"

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JsonRpcResponse:
        return cls(
            id=data.get("id"),
            result=data.get("result"),
            error=data.get("error"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )
