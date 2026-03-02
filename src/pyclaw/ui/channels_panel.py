"""Channel status panel — displays connection status for each configured channel."""

from __future__ import annotations

from typing import Any

import flet as ft

from pyclaw.ui.i18n import t


class ChannelStatusPanel(ft.Column):
    """Panel showing configured channels and their connection status."""

    def __init__(self, on_refresh: Any = None) -> None:
        self._on_refresh = on_refresh
        self._channel_list = ft.ListView(expand=True, spacing=4)

        header = ft.Row(
            [
                ft.Text(t("channels.title"), size=18, weight=ft.FontWeight.BOLD, expand=True),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    tooltip=t("channels.refresh"),
                    icon_size=20,
                    on_click=self._handle_refresh,
                ),
            ]
        )

        super().__init__(
            controls=[
                header,
                ft.Divider(height=1),
                self._channel_list,
            ],
            expand=True,
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

    def update_channels(self, channels: list[dict[str, Any]]) -> None:
        """Refresh the channel list display."""
        self._channel_list.controls.clear()

        if not channels:
            self._channel_list.controls.append(
                ft.Container(
                    content=ft.Text(
                        t("channels.no_configured"),
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    padding=ft.padding.all(16),
                ),
            )
        else:
            for ch in channels:
                self._channel_list.controls.append(self._build_channel_tile(ch))

        try:
            if self._channel_list.page:
                self._channel_list.update()
        except RuntimeError:
            pass

    def _build_channel_tile(self, ch: dict[str, Any]) -> ft.Control:
        name = ch.get("name", "unknown")
        status = ch.get("status", "unknown")
        enabled = ch.get("enabled", False)

        status_colors = {
            "connected": ft.Colors.GREEN,
            "running": ft.Colors.GREEN,
            "disconnected": ft.Colors.RED,
            "error": ft.Colors.RED,
            "disabled": ft.Colors.GREY,
            "unknown": ft.Colors.AMBER,
        }
        color = status_colors.get(status, ft.Colors.GREY)

        icon_map = {
            "telegram": ft.Icons.TELEGRAM,
            "discord": ft.Icons.DISCORD,
            "slack": ft.Icons.CHAT,
            "whatsapp": ft.Icons.PHONE_ANDROID,
            "signal": ft.Icons.SECURITY,
            "imessage": ft.Icons.MESSAGE,
        }
        icon = icon_map.get(name.lower(), ft.Icons.LINK)

        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=20, color=color),
                    ft.Column(
                        [
                            ft.Text(name.title(), size=14, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"{t('channels.enabled') if enabled else t('channels.disabled')} — {status}",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                        tight=True,
                    ),
                    ft.Container(
                        width=10,
                        height=10,
                        border_radius=ft.border_radius.all(5),
                        bgcolor=color,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border_radius=ft.border_radius.all(8),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

    async def _handle_refresh(self, e: Any) -> None:
        if self._on_refresh:
            await self._on_refresh()
