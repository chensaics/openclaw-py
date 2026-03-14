"""Debug panel — status/health/heartbeat JSON, manual RPC, event log."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import flet as ft

from pyclaw.ui.components import page_header
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_debug_panel(*, gateway_client: Any = None) -> ft.Column:
    theme = get_theme()
    status_json = ft.Text("", size=11, font_family="monospace", selectable=True)
    health_json = ft.Text("", size=11, font_family="monospace", selectable=True)
    heartbeat_json = ft.Text("", size=11, font_family="monospace", selectable=True)
    method_field = ft.TextField(
        label=t("debug.method", default="Method"),
        hint_text="status",
        dense=True,
        expand=True,
    )
    params_field = ft.TextField(
        label=t("debug.params", default="Params (JSON)"),
        hint_text="{}",
        multiline=True,
        min_lines=2,
        dense=True,
        expand=True,
    )
    rpc_result_text = ft.Text("", size=11, font_family="monospace", selectable=True)
    event_log_list = ft.ListView(spacing=2, height=200)

    event_log_ref: list[dict[str, Any]] = []

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _render_json(obj: Any) -> str:
        try:
            return json.dumps(obj, indent=2, ensure_ascii=False)
        except Exception:
            return str(obj)

    async def _refresh_status_health() -> None:
        if not gateway_client or not gateway_client.connected:
            status_json.value = t("debug.offline", default="Not connected")
            health_json.value = ""
            heartbeat_json.value = ""
            _safe_update(status_json)
            _safe_update(health_json)
            _safe_update(heartbeat_json)
            return
        try:
            status_res = await gateway_client.call("status", timeout=10.0)
            status_json.value = _render_json(status_res)
            _safe_update(status_json)
        except Exception as exc:
            status_json.value = f"Error: {exc}"
            _safe_update(status_json)
        try:
            health_res = await gateway_client.call("health", timeout=10.0)
            health_json.value = _render_json(health_res)
            _safe_update(health_json)
        except Exception as exc:
            health_json.value = f"Error: {exc}"
            _safe_update(health_json)
        try:
            hb_res = await gateway_client.call("system.heartbeat.last", timeout=10.0)
            heartbeat_json.value = _render_json(hb_res)
            _safe_update(heartbeat_json)
        except Exception as exc:
            heartbeat_json.value = f"Error: {exc}"
            _safe_update(heartbeat_json)

    async def _do_rpc_call() -> None:
        method = (method_field.value or "").strip()
        if not method:
            rpc_result_text.value = "Method required"
            _safe_update(rpc_result_text)
            return
        params_str = params_field.value or "{}"
        try:
            params = json.loads(params_str) if params_str.strip() else {}
        except json.JSONDecodeError as e:
            rpc_result_text.value = f"Invalid JSON: {e}"
            _safe_update(rpc_result_text)
            return
        if not gateway_client or not gateway_client.connected:
            rpc_result_text.value = "Not connected"
            _safe_update(rpc_result_text)
            return
        try:
            result = await gateway_client.call(method, params, timeout=30.0)
            rpc_result_text.value = _render_json(result)
            event_log_ref.append({"type": "rpc", "method": method, "result": "ok"})
            _update_event_log()
        except Exception as exc:
            rpc_result_text.value = f"Error: {exc}"
            event_log_ref.append({"type": "rpc", "method": method, "result": str(exc)})
            _update_event_log()
        _safe_update(rpc_result_text)

    def _update_event_log() -> None:
        event_log_list.controls.clear()
        for entry in reversed(event_log_ref[-50:]):
            etype = entry.get("type", "")
            msg = entry.get("event", entry.get("method", ""))
            if etype == "rpc":
                msg = f"RPC {entry.get('method', '')} -> {entry.get('result', '')}"
            row = ft.Row(
                [
                    ft.Text(etype, size=10, color=theme.colors.muted, width=50),
                    ft.Text(str(msg), size=10, expand=True, overflow=ft.TextOverflow.ELLIPSIS),
                ],
                spacing=8,
            )
            event_log_list.controls.append(row)
        _safe_update(event_log_list)

    def _on_gateway_event(event_name: str, payload: Any) -> None:
        event_log_ref.append({"type": "event", "event": event_name, "payload": payload})
        _update_event_log()

    call_btn = ft.ElevatedButton(
        t("debug.call", default="Call"),
        icon=ft.Icons.PLAY_ARROW,
        on_click=lambda e: _fire_async(_do_rpc_call),
    )

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        icon_size=20,
        on_click=lambda e: _fire_async(_refresh_status_health),
    )

    status_section = ft.Container(
        content=ft.Column(
            [
                ft.Text(t("debug.status", default="Status"), size=14, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=status_json,
                    padding=8,
                    bgcolor=theme.colors.surface_container,
                    border_radius=8,
                ),
            ],
            spacing=4,
        ),
    )
    health_section = ft.Container(
        content=ft.Column(
            [
                ft.Text(t("debug.health", default="Health"), size=14, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=health_json,
                    padding=8,
                    bgcolor=theme.colors.surface_container,
                    border_radius=8,
                ),
            ],
            spacing=4,
        ),
    )
    heartbeat_section = ft.Container(
        content=ft.Column(
            [
                ft.Text(t("debug.heartbeat", default="Heartbeat"), size=14, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=heartbeat_json,
                    padding=8,
                    bgcolor=theme.colors.surface_container,
                    border_radius=8,
                ),
            ],
            spacing=4,
        ),
    )
    rpc_section = ft.Column(
        [
            ft.Text(t("debug.manual_rpc", default="Manual RPC"), size=14, weight=ft.FontWeight.BOLD),
            ft.Row([method_field, params_field], spacing=8),
            call_btn,
            ft.Container(
                content=rpc_result_text,
                padding=8,
                bgcolor=theme.colors.surface_container,
                border_radius=8,
            ),
        ],
        spacing=8,
    )
    event_section = ft.Column(
        [
            ft.Text(t("debug.event_log", default="Event Log"), size=14, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=event_log_list,
                border=ft.border.all(0.5, theme.colors.border),
                border_radius=8,
            ),
        ],
        spacing=4,
    )

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.BUG_REPORT,
                t("debug.title", default="Debug"),
                actions=[refresh_btn],
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row([status_section, health_section, heartbeat_section], spacing=16, wrap=True),
                        ft.Divider(height=1),
                        rpc_section,
                        ft.Divider(height=1),
                        event_section,
                    ],
                    spacing=16,
                ),
                padding=16,
            ),
        ],
        expand=True,
        spacing=0,
    )

    if gateway_client:
        gateway_client.on_any_event(_on_gateway_event)
        _fire_async(_refresh_status_health)

    return panel
