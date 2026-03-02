"""CLI command: start the gateway server."""

from __future__ import annotations

import typer


def gateway_command(
    port: int = typer.Option(18789, help="Port to listen on."),
    bind: str = typer.Option("127.0.0.1", help="Address to bind to."),
    auth_token: str | None = typer.Option(None, envvar="PYCLAW_AUTH_TOKEN", help="Auth token."),
) -> None:
    """Start the pyclaw gateway server."""
    import uvicorn

    from pyclaw.gateway.server import create_gateway_app

    server = create_gateway_app(auth_token=auth_token)
    typer.echo(f"Starting pyclaw gateway on {bind}:{port}")
    uvicorn.run(server.app, host=bind, port=port, log_level="info")
