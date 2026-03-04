"""Channel status panel — displays connection status, capabilities, and metrics.

Shows each configured channel with catalog-driven capability badges,
runtime metrics (messages sent/failed), and color-coded status indicators.
Works across Web, Desktop, and Mobile (Flet) targets.
"""

from __future__ import annotations

from typing import Any

import flet as ft

from pyclaw.ui.i18n import t

# Icon mapping — covers all known channels
_ICON_MAP: dict[str, str] = {
    "telegram": ft.Icons.TELEGRAM,
    "discord": ft.Icons.DISCORD,
    "slack": ft.Icons.CHAT,
    "whatsapp": ft.Icons.PHONE_ANDROID,
    "signal": ft.Icons.SECURITY,
    "imessage": ft.Icons.MESSAGE,
    "feishu": ft.Icons.BUSINESS,
    "matrix": ft.Icons.GRID_VIEW,
    "irc": ft.Icons.TERMINAL,
    "msteams": ft.Icons.GROUPS,
    "googlechat": ft.Icons.CHAT_BUBBLE,
    "dingtalk": ft.Icons.NOTIFICATIONS,
    "qq": ft.Icons.QUESTION_ANSWER,
    "twitch": ft.Icons.LIVE_TV,
    "line": ft.Icons.FORUM,
    "mattermost": ft.Icons.DEVELOPER_BOARD,
    "bluebubbles": ft.Icons.BUBBLE_CHART,
    "nostr": ft.Icons.PUBLIC,
    "voice_call": ft.Icons.PHONE,
    "webchat": ft.Icons.WEB,
}

_STATUS_COLORS: dict[str, str] = {
    "connected": ft.Colors.GREEN,
    "running": ft.Colors.GREEN,
    "configured": ft.Colors.AMBER,
    "disconnected": ft.Colors.RED,
    "error": ft.Colors.RED,
    "disabled": ft.Colors.GREY,
    "stopped": ft.Colors.AMBER,
    "unknown": ft.Colors.GREY,
}

_CAPABILITY_LABELS: list[tuple[str, str, str]] = [
    ("typing", "T", "Typing indicator"),
    ("reactions", "R", "Reactions"),
    ("threads", "Th", "Threads"),
    ("editing", "E", "Message editing"),
    ("buttons", "B", "Buttons/actions"),
    ("pins", "P", "Pins"),
]


class ChannelStatusPanel(ft.Column):
    """Panel showing configured channels with capabilities and metrics."""

    def __init__(self, on_refresh: Any = None) -> None:
        from pyclaw.ui.components import page_header

        self._on_refresh = on_refresh
        self._channel_list = ft.ListView(expand=True, spacing=6)
        self._summary_row = ft.Row(spacing=16)

        header = page_header(
            ft.Icons.LINK, t("channels.title"),
            [ft.IconButton(
                icon=ft.Icons.REFRESH, tooltip=t("channels.refresh"),
                icon_size=20, on_click=self._handle_refresh,
            )],
        )

        super().__init__(
            controls=[
                header,
                ft.Container(content=self._summary_row, padding=ft.padding.symmetric(horizontal=16)),
                self._channel_list,
            ],
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

    def update_channels(self, channels: list[dict[str, Any]]) -> None:
        """Refresh the channel list display with capability badges and metrics."""
        self._channel_list.controls.clear()

        total = len(channels)
        running = sum(1 for c in channels if c.get("running") or c.get("status") == "running")
        configured = sum(1 for c in channels if c.get("status") == "configured")

        self._summary_row.controls = [
            self._stat_chip(f"{total}", "Total"),
            self._stat_chip(f"{running}", "Running", ft.Colors.GREEN),
            self._stat_chip(f"{configured}", "Configured", ft.Colors.AMBER),
        ]
        self._safe_update(self._summary_row)

        if not channels:
            from pyclaw.ui.components import empty_state
            self._channel_list.controls.append(
                empty_state(ft.Icons.LINK_OFF, t("channels.no_configured")),
            )
        else:
            for ch in channels:
                self._channel_list.controls.append(self._build_channel_tile(ch))

        self._safe_update(self._channel_list)

    @staticmethod
    def _stat_chip(value: str, label: str, color: str = ft.Colors.ON_SURFACE_VARIANT) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(value, size=18, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(label, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=4),
        )

    def _build_channel_tile(self, ch: dict[str, Any]) -> ft.Control:
        cid = ch.get("id", ch.get("name", "unknown"))
        display_name = ch.get("display_name", ch.get("name", cid)).title()
        status = ch.get("status", "unknown")
        color = _STATUS_COLORS.get(status, ft.Colors.GREY)
        ch_color = ch.get("color", "")
        icon = _ICON_MAP.get(cid.lower(), ft.Icons.LINK)

        capabilities = ch.get("capabilities", {})
        cap_badges = self._build_capability_badges(capabilities)

        metrics = ch.get("metrics", {})
        metrics_row = self._build_metrics_row(metrics)

        info_col_children: list[ft.Control] = [
            ft.Text(display_name, size=14, weight=ft.FontWeight.BOLD),
            ft.Text(
                status.replace("_", " ").title(),
                size=11,
                color=color,
            ),
        ]
        if cap_badges:
            info_col_children.append(ft.Row(cap_badges, spacing=4, wrap=True))
        if metrics_row:
            info_col_children.append(metrics_row)

        from pyclaw.ui.theme import get_theme

        theme = get_theme()
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=22, color=ch_color or color),
                    ft.Column(
                        info_col_children,
                        spacing=3,
                        expand=True,
                        tight=True,
                    ),
                    ft.Container(
                        width=10, height=10,
                        border_radius=ft.border_radius.all(5),
                        bgcolor=color,
                    ),
                ],
                spacing=10,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border_radius=ft.border_radius.all(theme.card_border_radius),
            bgcolor=theme.colors.surface_container,
            border=ft.border.all(0.5, theme.colors.border),
        )

    @staticmethod
    def _build_capability_badges(capabilities: dict[str, Any]) -> list[ft.Control]:
        if not capabilities:
            return []
        badges: list[ft.Control] = []
        for key, short, tooltip_text in _CAPABILITY_LABELS:
            supported = capabilities.get(key, False)
            if supported:
                badges.append(
                    ft.Tooltip(
                        message=tooltip_text,
                        content=ft.Container(
                            content=ft.Text(
                                short, size=9, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.ON_PRIMARY,
                            ),
                            bgcolor=ft.Colors.PRIMARY,
                            padding=ft.padding.symmetric(horizontal=5, vertical=2),
                            border_radius=ft.border_radius.all(4),
                        ),
                    )
                )
        return badges

    @staticmethod
    def _build_metrics_row(metrics: dict[str, Any]) -> ft.Control | None:
        if not metrics:
            return None
        sent = metrics.get("messages_sent", 0)
        failed = metrics.get("messages_failed", 0)
        parts: list[ft.Control] = []
        if sent:
            parts.append(ft.Text(f"{sent} sent", size=10, color=ft.Colors.GREEN))
        if failed:
            parts.append(ft.Text(f"{failed} failed", size=10, color=ft.Colors.RED))
        if not parts:
            return None
        return ft.Row(parts, spacing=8)

    async def _handle_refresh(self, e: Any) -> None:
        if self._on_refresh:
            await self._on_refresh()

    def _safe_update(self, control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass
