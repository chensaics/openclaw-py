from __future__ import annotations

from typing import Any


def run(
    payload: dict[str, Any] | None = None,
    *,
    config: dict[str, Any] | None = None,
    skill_key: str = "mcp-admin",
) -> dict[str, Any]:
    payload = payload or {}
    target = str(payload.get("target", "")).strip()
    tools = (config or {}).get("tools")
    mcp_servers = tools.get("mcpServers") if isinstance(tools, dict) else {}
    configured = sorted(mcp_servers.keys()) if isinstance(mcp_servers, dict) else []
    return {
        "skill": skill_key,
        "status": "ok",
        "summary": "MCP admin script runtime ready.",
        "target": target,
        "configured_servers": configured,
    }
