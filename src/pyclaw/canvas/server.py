"""Canvas host HTTP server — serves A2UI and user canvas files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pyclaw.canvas.handler import (
    A2UI_PATH,
    CANVAS_HOST_PATH,
    CANVAS_WS_PATH,
    DEFAULT_INDEX_HTML,
    guess_content_type,
    inject_canvas_live_reload,
    resolve_file_within_root,
)
from pyclaw.constants.runtime import DEFAULT_BRIDGE_PORT, DEFAULT_GATEWAY_BIND

logger = logging.getLogger(__name__)


class CanvasHostServer:
    """Serves A2UI bundle and user canvas with WebSocket live-reload."""

    def __init__(
        self,
        canvas_root: Path | None = None,
        a2ui_root: Path | None = None,
        host: str = DEFAULT_GATEWAY_BIND,
        port: int = DEFAULT_BRIDGE_PORT,
    ) -> None:
        self._canvas_root = canvas_root
        self._a2ui_root = a2ui_root
        self._host = host
        self._port = port
        self._ws_clients: list[Any] = []
        self._runner: Any = None

    async def start(self) -> None:
        try:
            from aiohttp import web
        except ImportError:
            raise RuntimeError("aiohttp required: pip install aiohttp")

        app = web.Application()
        app.router.add_get(CANVAS_WS_PATH, self._handle_ws)
        app.router.add_get(f"{A2UI_PATH}/{{path:.*}}", self._handle_a2ui)
        app.router.add_get(f"{CANVAS_HOST_PATH}/{{path:.*}}", self._handle_canvas)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        logger.info("Canvas host on %s:%d", self._host, self._port)

    async def stop(self) -> None:
        for ws in self._ws_clients:
            await ws.close()
        self._ws_clients.clear()
        if self._runner:
            await self._runner.cleanup()

    async def notify_reload(self) -> None:
        """Notify all connected WebSocket clients to reload."""
        for ws in list(self._ws_clients):
            try:
                await ws.send_str("reload")
            except Exception:
                self._ws_clients.remove(ws)

    async def _handle_ws(self, request: Any) -> Any:
        from aiohttp import web

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.append(ws)
        try:
            async for _msg in ws:
                pass  # only server→client messages
        finally:
            self._ws_clients.remove(ws)
        return ws

    async def _handle_a2ui(self, request: Any) -> Any:
        from aiohttp import web

        if not self._a2ui_root:
            return web.Response(status=404, text="A2UI root not configured")

        path = request.match_info.get("path", "index.html") or "index.html"
        file = resolve_file_within_root(self._a2ui_root, path)
        if not file:
            return web.Response(status=404)

        content = file.read_bytes()
        ct = guess_content_type(file)

        if ct == "text/html":
            html = content.decode("utf-8", errors="replace")
            html = inject_canvas_live_reload(html)
            return web.Response(text=html, content_type=ct)

        return web.Response(body=content, content_type=ct)

    async def _handle_canvas(self, request: Any) -> Any:
        from aiohttp import web

        if not self._canvas_root:
            return web.Response(text=DEFAULT_INDEX_HTML, content_type="text/html")

        path = request.match_info.get("path", "index.html") or "index.html"
        file = resolve_file_within_root(self._canvas_root, path)
        if not file:
            if path.endswith((".js", ".css", ".png", ".jpg", ".svg", ".woff2")):
                return web.Response(status=404)
            # SPA fallback
            index = self._canvas_root / "index.html"
            if index.is_file():
                html = index.read_text("utf-8")
                html = inject_canvas_live_reload(html)
                return web.Response(text=html, content_type="text/html")
            return web.Response(text=DEFAULT_INDEX_HTML, content_type="text/html")

        content = file.read_bytes()
        ct = guess_content_type(file)

        if ct == "text/html":
            html = content.decode("utf-8", errors="replace")
            html = inject_canvas_live_reload(html)
            return web.Response(text=html, content_type=ct)

        return web.Response(body=content, content_type=ct)


async def start_canvas_host(
    canvas_root: Path | None = None,
    a2ui_root: Path | None = None,
    host: str = DEFAULT_GATEWAY_BIND,
    port: int = DEFAULT_BRIDGE_PORT,
) -> CanvasHostServer:
    server = CanvasHostServer(canvas_root=canvas_root, a2ui_root=a2ui_root, host=host, port=port)
    await server.start()
    return server
