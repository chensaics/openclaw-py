"""CLI commands for daemon/service management (install, uninstall, status)."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import typer


def service_install(
    label: str = "ai.pyclaw.gateway",
    port: int = 18789,
    bind: str = "127.0.0.1",
) -> None:
    """Install the gateway as a system service."""
    from pyclaw.daemon.service import resolve_gateway_service, GatewayServiceInstallArgs

    svc = resolve_gateway_service()
    args = GatewayServiceInstallArgs(
        label=label,
        program=sys.executable,
        arguments=["-m", "pyclaw", "gateway", "run", "--port", str(port), "--bind", bind],
    )

    asyncio.run(svc.install(args))
    typer.echo(f"Service installed: {label}")


def service_uninstall(label: str = "ai.pyclaw.gateway") -> None:
    """Uninstall the gateway service."""
    from pyclaw.daemon.service import resolve_gateway_service

    svc = resolve_gateway_service()
    asyncio.run(svc.uninstall(label))
    typer.echo(f"Service uninstalled: {label}")


def service_status(label: str = "ai.pyclaw.gateway") -> None:
    """Show gateway service status."""
    from pyclaw.daemon.service import resolve_gateway_service

    svc = resolve_gateway_service()
    runtime = asyncio.run(svc.read_runtime(label))
    typer.echo(f"Service: {label}")
    typer.echo(f"  Status: {runtime.status}")
    if runtime.pid:
        typer.echo(f"  PID: {runtime.pid}")
    if runtime.last_exit_code is not None:
        typer.echo(f"  Last exit code: {runtime.last_exit_code}")


def service_restart(label: str = "ai.pyclaw.gateway") -> None:
    """Restart the gateway service."""
    from pyclaw.daemon.service import resolve_gateway_service

    svc = resolve_gateway_service()
    asyncio.run(svc.restart(label))
    typer.echo(f"Service restarted: {label}")


def service_stop(label: str = "ai.pyclaw.gateway") -> None:
    """Stop the gateway service."""
    from pyclaw.daemon.service import resolve_gateway_service

    svc = resolve_gateway_service()
    asyncio.run(svc.stop(label))
    typer.echo(f"Service stopped: {label}")
