"""Canvas file resolution and live-reload injection."""

from __future__ import annotations

import mimetypes
from pathlib import Path

A2UI_PATH = "/__pyclaw__/a2ui"
CANVAS_HOST_PATH = "/__pyclaw__/canvas"
CANVAS_WS_PATH = "/__pyclaw__/ws"

LIVE_RELOAD_SCRIPT = """
<script>
(function() {
  var ws = new WebSocket(
    (location.protocol === 'https:' ? 'wss' : 'ws') +
    '://' + location.host + '/__pyclaw__/ws'
  );
  ws.onmessage = function(e) {
    if (e.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() { location.reload(); }, 2000);
  };
  // Mobile bridge
  window.pyclawSendUserAction = function(action) {
    try {
      if (window.webkit && window.webkit.messageHandlers) {
        window.webkit.messageHandlers.pyclaw.postMessage(action);
      } else if (window.PyClawBridge) {
        window.PyClawBridge.postMessage(JSON.stringify(action));
      }
    } catch(e) {}
  };
})();
</script>
"""

DEFAULT_INDEX_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>pyclaw Canvas</title></head>
<body style="font-family: system-ui; padding: 2em; text-align: center; color: #666;">
  <h2>pyclaw Canvas</h2>
  <p>No canvas content yet. Place files in the canvas directory.</p>
</body>
</html>
"""


def resolve_file_within_root(root: Path, url_path: str) -> Path | None:
    """Safely resolve a URL path within *root*, preventing directory traversal."""
    clean = url_path.lstrip("/").replace("..", "")
    target = (root / clean).resolve()
    if not str(target).startswith(str(root.resolve())):
        return None
    if target.is_file():
        return target
    # Try index.html
    index = target / "index.html"
    if index.is_file():
        return index
    return None


def inject_canvas_live_reload(html: str) -> str:
    """Inject live-reload and mobile bridge scripts into HTML."""
    if "</head>" in html:
        return html.replace("</head>", LIVE_RELOAD_SCRIPT + "</head>")
    if "</body>" in html:
        return html.replace("</body>", LIVE_RELOAD_SCRIPT + "</body>")
    return html + LIVE_RELOAD_SCRIPT


def guess_content_type(path: Path) -> str:
    ct, _ = mimetypes.guess_type(str(path))
    return ct or "application/octet-stream"
