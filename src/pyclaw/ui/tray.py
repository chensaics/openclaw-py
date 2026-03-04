"""System tray icon for macOS/Windows/Linux.

Uses pystray for the menu bar / system tray icon,
and launches the Flet app on "Open" or "Show Chat".
Provides quick actions: new chat, toggle theme, mute notifications.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from pyclaw.ui.i18n import t


_notifications_muted = False


def is_notifications_muted() -> bool:
    """Check whether tray notifications are muted."""
    return _notifications_muted


def create_tray_icon(
    *,
    on_open: Any = None,
    on_quit: Any = None,
    on_new_session: Callable[[], None] | None = None,
    on_toggle_theme: Callable[[], None] | None = None,
) -> Any:
    """Create a system tray icon with pyclaw branding and quick actions."""
    import pystray

    icon_image = _generate_icon()

    def _toggle_mute(icon: Any, item: Any) -> None:
        global _notifications_muted
        _notifications_muted = not _notifications_muted

    def _mute_label(item: Any) -> str:
        return t("tray.unmute", default="Unmute Notifications") if _notifications_muted else t("tray.mute", default="Mute Notifications")

    def _mute_checked(item: Any) -> bool:
        return _notifications_muted

    _noop: Callable[..., None] = lambda *a: None

    menu = pystray.Menu(
        pystray.MenuItem(t("tray.open"), on_open or _noop, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            t("tray.new_session", default="New Chat"),
            (lambda icon, item: on_new_session()) if on_new_session else _noop,
        ),
        pystray.MenuItem(
            t("tray.toggle_theme", default="Toggle Theme"),
            (lambda icon, item: on_toggle_theme()) if on_toggle_theme else _noop,
        ),
        pystray.MenuItem(
            _mute_label,
            _toggle_mute,
            checked=_mute_checked,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(t("tray.quit"), on_quit or _noop),
    )

    icon = pystray.Icon("pyclaw", icon_image, "pyclaw", menu)
    return icon


def run_tray_with_app(
    *,
    on_new_session: Callable[[], None] | None = None,
    on_toggle_theme: Callable[[], None] | None = None,
) -> None:
    """Run the system tray icon alongside the Flet app."""

    def on_open(icon: Any, item: Any) -> None:
        from pyclaw.ui.app import run_app

        threading.Thread(target=run_app, daemon=True).start()

    def on_quit(icon: Any, item: Any) -> None:
        icon.stop()

    icon = create_tray_icon(
        on_open=on_open,
        on_quit=on_quit,
        on_new_session=on_new_session,
        on_toggle_theme=on_toggle_theme,
    )
    icon.run()


def _generate_icon() -> Any:
    """Generate a simple tray icon image."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.ellipse([2, 2, size - 2, size - 2], fill=(59, 130, 246, 255))

    try:
        from PIL import ImageFont

        font = ImageFont.load_default(size=20)
        draw.text((12, 18), "PC", fill=(255, 255, 255, 255), font=font)
    except Exception:
        draw.text((16, 20), "PC", fill=(255, 255, 255, 255))

    return img
