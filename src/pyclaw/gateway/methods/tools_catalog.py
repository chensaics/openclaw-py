"""Gateway methods: tools.catalog — list available tools and metadata."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection

from pyclaw.agents.tools.registry import ToolRegistry, create_default_tools


async def _handle_tools_catalog(
    params: dict[str, Any] | None,
    conn: GatewayConnection,
) -> dict[str, Any]:
    """Return the catalog of available tools with their schemas."""
    registry = create_default_tools()

    tools = []
    for tool in registry.all():
        entry: dict[str, Any] = {
            "name": tool.name,
            "description": tool.description,
        }
        if hasattr(tool, "owner_only"):
            entry["ownerOnly"] = tool.owner_only
        if hasattr(tool, "schema") and tool.schema:
            entry["schema"] = tool.schema
        tools.append(entry)

    return {"tools": tools, "count": len(tools)}


async def _handle_tools_list(
    params: dict[str, Any] | None,
    conn: GatewayConnection,
) -> dict[str, Any]:
    """Return a simple list of tool names."""
    registry = create_default_tools()
    return {"tools": registry.names()}


def create_tools_handlers() -> dict[str, Any]:
    return {
        "tools.catalog": _handle_tools_catalog,
        "tools.list": _handle_tools_list,
    }
