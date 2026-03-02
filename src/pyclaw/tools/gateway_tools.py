"""Agent tools for gateway control — status, restart, config."""

from __future__ import annotations

from typing import Any


def tool_gateway_status() -> dict[str, Any]:
    """Tool definition for checking gateway status."""
    return {
        "name": "gateway_status",
        "description": "Check the current gateway server status including uptime, connections, and memory.",
        "parameters": {"type": "object", "properties": {}},
    }


def tool_gateway_restart() -> dict[str, Any]:
    """Tool definition for restarting the gateway."""
    return {
        "name": "gateway_restart",
        "description": "Restart the gateway server gracefully.",
        "parameters": {"type": "object", "properties": {}},
    }


def tool_gateway_config() -> dict[str, Any]:
    """Tool definition for reading/writing gateway config."""
    return {
        "name": "gateway_config",
        "description": "Read or update gateway configuration values.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "'get' or 'set'"},
                "key": {"type": "string", "description": "Config key path (e.g., 'gateway.port')"},
                "value": {"type": "string", "description": "New value (for 'set' action)"},
            },
            "required": ["action", "key"],
        },
    }


async def handle_gateway_status(params: dict[str, Any], context: Any = None) -> str:
    """Return current gateway status."""
    import os
    import time

    info_parts = [
        "Gateway Status:",
        f"  PID: {os.getpid()}",
    ]

    if context and hasattr(context, "gateway"):
        gw = context.gateway
        uptime = time.time() - getattr(gw, "start_time", time.time())
        hours = int(uptime // 3600)
        mins = int((uptime % 3600) // 60)
        info_parts.append(f"  Uptime: {hours}h {mins}m")

        conns = len(getattr(gw, "connections", []))
        info_parts.append(f"  Connections: {conns}")

        nodes = len(getattr(gw, "connected_nodes", {}))
        info_parts.append(f"  Nodes: {nodes}")

    try:
        import psutil

        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        info_parts.append(f"  Memory: {mem.rss / 1024 / 1024:.1f} MB")
    except ImportError:
        pass

    return "\n".join(info_parts)


async def handle_gateway_restart(params: dict[str, Any], context: Any = None) -> str:
    """Trigger a graceful gateway restart."""
    if context and hasattr(context, "gateway"):
        gw = context.gateway
        if hasattr(gw, "restart"):
            await gw.restart()
            return "Gateway restart initiated."
    return "Gateway restart not available (no gateway context)."


async def handle_gateway_config(params: dict[str, Any], context: Any = None) -> str:
    """Read or update gateway config."""
    action = params.get("action", "get")
    key = params.get("key", "")

    if action == "get":
        from pyclaw.config.io import load_config

        config = load_config()
        # Dot-path traversal
        value = config
        for part in key.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return f"Key not found: {key}"
        return f"{key} = {value}"

    elif action == "set":
        value = params.get("value", "")
        from pyclaw.config.io import load_config, save_config

        config = load_config()
        parts = key.split(".")
        target = config
        for part in parts[:-1]:
            if isinstance(target, dict):
                target = target.setdefault(part, {})
        if isinstance(target, dict):
            target[parts[-1]] = value
        save_config(config)
        return f"Set {key} = {value}"

    return f"Unknown action: {action}"
