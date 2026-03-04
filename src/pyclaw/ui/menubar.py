"""Desktop menubar — native menu bar for macOS/Windows/Linux Flet apps.

Provides a top-level menu bar with File, Edit, View, and Help menus.
Integrates with the theme toggle, session management, and app lifecycle.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)


def build_menubar(
    *,
    on_new_session: Callable[[], Coroutine[Any, Any, None]] | None = None,
    on_export: Callable[[], Coroutine[Any, Any, None]] | None = None,
    on_quit: Callable[[], None] | None = None,
    on_toggle_theme: Callable[[], None] | None = None,
    on_show_about: Callable[[], None] | None = None,
) -> Any:
    """Build a Flet MenuBar for the desktop window.

    Returns a ``ft.MenuBar`` control, or ``None`` if Flet is unavailable.
    """
    try:
        import flet as ft
    except ImportError:
        return None

    async def _wrap(handler: Any) -> None:
        if handler and callable(handler):
            try:
                await handler()
            except TypeError:
                handler()

    def _make_click(handler: Any) -> Callable[[Any], Any] | None:
        if handler is None:
            return None

        async def _on_click(e: Any) -> None:
            await _wrap(handler)

        return _on_click

    file_menu = ft.SubmenuButton(
        content=ft.Text("File"),
        controls=[
            ft.MenuItemButton(
                content=ft.Text("New Session"),
                leading=ft.Icon(ft.Icons.ADD),
                on_click=_make_click(on_new_session),
            ),
            ft.MenuItemButton(
                content=ft.Text("Export Chat"),
                leading=ft.Icon(ft.Icons.DOWNLOAD),
                on_click=_make_click(on_export),
            ),
            ft.Divider(height=1),
            ft.MenuItemButton(
                content=ft.Text("Quit"),
                leading=ft.Icon(ft.Icons.EXIT_TO_APP),
                on_click=lambda e: on_quit() if on_quit else None,
            ),
        ],
    )

    view_menu = ft.SubmenuButton(
        content=ft.Text("View"),
        controls=[
            ft.MenuItemButton(
                content=ft.Text("Toggle Theme"),
                leading=ft.Icon(ft.Icons.BRIGHTNESS_6),
                on_click=lambda e: on_toggle_theme() if on_toggle_theme else None,
            ),
        ],
    )

    help_menu = ft.SubmenuButton(
        content=ft.Text("Help"),
        controls=[
            ft.MenuItemButton(
                content=ft.Text("About"),
                leading=ft.Icon(ft.Icons.INFO_OUTLINE),
                on_click=lambda e: on_show_about() if on_show_about else None,
            ),
            ft.MenuItemButton(
                content=ft.Text("Documentation"),
                leading=ft.Icon(ft.Icons.BOOK),
                on_click=lambda e: e.page.launch_url("https://docs.openclaw.ai") if e.page else None,
            ),
        ],
    )

    return ft.MenuBar(
        controls=[file_menu, view_menu, help_menu],
    )
