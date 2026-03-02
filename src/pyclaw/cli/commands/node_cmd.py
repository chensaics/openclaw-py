"""CLI command for running a node host."""

from __future__ import annotations

import asyncio

import typer


def node_run(
    gateway_url: str = "ws://127.0.0.1:18789/ws",
    auth_token: str | None = None,
    node_id: str = "",
) -> None:
    """Start a headless node host connecting to the gateway."""
    from pyclaw.node_host.runner import run_node_host

    typer.echo(f"Starting node host → {gateway_url}")
    asyncio.run(run_node_host(gateway_url=gateway_url, auth_token=auth_token, node_id=node_id))
