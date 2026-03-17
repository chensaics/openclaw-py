"""Logs panel — real-time log list with filters and export."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import flet as ft

from pyclaw.ui.components import empty_state_simple, error_state, page_header
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


_LOG_LEVELS = ["trace", "debug", "info", "warn", "error", "fatal"]


def build_logs_panel(*, gateway_client: Any = None) -> ft.Column:
    theme = get_theme()
    log_list = ft.ListView(expand=True, spacing=2, padding=8)
    search_field = ft.TextField(
        hint_text=t("logs.search", default="Search..."),
        dense=True,
        prefix_icon=ft.Icons.SEARCH,
        height=36,
        text_size=12,
        on_change=lambda e: _apply_filters(),
    )
    level_chips_ref: dict[str, ft.Chip] = {}
    auto_follow_switch = ft.Switch(
        label=t("logs.auto_follow", default="Auto follow"),
        value=True,
    )
    level_filter_ref: dict[str, bool] = {lv: True for lv in _LOG_LEVELS}
    raw_lines_ref: list[Any] = []

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _parse_log_line(line: str | dict) -> tuple[str, str, str, str]:
        if isinstance(line, dict):
            ts = str(line.get("time", line.get("timestamp", "")))
            raw = str(line.get("line", line.get("message", "")))
        else:
            ts = ""
            raw = str(line)

        level = "info"
        subsystem = ""
        msg = raw
        raw_upper = raw.upper()
        for lv in ["FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE"]:
            if lv in raw_upper:
                level = "warn" if lv == "WARNING" else lv.lower()
                break

        if " " in raw:
            parts = raw.split(None, 2)
            if len(parts) >= 3 and ":" in parts[1]:
                subsystem = parts[1]
                msg = parts[2] if len(parts) > 2 else raw
        return ts, level, subsystem, msg

    def _apply_filters() -> None:
        search_lower = (search_field.value or "").lower()
        log_list.controls.clear()
        for item in raw_lines_ref:
            line = item.get("line", item.get("message", str(item))) if isinstance(item, dict) else str(item)
            if search_lower and search_lower not in line.lower():
                continue
            ts, level, subsystem, msg = _parse_log_line(item)
            if not level_filter_ref.get(level, True):
                continue
            color = {
                "error": theme.colors.error,
                "fatal": theme.colors.error,
                "warn": theme.colors.warning,
                "debug": theme.colors.muted,
                "trace": theme.colors.muted,
            }.get(level, theme.colors.on_surface)
            row = ft.Row(
                [
                    ft.Text(ts[:19] if ts else "", size=10, color=theme.colors.muted, width=100),
                    ft.Container(
                        content=ft.Text(
                            level.upper(), size=9, color=theme.colors.on_primary, weight=ft.FontWeight.W_500
                        ),
                        bgcolor=theme.colors.primary,
                        padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                        border_radius=4,
                    ),
                    ft.Text(subsystem or "-", size=10, color=theme.colors.muted, width=80),
                    ft.Text(msg, size=11, color=color, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ],
                spacing=8,
            )
            log_list.controls.append(row)
        _safe_update(log_list)

    async def _refresh() -> None:
        log_list.controls.clear()
        if not gateway_client or not gateway_client.connected:
            log_list.controls.append(
                error_state(
                    t("logs.offline", default="Connect to gateway to view logs."),
                    on_retry=_refresh,
                )
            )
            _safe_update(log_list)
            return

        try:
            result = await gateway_client.call("logs.tail", {"limit": 200, "json": True})
            raw_lines_ref[:] = result.get("lines", [])
            _apply_filters()
            if not raw_lines_ref and not log_list.controls:
                log_list.controls.append(
                    empty_state_simple(
                        t("logs.empty", default="No log entries."),
                        icon=ft.Icons.DESCRIPTION_OUTLINED,
                    )
                )
                _safe_update(log_list)
        except Exception as exc:
            log_list.controls.clear()
            log_list.controls.append(error_state(str(exc), on_retry=_refresh))
            _safe_update(log_list)

    def _on_level_chip_click(lv: str) -> None:
        level_filter_ref[lv] = not level_filter_ref.get(lv, True)
        if lv in level_chips_ref:
            level_chips_ref[lv].selected = level_filter_ref[lv]
            _safe_update(level_chips_ref[lv])
        _apply_filters()

    level_chips_row = ft.Row(
        [ft.Text(t("logs.level", default="Level:"), size=12)],
        spacing=4,
    )
    for lv in _LOG_LEVELS:
        chip = ft.Chip(
            label=ft.Text(lv.upper()),
            selected=level_filter_ref.get(lv, True),
            on_click=lambda e, l=lv: _on_level_chip_click(l),
        )
        chip.data = lv
        level_chips_ref[lv] = chip
        level_chips_row.controls.append(chip)

    async def _export_logs() -> None:
        if not raw_lines_ref:
            return
        lines = []
        for item in raw_lines_ref:
            if isinstance(item, dict):
                lines.append(json.dumps(item, ensure_ascii=False))
            else:
                lines.append(str(item))
        content = "\n".join(lines)
        try:
            from pyclaw.infra.misc_extras import clipboard_write

            clipboard_write(content)
        except Exception:
            pass

    export_btn = ft.Button(
        t("logs.export", default="Export"),
        icon=ft.Icons.DOWNLOAD,
        on_click=lambda e: _fire_async(_export_logs),
    )

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        icon_size=20,
        on_click=lambda e: _fire_async(_refresh),
    )

    toolbar = ft.Row(
        [
            search_field,
            ft.Container(width=8),
            level_chips_row,
            ft.Container(width=8),
            auto_follow_switch,
            export_btn,
            refresh_btn,
        ],
        spacing=8,
        wrap=True,
    )

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.DESCRIPTION,
                t("logs.title", default="Logs"),
                actions=[refresh_btn],
            ),
            ft.Container(content=toolbar, padding=ft.Padding.symmetric(horizontal=16, vertical=8)),
            log_list,
        ],
        expand=True,
        spacing=0,
    )

    def _handle_log_event(data: dict) -> None:
        """Handle real-time log events pushed from the gateway."""
        line = data.get("line") or data.get("message") or data
        raw_lines_ref.append(line)
        if len(raw_lines_ref) > 2000:
            raw_lines_ref[:] = raw_lines_ref[-1500:]

        ts, level, subsystem, msg = _parse_log_line(line)
        if not level_filter_ref.get(level, True):
            return
        search_lower = (search_field.value or "").lower()
        raw_str = line if isinstance(line, str) else str(line.get("message", str(line)))
        if search_lower and search_lower not in raw_str.lower():
            return
        cur_theme = get_theme()
        color = {
            "error": cur_theme.colors.error,
            "fatal": cur_theme.colors.error,
            "warn": cur_theme.colors.warning,
            "debug": cur_theme.colors.muted,
            "trace": cur_theme.colors.muted,
        }.get(level, cur_theme.colors.on_surface)
        row = ft.Row(
            [
                ft.Text(ts[:19] if ts else "", size=10, color=cur_theme.colors.muted, width=100),
                ft.Container(
                    content=ft.Text(
                        level.upper(), size=9, color=cur_theme.colors.on_primary, weight=ft.FontWeight.W_500
                    ),
                    bgcolor=cur_theme.colors.primary,
                    padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                    border_radius=4,
                ),
                ft.Text(subsystem or "-", size=10, color=cur_theme.colors.muted, width=80),
                ft.Text(msg, size=11, color=color, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ],
            spacing=8,
        )
        log_list.controls.append(row)
        if auto_follow_switch.value:
            _fire_async(lambda: log_list.scroll_to(offset=-1))
        _safe_update(log_list)

    if gateway_client:
        gateway_client.on_event("logs.new", _handle_log_event)
        gateway_client.on_event("log.entry", _handle_log_event)

    panel.refresh = _refresh
    _fire_async(_refresh)
    return panel
