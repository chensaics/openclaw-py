"""Overview panel — connection overview with Gateway status and config."""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft

from pyclaw.ui.components import card_tile, page_header, status_chip
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_overview_panel(
    *,
    gateway_client: Any = None,
    config: dict | None = None,
    on_connect: Any = None,
    on_refresh: Any = None,
) -> ft.Column:
    theme = get_theme()
    url_field = ft.TextField(
        label=t("overview.url", default="Gateway URL"),
        value=(config or {}).get("url", "ws://127.0.0.1:18789/"),
        dense=True,
        expand=True,
    )
    token_field = ft.TextField(
        label=t("overview.auth_token", default="Auth Token"),
        value=(config or {}).get("auth_token", "") or "",
        password=True,
        dense=True,
        expand=True,
    )
    status_info = ft.Column(spacing=4, tight=True)
    version_text = ft.Text("", size=12, color=theme.colors.muted)
    uptime_text = ft.Text("", size=12, color=theme.colors.muted)

    async def _fetch_status() -> None:
        if not gateway_client or not gateway_client.connected:
            return
        try:
            health = await gateway_client.call("health", timeout=10.0)
            version_text.value = f"Version: {health.get('version', 'N/A')}"
            uptime_sec = health.get("uptime_seconds", 0)
            if uptime_sec:
                uptime_text.value = f"Uptime: {uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m"
            else:
                uptime_text.value = ""
            if version_text.page:
                version_text.update()
            if uptime_text.page:
                uptime_text.update()
        except Exception:
            version_text.value = ""
            uptime_text.value = ""
            if version_text.page:
                version_text.update()
            if uptime_text.page:
                uptime_text.update()

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _update_status_display() -> None:
        status_info.controls.clear()
        connected = gateway_client and gateway_client.connected
        status_label = (
            t("overview.connected", default="Connected") if connected else t("overview.offline", default="Offline")
        )
        status_color = theme.colors.success if connected else theme.colors.error
        status_info.controls.append(status_chip(status_label, status_color))
        status_info.controls.append(version_text)
        status_info.controls.append(uptime_text)
        _safe_update(status_info)
        if connected:
            _fire_async(_fetch_status)

    connect_btn = ft.ElevatedButton(
        t("overview.connect", default="Connect"),
        icon=ft.Icons.LINK,
        on_click=lambda e: _fire_async(_handle_connect),
    )
    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        icon_size=20,
        on_click=lambda e: _fire_async(_handle_refresh),
    )

    async def _handle_connect() -> None:
        if on_connect:
            cfg = {"url": url_field.value, "auth_token": token_field.value or None}
            await on_connect(cfg)

    async def _handle_refresh() -> None:
        await _fetch_status()
        if on_refresh:
            await on_refresh()

    status_card = card_tile(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.ROUTER, size=22, color=theme.colors.primary),
                        ft.Column(
                            [
                                ft.Text(
                                    t("overview.gateway_status", default="Gateway Status"),
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                status_info,
                            ],
                            spacing=4,
                            expand=True,
                            tight=True,
                        ),
                    ],
                    spacing=12,
                ),
            ],
            spacing=8,
        ),
    )

    config_card = card_tile(
        content=ft.Column(
            [
                ft.Text(t("overview.connection", default="Connection"), size=14, weight=ft.FontWeight.BOLD),
                ft.Row([url_field, token_field], spacing=12),
                ft.Row([connect_btn, refresh_btn], spacing=8),
            ],
            spacing=12,
        ),
    )

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.DASHBOARD,
                t("overview.title", default="Overview"),
                actions=[refresh_btn],
            ),
            ft.Container(
                content=ft.Column(
                    [status_card, config_card],
                    spacing=12,
                ),
                padding=16,
            ),
        ],
        expand=True,
        spacing=0,
    )

    # Local info card — always visible, shows local environment even when offline
    local_info_items: list[ft.Control] = []
    try:
        import platform as _platform

        local_info_items.append(
            ft.Row(
                [
                    ft.Text("Host:", size=12, weight=ft.FontWeight.BOLD, width=100),
                    ft.Text(_platform.node(), size=12),
                ],
                spacing=8,
            )
        )
        local_info_items.append(
            ft.Row(
                [
                    ft.Text("Platform:", size=12, weight=ft.FontWeight.BOLD, width=100),
                    ft.Text(f"{_platform.system()} {_platform.release()}", size=12),
                ],
                spacing=8,
            )
        )
        local_info_items.append(
            ft.Row(
                [
                    ft.Text("Python:", size=12, weight=ft.FontWeight.BOLD, width=100),
                    ft.Text(_platform.python_version(), size=12),
                ],
                spacing=8,
            )
        )
    except Exception:
        pass
    try:
        from pyclaw import __version__

        local_info_items.append(
            ft.Row(
                [
                    ft.Text("pyclaw:", size=12, weight=ft.FontWeight.BOLD, width=100),
                    ft.Text(__version__, size=12),
                ],
                spacing=8,
            )
        )
    except Exception:
        pass
    try:
        from pyclaw.config.paths import resolve_config_path

        local_info_items.append(
            ft.Row(
                [
                    ft.Text("Config:", size=12, weight=ft.FontWeight.BOLD, width=100),
                    ft.Text(str(resolve_config_path()), size=12),
                ],
                spacing=8,
            )
        )
    except Exception:
        pass

    if local_info_items:
        local_card = card_tile(
            content=ft.Column(
                [
                    ft.Text(
                        t("overview.local_info", default="Local Environment"),
                        size=14,
                        weight=ft.FontWeight.BOLD,
                    ),
                    *local_info_items,
                ],
                spacing=6,
            ),
        )
        panel.controls[1].content.controls.append(local_card)

    if gateway_client:
        _update_status_display()

    return panel
