"""CLI command: start the gateway server."""

from __future__ import annotations

import typer

from pyclaw.constants.env import AUTH_TOKEN_ENV_VARS
from pyclaw.constants.runtime import DEFAULT_GATEWAY_BIND, DEFAULT_GATEWAY_PORT


def gateway_command(
    port: int = typer.Option(DEFAULT_GATEWAY_PORT, help="Port to listen on."),
    bind: str = typer.Option(DEFAULT_GATEWAY_BIND, help="Address to bind to."),
    auth_token: str | None = typer.Option(None, envvar=AUTH_TOKEN_ENV_VARS, help="Auth token."),
) -> None:
    """Start the pyclaw gateway server."""
    import uvicorn

    from pyclaw.gateway.server import create_gateway_app

    server = create_gateway_app(auth_token=auth_token)
    typer.echo(f"Starting pyclaw gateway on {bind}:{port}")
    uvicorn.run(server.app, host=bind, port=port, log_level="info")
