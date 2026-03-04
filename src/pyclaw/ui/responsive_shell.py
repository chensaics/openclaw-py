"""Responsive shell — manages NavigationRail / BottomNav / Sidebar switching.

Encapsulates breakpoint-based layout logic so that ``app.py`` only needs
to call ``shell.apply(width)`` on resize.  Follows the Flutter
``ResponsiveShell`` pattern from ``flutter_app/lib/widgets/responsive_shell.dart``.
"""

from __future__ import annotations

import flet as ft

from pyclaw.ui.theme import get_theme


class ResponsiveShell:
    """Manages the responsive layout skeleton of the application.

    Three layout modes based on window width:
    - **Mobile** (< breakpoint_mobile):  Bottom NavigationBar, no rail/sidebar
    - **Tablet** (< breakpoint_tablet):  Collapsed NavigationRail, no sidebar
    - **Desktop** (>= breakpoint_tablet): Full NavigationRail + SessionSidebar
    """

    def __init__(
        self,
        *,
        nav_rail: ft.NavigationRail,
        bottom_nav: ft.NavigationBar,
        session_sidebar: ft.Control,
        sidebar_divider1: ft.VerticalDivider,
        sidebar_divider2: ft.VerticalDivider,
        top_bar: ft.Control | None,
        menubar: ft.Control | None,
        main_content: ft.Control,
    ) -> None:
        self._nav_rail = nav_rail
        self._bottom_nav = bottom_nav
        self._session_sidebar = session_sidebar
        self._divider1 = sidebar_divider1
        self._divider2 = sidebar_divider2
        self._top_bar = top_bar
        self._menubar = menubar
        self._main_content = main_content
        self._current_mode: str = "desktop"

    @property
    def current_mode(self) -> str:
        """Current layout mode: 'mobile', 'tablet', or 'desktop'."""
        return self._current_mode

    def build(self) -> ft.Column:
        """Build the root layout Column containing the desktop row and bottom nav."""
        desktop_row = ft.Row(
            controls=[
                self._nav_rail,
                self._divider1,
                self._session_sidebar,
                self._divider2,
                self._main_content,
            ],
            expand=True,
        )
        return ft.Column(
            controls=[desktop_row, self._bottom_nav],
            expand=True,
            spacing=0,
        )

    def apply(self, width: float) -> None:
        """Apply breakpoint-based layout for the given width."""
        theme = get_theme()
        bp_mobile = theme.breakpoint_mobile
        bp_tablet = theme.breakpoint_tablet

        if width < bp_mobile:
            self._apply_mobile()
        elif width < bp_tablet:
            self._apply_tablet()
        else:
            self._apply_desktop()

    def _apply_mobile(self) -> None:
        self._current_mode = "mobile"
        self._nav_rail.visible = False
        self._divider1.visible = False
        self._session_sidebar.visible = False
        self._divider2.visible = False
        self._bottom_nav.visible = True
        if self._top_bar:
            self._top_bar.visible = True
        if self._menubar:
            self._menubar.visible = False

    def _apply_tablet(self) -> None:
        self._current_mode = "tablet"
        self._nav_rail.visible = True
        self._nav_rail.label_type = ft.NavigationRailLabelType.SELECTED
        self._divider1.visible = True
        self._session_sidebar.visible = False
        self._divider2.visible = False
        self._bottom_nav.visible = False
        if self._top_bar:
            self._top_bar.visible = True
        if self._menubar:
            self._menubar.visible = True

    def _apply_desktop(self) -> None:
        self._current_mode = "desktop"
        self._nav_rail.visible = True
        self._nav_rail.label_type = ft.NavigationRailLabelType.ALL
        self._divider1.visible = True
        self._session_sidebar.visible = True
        self._divider2.visible = True
        self._bottom_nav.visible = False
        if self._top_bar:
            self._top_bar.visible = True
        if self._menubar:
            self._menubar.visible = True
