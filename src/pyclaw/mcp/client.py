"""MCP client — manages connections to MCP servers and discovers tools."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyclaw.mcp.types import McpServerConfig, McpToolInfo

logger = logging.getLogger(__name__)


class McpClient:
    """Client for a single MCP server — handles connection, initialization, and tool calls."""

    def __init__(self, config: McpServerConfig) -> None:
        self._config = config
        self._transport: Any = None
        self._tools: list[McpToolInfo] = []
        self._initialized = False

    @property
    def server_name(self) -> str:
        return self._config.name

    @property
    def tools(self) -> list[McpToolInfo]:
        return list(self._tools)

    @property
    def is_connected(self) -> bool:
        return self._transport is not None and self._transport.is_connected

    async def connect(self) -> None:
        if self._config.is_stdio:
            from pyclaw.mcp.stdio_transport import StdioTransport

            assert self._config.command is not None
            self._transport = StdioTransport(
                command=self._config.command,
                args=self._config.args,
                env=self._config.env,
            )
        elif self._config.is_http:
            from pyclaw.mcp.http_transport import HttpTransport

            assert self._config.url is not None
            self._transport = HttpTransport(
                url=self._config.url,
                headers=self._config.headers,
            )
        else:
            raise ValueError(f"MCP server '{self._config.name}': must specify 'command' or 'url'")

        await self._transport.connect()
        await self._initialize()
        await self._discover_tools()

    async def disconnect(self) -> None:
        if self._transport:
            await self._transport.disconnect()
            self._transport = None
        self._initialized = False
        self._tools.clear()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if not self._transport:
            raise RuntimeError(f"MCP server '{self._config.name}' not connected")

        result = await asyncio.wait_for(
            self._transport.send("tools/call", {"name": tool_name, "arguments": arguments}),
            timeout=self._config.tool_timeout,
        )
        return result

    async def _initialize(self) -> None:
        result = await self._transport.send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pyclaw", "version": "0.1.0"},
            },
        )
        logger.info(
            "MCP server '%s' initialized: %s",
            self._config.name,
            result.get("serverInfo", {}).get("name", "unknown") if isinstance(result, dict) else "ok",
        )
        self._initialized = True

        await self._transport.send("notifications/initialized", None)

    async def _discover_tools(self) -> None:
        result = await self._transport.send("tools/list", {})

        tools_data = result.get("tools", []) if isinstance(result, dict) else []
        self._tools = [
            McpToolInfo(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {"type": "object", "properties": {}}),
                server_name=self._config.name,
            )
            for t in tools_data
        ]
        logger.info(
            "MCP server '%s': discovered %d tool(s): %s",
            self._config.name,
            len(self._tools),
            [t.name for t in self._tools],
        )
