"""Sessions panel — session list with edit/delete."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import flet as ft

from pyclaw.ui.components import card_tile, empty_state, error_state, page_header
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_sessions_panel(*, gateway_client: Any = None) -> ft.Column:
    theme = get_theme()
    session_list = ft.ListView(expand=True, spacing=6)
    label_store: dict[str, str] = {}

    limit_field = ft.TextField(
        label=t("sessions.limit", default="Limit"),
        value="50",
        dense=True,
        width=80,
    )
    active_min_field = ft.TextField(
        label=t("sessions.active_min", default="Active (min)"),
        value="",
        dense=True,
        width=100,
    )

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _format_updated(path_str: str) -> str:
        try:
            p = Path(path_str)
            if p.exists():
                mtime = p.stat().st_mtime
                dt = datetime.fromtimestamp(mtime, tz=UTC)
                return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        return "-"

    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size // 1024} KB"
        return f"{size // (1024 * 1024)} MB"

    def _render_sessions(sessions: list[dict[str, Any]], *, offline: bool = False) -> None:
        """Render session tiles into the session_list."""
        if not sessions:
            session_list.controls.append(
                empty_state(
                    ft.Icons.CHAT_BUBBLE_OUTLINE,
                    t("sessions.empty_hint", default="Send a message to create your first session."),
                    action_label=t("sessions.new", default="New Session"),
                    on_action=lambda e: _fire_async(_refresh),
                )
            )
            return

        if offline:
            session_list.controls.append(
                ft.Container(
                    content=ft.Text(
                        t("sessions.offline_mode", default="Offline — showing local session files"),
                        size=11,
                        color=theme.colors.warning,
                        italic=True,
                    ),
                    padding=ft.padding.symmetric(horizontal=16, vertical=4),
                )
            )

        for s in sessions:
            path_str = s.get("path", "")
            key = path_str or s.get("key", "")
            default_label = s.get("label", f"{s.get('agentId', '')}/{s.get('file', '')}")
            label = label_store.get(key, default_label)
            kind = s.get("kind", "chat")
            updated = _format_updated(path_str)
            size = s.get("size", 0)
            tokens_str = str(s.get("tokens", "-"))

            label_tf = ft.TextField(
                value=label,
                dense=True,
                height=32,
                content_padding=4,
                text_size=12,
                on_submit=lambda e, k=key: _on_label_submit(e, k),
            )
            label_tf.data = key

            def _on_label_submit(e: Any, k: str) -> None:
                label_store[k] = e.control.value
                _safe_update(e.control)

            actions: list[ft.Control] = []
            if not offline:

                def _make_delete_cb(p: str):
                    async def _do_delete() -> None:
                        if gateway_client:
                            try:
                                await gateway_client.call("sessions.delete", {"path": p})
                                await _refresh()
                            except Exception:
                                pass

                    return _do_delete

                actions.append(
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=18,
                        tooltip=t("sessions.delete", default="Delete"),
                        on_click=lambda e, p=path_str: _fire_async(_make_delete_cb(p)),
                    )
                )

            tile = card_tile(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, size=18, color=theme.colors.muted),
                                ft.Container(content=label_tf, expand=True),
                                *actions,
                            ],
                            spacing=8,
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    f"Key: {Path(path_str).name if path_str else key}",
                                    size=10,
                                    color=theme.colors.muted,
                                ),
                                ft.Text(f"Kind: {kind}", size=10, color=theme.colors.muted),
                                ft.Text(f"Updated: {updated}", size=10, color=theme.colors.muted),
                                ft.Text(f"Size: {_format_size(size)}", size=10, color=theme.colors.muted),
                                ft.Text(f"Tokens: {tokens_str}", size=10, color=theme.colors.muted),
                            ],
                            spacing=12,
                            wrap=True,
                        ),
                    ],
                    spacing=6,
                ),
            )
            session_list.controls.append(tile)

    def _load_local_sessions() -> list[dict[str, Any]]:
        """Fall back to local session files when gateway is offline."""
        sessions: list[dict[str, Any]] = []
        try:
            from pyclaw.config.paths import get_sessions_dir

            sessions_dir = get_sessions_dir()
            if sessions_dir.exists():
                for f in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
                    sessions.append(
                        {
                            "key": f.stem,
                            "label": f.stem,
                            "kind": "local",
                            "path": str(f),
                            "tokens": 0,
                        }
                    )
        except Exception:
            pass
        return sessions

    async def _refresh() -> None:
        session_list.controls.clear()
        if not gateway_client or not gateway_client.connected:
            local = _load_local_sessions()
            if local:
                _render_sessions(local, offline=True)
            else:
                session_list.controls.append(
                    error_state(
                        t("sessions.offline", default="Connect to gateway to view sessions."),
                        on_retry=_refresh,
                    )
                )
            _safe_update(session_list)
            return

        try:
            limit_val = 50
            try:
                limit_val = max(1, min(500, int(limit_field.value or "50")))
            except ValueError:
                pass

            result = await gateway_client.call("sessions.list")
            raw_sessions = result.get("sessions", [])[:limit_val]

            active_min_val = None
            try:
                if active_min_field.value:
                    active_min_val = int(active_min_field.value)
            except ValueError:
                pass

            sessions: list[dict[str, Any]] = []
            for s in raw_sessions:
                path_str = s.get("path", "")
                try:
                    mtime = Path(path_str).stat().st_mtime if path_str else 0
                    if active_min_val is not None and active_min_val > 0:
                        from time import time

                        if (time() - mtime) > active_min_val * 60:
                            continue
                except Exception:
                    pass
                sessions.append(s)

            _render_sessions(sessions)
        except Exception as exc:
            session_list.controls.clear()
            session_list.controls.append(error_state(str(exc), on_retry=_refresh))
        _safe_update(session_list)

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        icon_size=20,
        on_click=lambda e: _fire_async(_refresh),
    )

    filter_row = ft.Row(
        [
            limit_field,
            active_min_field,
            ft.ElevatedButton(
                t("channels.refresh", default="Refresh"),
                icon=ft.Icons.REFRESH,
                on_click=lambda e: _fire_async(_refresh),
            ),
        ],
        spacing=12,
    )

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.CHAT_BUBBLE_OUTLINE,
                t("sessions.title", default="Sessions"),
                actions=[refresh_btn],
            ),
            ft.Container(content=filter_row, padding=ft.padding.symmetric(horizontal=16, vertical=8)),
            session_list,
        ],
        expand=True,
        spacing=0,
    )

    panel.refresh = _refresh
    _fire_async(_refresh)
    return panel
