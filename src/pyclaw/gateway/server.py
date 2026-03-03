"""Gateway server — FastAPI application with WebSocket endpoint.

Provides the main gateway that native apps (macOS, iOS, Android) and
the web UI connect to via WebSocket protocol v3.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from pyclaw.gateway.protocol.frames import (
    PROTOCOL_VERSION,
    EventFrame,
    RequestFrame,
    ResponseFrame,
)

logger = logging.getLogger("pyclaw.gateway")

MethodHandler = Callable[
    [dict[str, Any] | None, "GatewayConnection"],
    Coroutine[Any, Any, Any],
]


class GatewayConnection:
    """Represents a single WebSocket client connection."""

    def __init__(self, ws: WebSocket, server: GatewayServer) -> None:
        self.ws = ws
        self.server = server
        self.authenticated = False
        self.client_name: str | None = None
        self.connected_at = time.time()
        self._event_seq = 0
        self.message_channel: str = ""
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in ws.scope.get("headers", [])}
        self.message_channel = headers.get("message-channel") or headers.get("x-message-channel") or ""

    async def send_response(self, response: ResponseFrame) -> None:
        await self.ws.send_json(response.to_dict())

    async def send_event(self, event: str, payload: Any = None) -> None:
        self._event_seq += 1
        frame = EventFrame(event=event, payload=payload, seq=self._event_seq)
        await self.ws.send_json(frame.to_dict())

    async def send_ok(self, frame_id: str, payload: Any = None) -> None:
        await self.send_response(ResponseFrame.ok_response(frame_id, payload))

    async def send_error(self, frame_id: str, code: str, message: str, **kwargs: Any) -> None:
        await self.send_response(ResponseFrame.error_response(frame_id, code, message, **kwargs))


class GatewayServer:
    """Central gateway server managing connections and method dispatch."""

    def __init__(self, *, auth_token: str | None = None, config_path: str | None = None) -> None:
        self.app = FastAPI(title="pyclaw Gateway", docs_url=None, redoc_url=None)
        self.auth_token = auth_token
        self.config_path = config_path
        self.connections: list[GatewayConnection] = []
        self._handlers: dict[str, MethodHandler] = {}
        self._started_at: float = 0.0
        self._channel_health_check_interval: float = 15.0  # minutes
        self._channel_health_monitor: Any = None

        self._setup_routes()

    def register_handler(self, method: str, handler: MethodHandler) -> None:
        self._handlers[method] = handler

    def register_handlers(self, handlers: dict[str, MethodHandler]) -> None:
        self._handlers.update(handlers)

    def _setup_routes(self) -> None:
        @self.app.get("/health")
        async def health() -> JSONResponse:
            channels_healthy = 0
            if self._channel_health_monitor:
                from pyclaw.gateway.channel_health import HealthStatus
                statuses = self._channel_health_monitor.get_all_statuses()
                channels_healthy = sum(1 for s in statuses.values() if s == HealthStatus.HEALTHY)
            uptime = time.time() - self._started_at if self._started_at else 0
            return JSONResponse({
                "status": "ok",
                "protocol": PROTOCOL_VERSION,
                "channels_healthy": channels_healthy,
                "uptime": round(uptime, 1),
            })

        @self.app.websocket("/")
        async def websocket_endpoint(ws: WebSocket) -> None:
            await ws.accept()
            conn = GatewayConnection(ws, self)
            self.connections.append(conn)
            try:
                await self._handle_connection(conn)
            except WebSocketDisconnect:
                pass
            finally:
                self.connections.remove(conn)

        @self.app.on_event("startup")
        async def _record_startup() -> None:
            self._started_at = time.time()

    def reload_channel_health_config(self) -> None:
        """Hot-reload channelHealthCheckMinutes from config without full restart."""
        if not self.config_path:
            return
        try:
            from pathlib import Path
            import json5
            path = Path(self.config_path)
            if not path.exists():
                return
            raw = path.read_text(encoding="utf-8")
            data = json5.loads(raw)
            gw = data.get("gateway") or {}
            if isinstance(gw, dict):
                minutes = gw.get("channelHealthCheckMinutes") or gw.get("channel_health_check_minutes")
                if minutes is not None:
                    self._channel_health_check_interval = float(minutes)
                    logger.info("channelHealthCheckMinutes reloaded: %s", self._channel_health_check_interval)
        except Exception:
            logger.debug("channelHealthCheck reload skipped", exc_info=True)

    async def _handle_connection(self, conn: GatewayConnection) -> None:
        """Process incoming WebSocket frames for a connection."""
        while True:
            try:
                raw = await conn.ws.receive_text()
            except WebSocketDisconnect:
                return

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            frame = RequestFrame.from_dict(data)
            if not frame:
                continue

            # First message must be "connect"
            if not conn.authenticated and frame.method != "connect":
                await conn.send_error(frame.id, "auth_required", "First message must be 'connect'.")
                continue

            handler = self._handlers.get(frame.method)
            if handler:
                try:
                    await handler(frame.params, conn)
                    # If handler didn't send a response, we don't auto-respond
                    # (handlers are responsible for sending their own response)
                except Exception as e:
                    logger.exception("Handler error for %s", frame.method)
                    await conn.send_error(
                        frame.id,
                        "internal_error",
                        str(e),
                    )
            else:
                await conn.send_error(
                    frame.id,
                    "unknown_method",
                    f"Unknown method: {frame.method}",
                )

    async def broadcast_event(self, event: str, payload: Any = None) -> None:
        """Send an event to all connected authenticated clients."""
        for conn in self.connections:
            if conn.authenticated:
                try:
                    await conn.send_event(event, payload)
                except Exception:
                    pass


def create_gateway_app(
    *,
    auth_token: str | None = None,
    config_path: str | None = None,
) -> GatewayServer:
    """Create a fully configured gateway server with all default handlers."""
    from pyclaw.gateway.methods import register_core_handlers

    server = GatewayServer(auth_token=auth_token, config_path=config_path)
    register_core_handlers(server, config_path=config_path)
    _load_plugins(server)
    _start_config_watcher(server, config_path)
    return server


def _load_plugins(server: GatewayServer) -> None:
    """Discover and register third-party plugins via entry_points."""
    try:
        from pyclaw.plugins.loader import PluginLoader

        loader = PluginLoader()
        plugins = loader.load_from_entry_points()
        for plugin in plugins:
            if plugin.gateway_methods:
                server.register_handlers(plugin.gateway_methods)
            logger.info(
                "Plugin loaded: %s v%s (%d methods, %d tools)",
                plugin.name,
                plugin.version,
                len(plugin.gateway_methods),
                len(plugin.tools),
            )
    except Exception:
        logger.debug("Plugin loading skipped", exc_info=True)


def _start_config_watcher(server: GatewayServer, config_path: str | None) -> None:
    """Start background config file watcher if a config path is known."""
    import asyncio

    if not config_path:
        return

    try:
        from pyclaw.gateway.config_reload import ConfigFileWatcher, WatcherConfig

        watcher = ConfigFileWatcher(WatcherConfig(config_path=config_path))

        def _on_change(diff: object) -> None:
            logger.info("Config change detected (%s)", diff)

        watcher.on_change(_on_change)
        watcher.start()
        server._config_watcher = watcher  # type: ignore[attr-defined]

        async def _poll_loop() -> None:
            while watcher.is_running:
                watcher.check()
                await asyncio.sleep(watcher._config.poll_interval_s)

        @server.app.on_event("startup")
        async def _start_watcher() -> None:
            asyncio.create_task(_poll_loop())

        @server.app.on_event("shutdown")
        async def _stop_watcher() -> None:
            watcher.stop()

    except Exception:
        logger.debug("Config watcher init skipped", exc_info=True)
