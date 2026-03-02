"""Agent tools for node host management — list/invoke/status.

Integrates with ``gateway.node_command_policy`` for platform-aware command
filtering and capability-based tool generation.
"""

from __future__ import annotations

import json
from typing import Any

from pyclaw.gateway.node_command_policy import (
    NodeCapabilities,
    get_node_tool_definitions,
    is_command_allowed,
)


def tool_nodes_list() -> dict[str, Any]:
    """Tool definition for listing connected node hosts."""
    return {
        "name": "nodes_list",
        "description": "List all connected node hosts and their status.",
        "parameters": {"type": "object", "properties": {}},
    }


def tool_nodes_invoke() -> dict[str, Any]:
    """Tool definition for invoking a command on a remote node."""
    return {
        "name": "nodes_invoke",
        "description": "Execute a command on a remote node host.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Target node identifier"},
                "command": {
                    "type": "string",
                    "description": "Command to execute (e.g., system.run, system.which)",
                },
                "params": {"type": "object", "description": "Command parameters"},
                "timeout_ms": {
                    "type": "integer",
                    "description": "Timeout in milliseconds",
                    "default": 30000,
                },
            },
            "required": ["node_id", "command"],
        },
    }


def get_platform_tools(platform: str, caps: NodeCapabilities | None = None) -> list[dict[str, Any]]:
    """Get tool definitions filtered by platform and optional capabilities."""
    return get_node_tool_definitions(platform, caps)


async def handle_nodes_list(params: dict[str, Any], context: Any = None) -> str:
    """List connected nodes from gateway state."""
    if context and hasattr(context, "gateway"):
        nodes = getattr(context.gateway, "connected_nodes", {})
        if nodes:
            lines = ["Connected nodes:"]
            for nid, info in nodes.items():
                status = info.get("status", "unknown")
                platform = info.get("platform", "unknown")
                lines.append(f"  - {nid}: {status} ({platform})")
            return "\n".join(lines)
    return "No connected nodes."


async def handle_nodes_invoke(params: dict[str, Any], context: Any = None) -> str:
    """Invoke a command on a remote node, respecting command policy."""
    node_id = params.get("node_id", "")
    command = params.get("command", "")

    if not node_id or not command:
        return "Error: node_id and command are required"

    if context and hasattr(context, "gateway"):
        node_info = getattr(context.gateway, "connected_nodes", {}).get(node_id, {})
        platform = node_info.get("platform", "")

        if platform and not is_command_allowed(command, platform):
            return f"Error: command '{command}' not allowed on platform '{platform}'"

        ws = getattr(context.gateway, "node_connections", {}).get(node_id)
        if ws:
            import uuid

            invoke_id = str(uuid.uuid4())[:8]
            msg = {
                "event": "node.invoke.request",
                "payload": {
                    "id": invoke_id,
                    "nodeId": node_id,
                    "command": command,
                    "paramsJSON": json.dumps(params.get("params", {})),
                    "timeoutMs": params.get("timeout_ms", 30000),
                },
            }
            await ws.send(json.dumps(msg))
            return f"Invoke sent to {node_id}: {command} (id={invoke_id})"

    return f"Node {node_id} not connected"
