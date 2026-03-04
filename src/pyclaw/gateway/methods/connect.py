"""connect — WebSocket handshake / authentication handler."""

from __future__ import annotations

import platform
from typing import TYPE_CHECKING, Any

from pyclaw import __version__
from pyclaw.gateway.protocol.frames import PROTOCOL_VERSION

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, GatewayServer, MethodHandler


def create_connect_handler(server: GatewayServer) -> MethodHandler:
    async def handle_connect(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        params = params or {}

        # Protocol version negotiation
        min_proto = params.get("minProtocol", 1)
        max_proto = params.get("maxProtocol", PROTOCOL_VERSION)
        if max_proto < PROTOCOL_VERSION or min_proto > PROTOCOL_VERSION:
            await conn.send_error(
                "connect",
                "protocol_mismatch",
                f"Server requires protocol v{PROTOCOL_VERSION}, client supports v{min_proto}-v{max_proto}.",
            )
            return

        # Authentication
        if server.auth_token:
            auth = params.get("auth", {})
            token = auth.get("token", "")
            if token != server.auth_token:
                await conn.send_error("connect", "auth_failed", "Invalid authentication token.")
                return

        conn.authenticated = True
        conn.client_name = params.get("clientName", "unknown")

        await conn.send_ok(
            "connect",
            {
                "protocol": PROTOCOL_VERSION,
                "server": {
                    "name": "pyclaw-py",
                    "version": __version__,
                    "platform": platform.system().lower(),
                },
            },
        )

    return handle_connect
