"""Gateway HTTP control panel — serves a built SPA and bootstrap config.

Ported from ``src/gateway/`` control-ui handling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONTROL_UI_BOOTSTRAP_CONFIG_PATH = "/__pyclaw/control-ui-config.json"

# Security headers
CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "connect-src 'self' ws: wss:; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'"
)


@dataclass
class ControlUiBootstrapConfig:
    base_path: str = "/__control__"
    assistant_name: str = "pyclaw"
    assistant_avatar: str = ""
    assistant_agent_id: str = "main"


def resolve_control_ui_root() -> Path | None:
    """Find the built control UI root. Returns None if not found."""
    # Check common locations
    candidates = [
        Path.home() / ".pyclaw" / "control-ui",
        Path(__file__).parent.parent / "control-ui" / "dist",
    ]
    for c in candidates:
        if (c / "index.html").is_file():
            return c
    return None


def build_security_headers() -> dict[str, str]:
    return {
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": CSP_HEADER,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }


def create_control_ui_routes(
    config: ControlUiBootstrapConfig | None = None,
    ui_root: Path | None = None,
) -> Any:
    """Create FastAPI/aiohttp routes for the control UI.

    Returns an aiohttp.web.Application that can be mounted.
    """
    try:
        from aiohttp import web
    except ImportError:
        raise RuntimeError("aiohttp required: pip install aiohttp")

    if config is None:
        config = ControlUiBootstrapConfig()

    if ui_root is None:
        ui_root = resolve_control_ui_root()

    app = web.Application()

    async def handle_bootstrap_config(request: web.Request) -> web.Response:
        data = {
            "basePath": config.base_path,
            "assistantName": config.assistant_name,
            "assistantAvatar": config.assistant_avatar,
            "assistantAgentId": config.assistant_agent_id,
        }
        return web.json_response(data, headers=build_security_headers())

    async def handle_static(request: web.Request) -> web.Response:
        if not ui_root:
            return web.Response(status=404, text="Control UI not installed")

        path = request.match_info.get("path", "")
        if path == CONTROL_UI_BOOTSTRAP_CONFIG_PATH.lstrip("/"):
            return await handle_bootstrap_config(request)

        from pyclaw.canvas.handler import guess_content_type, resolve_file_within_root

        file = resolve_file_within_root(ui_root, path or "index.html")

        if not file:
            # Static asset → 404; route → SPA fallback
            static_exts = (".js", ".css", ".png", ".jpg", ".svg", ".ico", ".woff2", ".map")
            if any(path.endswith(ext) for ext in static_exts):
                return web.Response(status=404)
            index = ui_root / "index.html"
            if index.is_file():
                return web.Response(
                    text=index.read_text("utf-8"),
                    content_type="text/html",
                    headers=build_security_headers(),
                )
            return web.Response(status=404)

        content = file.read_bytes()
        ct = guess_content_type(file)
        headers = build_security_headers() if ct == "text/html" else {}
        return web.Response(body=content, content_type=ct, headers=headers)

    app.router.add_get("/__pyclaw/control-ui-config.json", handle_bootstrap_config)
    app.router.add_get("/{path:.*}", handle_static)
    app.router.add_get("/", handle_static)

    return app
