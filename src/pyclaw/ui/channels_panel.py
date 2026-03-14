"""Channel status panel — displays connection status, capabilities, and metrics.

Shows each configured channel with catalog-driven capability badges,
runtime metrics (messages sent/failed), and color-coded status indicators.
Works across Web, Desktop, and Mobile (Flet) targets.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import flet as ft

from pyclaw.ui.components import empty_state_simple, error_state, page_header
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme

logger = logging.getLogger(__name__)

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

_CAPABILITY_LABELS: list[tuple[str, str, str]] = [
    ("typing", "T", "Typing indicator"),
    ("reactions", "R", "Reactions"),
    ("threads", "Th", "Threads"),
    ("editing", "E", "Message editing"),
    ("buttons", "B", "Buttons/actions"),
    ("pins", "P", "Pins"),
]


def _status_color(status: str) -> str:
    theme = get_theme()
    return {
        "connected": theme.colors.success,
        "running": theme.colors.success,
        "configured": theme.colors.warning,
        "disconnected": theme.colors.error,
        "error": theme.colors.error,
        "disabled": theme.colors.muted,
        "stopped": theme.colors.warning,
        "unknown": theme.colors.muted,
    }.get(status, theme.colors.muted)


def _build_capability_badges(capabilities: dict[str, Any]) -> list[ft.Control]:
    if not capabilities:
        return []
    theme = get_theme()
    badges: list[ft.Control] = []
    for key, short, tooltip_text in _CAPABILITY_LABELS:
        if capabilities.get(key, False):
            badges.append(
                ft.Tooltip(
                    message=tooltip_text,
                    content=ft.Container(
                        content=ft.Text(
                            short,
                            size=9,
                            weight=ft.FontWeight.BOLD,
                            color=theme.colors.on_primary,
                        ),
                        bgcolor=theme.colors.primary,
                        padding=ft.padding.symmetric(horizontal=5, vertical=2),
                        border_radius=ft.border_radius.all(4),
                    ),
                )
            )
    return badges


def _build_metrics_row(metrics: dict[str, Any]) -> ft.Control | None:
    if not metrics:
        return None
    theme = get_theme()
    sent = metrics.get("messages_sent", 0)
    failed = metrics.get("messages_failed", 0)
    parts: list[ft.Control] = []
    if sent:
        parts.append(ft.Text(f"{sent} sent", size=10, color=theme.colors.success))
    if failed:
        parts.append(ft.Text(f"{failed} failed", size=10, color=theme.colors.error))
    return ft.Row(parts, spacing=8) if parts else None


def _build_channel_tile(ch: dict[str, Any]) -> ft.Control:
    theme = get_theme()
    cid = ch.get("id", ch.get("name", "unknown"))
    display_name = ch.get("display_name", ch.get("name", cid)).title()
    status = ch.get("status", "unknown")
    color = _status_color(status)
    ch_color = ch.get("color", "")
    icon = _ICON_MAP.get(cid.lower(), ft.Icons.LINK)

    cap_badges = _build_capability_badges(ch.get("capabilities", {}))
    metrics_row = _build_metrics_row(ch.get("metrics", {}))

    info_children: list[ft.Control] = [
        ft.Text(display_name, size=14, weight=ft.FontWeight.BOLD),
        ft.Text(status.replace("_", " ").title(), size=11, color=color),
    ]
    if cap_badges:
        info_children.append(ft.Row(cap_badges, spacing=4, wrap=True))
    if metrics_row:
        info_children.append(metrics_row)

    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, size=22, color=ch_color or color),
                ft.Column(info_children, spacing=3, expand=True, tight=True),
                ft.Container(width=10, height=10, border_radius=ft.border_radius.all(5), bgcolor=color),
            ],
            spacing=10,
        ),
        padding=ft.padding.symmetric(horizontal=12, vertical=10),
        border_radius=ft.border_radius.all(theme.card_border_radius),
        bgcolor=theme.colors.surface_container,
        border=ft.border.all(0.5, theme.colors.border),
    )


def _stat_chip(value: str, label: str, color: str | None = None) -> ft.Control:
    theme = get_theme()
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(value, size=18, weight=ft.FontWeight.BOLD, color=color or theme.colors.muted),
                ft.Text(label, size=10, color=theme.colors.muted),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
        padding=ft.padding.symmetric(horizontal=12, vertical=4),
    )


def build_channels_panel(*, gateway_client: Any = None) -> ft.Column:
    """Build a channels panel following the standard ``build_*_panel`` convention.

    The returned ``ft.Column`` has two extra attributes:
      - ``refresh``: coroutine to reload channel data
      - ``update_channels``: sync method for external data push
    """
    gw = gateway_client
    channel_list = ft.ListView(expand=True, spacing=6)
    summary_row = ft.Row(spacing=16)

    def _safe_update(ctrl: ft.Control) -> None:
        try:
            ctrl.update()
        except Exception:
            pass

    def update_channels(
        channels: list[dict[str, Any]],
        *,
        error: str | None = None,
        on_retry: Any = None,
    ) -> None:
        channel_list.controls.clear()
        if error:
            channel_list.controls.append(
                error_state(error, on_retry=on_retry or _refresh_wrapper),
            )
            summary_row.controls = []
        else:
            theme = get_theme()
            total = len(channels)
            running = sum(1 for c in channels if c.get("running") or c.get("status") == "running")
            configured = sum(1 for c in channels if c.get("status") == "configured")

            summary_row.controls = [
                _stat_chip(f"{total}", "Total", theme.colors.muted),
                _stat_chip(f"{running}", "Running", theme.colors.success),
                _stat_chip(f"{configured}", "Configured", theme.colors.warning),
            ]

            if not channels:
                channel_list.controls.append(
                    empty_state_simple("暂无频道配置", icon=ft.Icons.LINK_OFF),
                )
            else:
                for ch in channels:
                    channel_list.controls.append(_build_channel_tile(ch))

        _safe_update(summary_row)
        _safe_update(channel_list)

    async def _refresh() -> None:
        if not gw or not gw.connected:
            from pyclaw.config.io import load_config
            from pyclaw.config.paths import resolve_config_path

            channels: list[dict[str, Any]] = []
            try:
                config = load_config(resolve_config_path())
                ch_cfg = config.channels
                if ch_cfg:
                    cfg_dict = ch_cfg.model_dump(by_alias=True, exclude_none=True)
                    for name, cfg_val in cfg_dict.items():
                        if name == "defaults" or not isinstance(cfg_val, dict):
                            continue
                        enabled = cfg_val.get("enabled", True)
                        info: dict[str, Any] = {
                            "id": name,
                            "name": name.title(),
                            "enabled": enabled,
                            "status": "configured" if enabled else "disabled",
                        }
                        channels.append(info)
            except Exception:
                update_channels([], error="加载失败", on_retry=_refresh)
                return
            update_channels(channels)
            return

        try:
            result = await gw.call("channels.list")
            gw_channels = result.get("channels", [])
            update_channels(gw_channels)
        except Exception:
            logger.warning("_refresh_channels failed", exc_info=True)
            update_channels([], error="加载失败", on_retry=_refresh)

    def _refresh_wrapper() -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_refresh())
        except RuntimeError:
            pass

    header = page_header(
        ft.Icons.LINK,
        t("channels.title"),
        [
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                tooltip=t("channels.refresh"),
                icon_size=20,
                on_click=lambda e: _refresh_wrapper(),
            )
        ],
    )

    col = ft.Column(
        controls=[
            header,
            ft.Container(content=summary_row, padding=ft.padding.symmetric(horizontal=16)),
            channel_list,
        ],
        expand=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )

    col.refresh = _refresh  # type: ignore[attr-defined]
    col.update_channels = update_channels  # type: ignore[attr-defined]
    return col
