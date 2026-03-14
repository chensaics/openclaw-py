"""Instances panel — online presence / instances list."""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft

from pyclaw.ui.components import card_tile, empty_state_simple, error_state, page_header
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_instances_panel(*, gateway_client: Any = None) -> ft.Column:
    theme = get_theme()
    instance_list = ft.ListView(expand=True, spacing=6)
    loading_ref = {"active": False}

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    async def _refresh() -> None:
        instance_list.controls.clear()
        if not gateway_client or not gateway_client.connected:
            instance_list.controls.append(
                error_state(
                    t("instances.offline", default="Connect to gateway to view instances."),
                    on_retry=_refresh,
                )
            )
            _safe_update(instance_list)
            return

        loading_ref["active"] = True
        loading_row = ft.Row(
            [ft.ProgressRing(width=20, height=20), ft.Text(t("instances.loading", default="Loading..."), size=12)],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        instance_list.controls.append(
            ft.Container(content=loading_row, alignment=ft.Alignment(0, 0), padding=24),
        )
        _safe_update(instance_list)

        try:
            result = await gateway_client.call("system.presence", timeout=10.0)
            entries = result.get("entries", [])
            instance_list.controls.clear()

            if not entries:
                instance_list.controls.append(
                    empty_state_simple(
                        t("instances.empty", default="No online instances."),
                        icon=ft.Icons.PERSON_OFF_OUTLINED,
                    )
                )
            else:
                for entry in entries:
                    comp_id = entry.get("componentId", "unknown")
                    state = entry.get("state", "unknown")
                    last_seen = entry.get("lastSeenAt", "")
                    host = entry.get("host", comp_id)
                    platform = entry.get("platform", "N/A")
                    version = entry.get("version", "N/A")
                    last_input = entry.get("lastInput", last_seen)
                    roles = ", ".join(entry.get("roles", []) or [])

                    tile = card_tile(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.DEVICES, size=20, color=theme.colors.primary),
                                        ft.Text(host, size=14, weight=ft.FontWeight.BOLD, expand=True),
                                        ft.Container(
                                            width=8,
                                            height=8,
                                            border_radius=4,
                                            bgcolor=theme.colors.success,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                ft.Row(
                                    [
                                        ft.Text(f"Platform: {platform}", size=11, color=theme.colors.muted),
                                        ft.Text(f"Version: {version}", size=11, color=theme.colors.muted),
                                    ],
                                    spacing=16,
                                ),
                                ft.Row(
                                    [
                                        ft.Text(f"Last: {last_input}", size=11, color=theme.colors.muted),
                                        ft.Text(f"Roles: {roles or 'N/A'}", size=11, color=theme.colors.muted),
                                    ],
                                    spacing=16,
                                ),
                                ft.Text(f"State: {state}", size=10, color=theme.colors.muted),
                            ],
                            spacing=4,
                        ),
                    )
                    instance_list.controls.append(tile)
        except Exception as exc:
            instance_list.controls.clear()
            instance_list.controls.append(
                error_state(str(exc), on_retry=_refresh),
            )
        finally:
            loading_ref["active"] = False
            _safe_update(instance_list)

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        icon_size=20,
        on_click=lambda e: _fire_async(_refresh),
    )

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.DEVICES,
                t("instances.title", default="Instances"),
                actions=[refresh_btn],
            ),
            instance_list,
        ],
        expand=True,
        spacing=0,
    )

    def _handle_presence_changed(data: dict) -> None:
        """Handle real-time presence change events from the gateway."""
        _fire_async(_refresh)

    if gateway_client:
        gateway_client.on_event("system.presence.changed", _handle_presence_changed)
        gateway_client.on_event("presence.update", _handle_presence_changed)

    panel.refresh = _refresh  # type: ignore[attr-defined]
    _fire_async(_refresh)
    return panel
