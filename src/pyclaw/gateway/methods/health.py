"""health / status — gateway health check handlers."""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

from pyclaw import __version__
from pyclaw.gateway.protocol.frames import PROTOCOL_VERSION

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

_start_time = time.time()


def create_health_handlers() -> dict[str, MethodHandler]:
    async def handle_health(
        params: dict[str, Any] | None, conn: GatewayConnection
    ) -> None:
        await conn.send_ok("health", {
            "status": "ok",
            "version": __version__,
            "protocol": PROTOCOL_VERSION,
            "uptime_seconds": int(time.time() - _start_time),
        })

    async def handle_status(
        params: dict[str, Any] | None, conn: GatewayConnection
    ) -> None:
        await conn.send_ok("status", {
            "status": "ok",
            "connections": len(conn.server.connections),
            "version": __version__,
        })

    return {
        "health": handle_health,
        "status": handle_status,
    }
