"""CLI MCP subcommands — status and tool listing."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import typer

from pyclaw.terminal.palette import PALETTE


def mcp_status_command(*, output_json: bool = False) -> None:
    """Show status of configured MCP servers."""
    from pyclaw.config.io import load_config

    p = PALETTE
    cfg = load_config()
    tools_cfg = cfg.tools
    mcp_servers = (tools_cfg.mcp_servers if tools_cfg else None) or {}

    if not mcp_servers:
        typer.echo(f"{p.muted}No MCP servers configured.{p.reset}")
        typer.echo("Add servers to your config under tools.mcpServers")
        return

    statuses = asyncio.run(_get_mcp_statuses(mcp_servers))

    if output_json:
        typer.echo(json.dumps(statuses, indent=2))
        return

    typer.echo(f"\n{p.info}MCP Servers:{p.reset}\n")
    for s in statuses:
        icon = f"{p.success}●{p.reset}" if s["connected"] else f"{p.error}●{p.reset}"
        typer.echo(f"  {icon} {s['name']} ({s['transport']})")
        if s["tools"]:
            for t in s["tools"]:
                typer.echo(f"      → {t}")
        elif s["connected"]:
            typer.echo(f"      {p.muted}(no tools){p.reset}")
        if s.get("error"):
            typer.echo(f"      {p.error}{s['error']}{p.reset}")
    typer.echo()


def mcp_list_tools_command(*, server: str | None = None) -> None:
    """List tools from connected MCP servers."""
    from pyclaw.config.io import load_config

    p = PALETTE
    cfg = load_config()
    tools_cfg = cfg.tools
    mcp_servers = (tools_cfg.mcp_servers if tools_cfg else None) or {}

    if not mcp_servers:
        typer.echo(f"{p.muted}No MCP servers configured.{p.reset}")
        return

    if server:
        mcp_servers = {k: v for k, v in mcp_servers.items() if k == server}
        if not mcp_servers:
            typer.echo(f"{p.error}Server '{server}' not found in config.{p.reset}")
            return

    statuses = asyncio.run(_get_mcp_statuses(mcp_servers))

    for s in statuses:
        if not s["connected"]:
            typer.echo(f"{p.error}{s['name']}: not connected{p.reset}")
            continue
        typer.echo(f"\n{p.info}{s['name']}{p.reset} ({s['transport']}):")
        for t in s["tools"]:
            typer.echo(f"  • {t}")


async def _get_mcp_statuses(
    mcp_servers: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    from pyclaw.mcp.registry import McpRegistry

    registry = McpRegistry()
    try:
        await registry.connect_all(mcp_servers)
        return registry.get_status()
    except Exception as exc:
        return [{"name": "error", "connected": False, "tools": [], "transport": "?", "error": str(exc)}]
    finally:
        await registry.disconnect_all()
