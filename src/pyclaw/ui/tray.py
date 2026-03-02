"""System tray icon for macOS/Windows/Linux.

Uses pystray for the menu bar / system tray icon,
and launches the Flet app on "Open" or "Show Chat".
"""

from __future__ import annotations

import threading
from typing import Any

from pyclaw.ui.i18n import t


def create_tray_icon(on_open: Any = None, on_quit: Any = None) -> Any:
    """Create a system tray icon with pyclaw branding."""
    import pystray

    # Generate a simple icon (blue circle with "PC" text)
    icon_image = _generate_icon()

    menu = pystray.Menu(
        pystray.MenuItem(t("tray.open"), on_open or (lambda: None), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(t("tray.quit"), on_quit or (lambda: None)),
    )

    icon = pystray.Icon("pyclaw", icon_image, "pyclaw", menu)
    return icon


def run_tray_with_app() -> None:
    """Run the system tray icon alongside the Flet app."""

    def on_open(icon: Any, item: Any) -> None:
        from pyclaw.ui.app import run_app

        threading.Thread(target=run_app, daemon=True).start()

    def on_quit(icon: Any, item: Any) -> None:
        icon.stop()

    icon = create_tray_icon(on_open=on_open, on_quit=on_quit)
    icon.run()


def _generate_icon() -> Any:
    """Generate a simple tray icon image."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Blue circle
    draw.ellipse([2, 2, size - 2, size - 2], fill=(59, 130, 246, 255))

    try:
        from PIL import ImageFont

        font = ImageFont.load_default(size=20)
        draw.text((12, 18), "PC", fill=(255, 255, 255, 255), font=font)
    except Exception:
        draw.text((16, 20), "PC", fill=(255, 255, 255, 255))

    return img
