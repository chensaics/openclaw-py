"""MCP registry — manages multiple MCP server connections and their tools."""

from __future__ import annotations

import logging
from typing import Any

from pyclaw.agents.tools.base import BaseTool
from pyclaw.agents.types import AgentTool, ToolResult
from pyclaw.mcp.client import McpClient
from pyclaw.mcp.types import McpServerConfig, McpToolInfo

logger = logging.getLogger(__name__)


class McpToolAdapter(BaseTool):
    """Wraps a discovered MCP tool as an AgentTool for the agent runtime."""

    def __init__(self, tool_info: McpToolInfo, client: McpClient) -> None:
        self._info = tool_info
        self._client = client

    @property
    def name(self) -> str:
        return f"mcp_{self._info.server_name}_{self._info.name}"

    @property
    def description(self) -> str:
        prefix = f"[MCP: {self._info.server_name}] "
        return prefix + (self._info.description or self._info.name)

    @property
    def parameters(self) -> dict[str, Any]:
        return self._info.input_schema

    async def execute(self, tool_call_id: str, arguments: dict[str, Any]) -> ToolResult:
        try:
            result = await self._client.call_tool(self._info.name, arguments)
            return _mcp_result_to_tool_result(result)
        except TimeoutError:
            return ToolResult.text(
                f"MCP tool '{self._info.name}' timed out after {self._client._config.tool_timeout}s",
                is_error=True,
            )
        except Exception as exc:
            return ToolResult.text(f"MCP tool '{self._info.name}' error: {exc}", is_error=True)


class McpRegistry:
    """Manages connections to all configured MCP servers."""

    def __init__(self) -> None:
        self._clients: dict[str, McpClient] = {}

    async def connect_all(self, configs: dict[str, dict[str, Any]]) -> None:
        for name, raw in configs.items():
            config = _parse_server_config(name, raw)
            client = McpClient(config)
            try:
                await client.connect()
                self._clients[name] = client
                logger.info("MCP server '%s' connected (%d tools)", name, len(client.tools))
            except Exception:
                logger.exception("Failed to connect MCP server '%s'", name)

    async def disconnect_all(self) -> None:
        for name, client in self._clients.items():
            try:
                await client.disconnect()
            except Exception:
                logger.exception("Error disconnecting MCP server '%s'", name)
        self._clients.clear()

    def get_tools(self) -> list[AgentTool]:
        tools: list[AgentTool] = []
        for client in self._clients.values():
            for info in client.tools:
                tools.append(McpToolAdapter(info, client))
        return tools

    def get_status(self) -> list[dict[str, Any]]:
        statuses: list[dict[str, Any]] = []
        for name, client in self._clients.items():
            statuses.append(
                {
                    "name": name,
                    "connected": client.is_connected,
                    "tools": [t.name for t in client.tools],
                    "transport": "stdio" if client._config.is_stdio else "http",
                }
            )
        return statuses

    @property
    def server_count(self) -> int:
        return len(self._clients)

    @property
    def tool_count(self) -> int:
        return sum(len(c.tools) for c in self._clients.values())


def _parse_server_config(name: str, raw: dict[str, Any]) -> McpServerConfig:
    return McpServerConfig(
        name=name,
        command=raw.get("command"),
        args=raw.get("args", []),
        env=raw.get("env", {}),
        url=raw.get("url"),
        headers=raw.get("headers", {}),
        tool_timeout=raw.get("toolTimeout", 30),
    )


def _mcp_result_to_tool_result(result: Any) -> ToolResult:
    if isinstance(result, dict):
        content = result.get("content", [])
        is_error = result.get("isError", False)
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif isinstance(item, str):
                    texts.append(item)
            if texts:
                return ToolResult.text("\n".join(texts), is_error=is_error)
        if isinstance(content, str):
            return ToolResult.text(content, is_error=is_error)
    if isinstance(result, str):
        return ToolResult.text(result)
    return ToolResult.text(str(result))
