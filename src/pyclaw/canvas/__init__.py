"""Canvas Host — A2UI static file server and WebSocket live-reload.

Ported from ``src/canvas-host/``.
"""

from pyclaw.canvas.handler import resolve_file_within_root
from pyclaw.canvas.server import CanvasHostServer, start_canvas_host

__all__ = [
    "CanvasHostServer",
    "resolve_file_within_root",
    "start_canvas_host",
]
