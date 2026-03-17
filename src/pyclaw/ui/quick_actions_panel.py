"""Quick actions panel — one-click shortcuts for common workflows."""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft

from pyclaw.ui.components import page_header, quick_action_card, status_chip
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import StatusColors, get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_quick_actions_panel(
    *,
    gateway_client: Any = None,
    get_gateway_client: Any = None,
    on_navigate: Any = None,
    on_feedback: Any = None,
) -> ft.Column:
    theme = get_theme()
    status_line = ft.Row(spacing=8, wrap=True)
    updated_line = ft.Text("", size=11, color=theme.colors.muted)

    def _notify(message: str) -> None:
        if on_feedback and message:
            try:
                on_feedback(message)
            except Exception:
                pass

    def _resolve_gateway_client() -> Any:
        if callable(get_gateway_client):
            try:
                return get_gateway_client()
            except Exception:
                return None
        return gateway_client

    async def _status_check() -> None:
        gw = _resolve_gateway_client()
        if not gw or not getattr(gw, "connected", False):
            status_line.controls = [
                status_chip(t("quick_actions.status_gateway", default="Gateway: Offline"), StatusColors.ERROR),
                status_chip(t("quick_actions.status_agents", default="Agents: Unknown"), theme.colors.muted),
                status_chip(t("quick_actions.status_cron", default="Cron: Unknown"), theme.colors.muted),
            ]
            updated_line.value = t("quick_actions.last_checked", default="Last checked: offline")
            if status_line.page:
                status_line.update()
            if updated_line.page:
                updated_line.update()
            _notify(t("quick_actions.offline_hint", default="Gateway offline."))
            return

        try:
            health = await gw.call("health", timeout=8.0)
            agents = await gw.call("agents.list", timeout=8.0)
            cron = await gw.call("cron.list", timeout=8.0)

            agent_count = len(agents.get("agents", []))
            cron_count = len(cron.get("jobs", []))
            status_line.controls = [
                status_chip(
                    t("quick_actions.status_gateway_ok", default="Gateway: Healthy"),
                    StatusColors.SUCCESS if health.get("ok", True) else StatusColors.WARNING,
                ),
                status_chip(
                    t("quick_actions.status_agents_count", default="Agents: {count}", count=agent_count),
                    StatusColors.INFO,
                ),
                status_chip(
                    t("quick_actions.status_cron_count", default="Cron: {count}", count=cron_count),
                    StatusColors.SUCCESS if cron_count > 0 else theme.colors.muted,
                ),
            ]
            updated_line.value = t("quick_actions.last_checked_now", default="Last checked: just now")
            if status_line.page:
                status_line.update()
            if updated_line.page:
                updated_line.update()
            _notify(t("quick_actions.status_ok", default="Status check complete."))
        except Exception as exc:
            _notify(t("quick_actions.status_failed", default="Status check failed: {error}", error=str(exc)))

    def _nav_action(idx: int) -> Any:
        return lambda e: _fire_async(on_navigate, idx)

    cards = [
        quick_action_card(
            ft.Icons.ARTICLE_OUTLINED,
            t("quick_actions.publish_wizard", default="Publish Wizard"),
            t("quick_actions.publish_wizard_desc", default="Quickly publish via configured skills."),
            [
                {"label": t("quick_actions.wechat_publish", default="WeChat"), "on_click": _nav_action(9)},
                {"label": t("quick_actions.redbook_publish", default="Redbook"), "on_click": _nav_action(9)},
            ],
            on_click=_nav_action(9),
        ),
        quick_action_card(
            ft.Icons.SMART_TOY_OUTLINED,
            t("quick_actions.agent_shortcut", default="Agent Shortcut"),
            t("quick_actions.agent_shortcut_desc", default="Create or switch to common agents."),
            [
                {"label": t("quick_actions.agent_select", default="Select"), "on_click": _nav_action(2)},
                {"label": t("quick_actions.agent_launch", default="Launch"), "on_click": _nav_action(2)},
            ],
            on_click=_nav_action(2),
        ),
        quick_action_card(
            ft.Icons.SCHEDULE,
            t("quick_actions.cron_shortcut", default="Cron Shortcut"),
            t("quick_actions.cron_shortcut_desc", default="Manage and run scheduled jobs."),
            [
                {"label": t("quick_actions.cron_run_now", default="Run now"), "on_click": _nav_action(7)},
            ],
            on_click=_nav_action(7),
        ),
        quick_action_card(
            ft.Icons.HEALTH_AND_SAFETY_OUTLINED,
            t("quick_actions.status_check", default="Status Check"),
            t("quick_actions.status_check_desc", default="Check gateway, agents and cron health."),
            [
                {
                    "label": t("quick_actions.run_check", default="Run check"),
                    "on_click": lambda e: _fire_async(_status_check),
                }
            ],
            on_click=lambda e: _fire_async(_status_check),
        ),
    ]

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        on_click=lambda e: _fire_async(_status_check),
    )

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.FLASH_ON,
                t("nav.quick_actions", default="Quick Actions"),
                actions=[refresh_btn],
            ),
            ft.Container(
                content=ft.Column(
                    [ft.Row([status_line], wrap=True), updated_line, ft.ResponsiveRow(cards)],
                    spacing=12,
                ),
                padding=16,
            ),
        ],
        expand=True,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
    )

    async def _refresh() -> None:
        await _status_check()

    panel.refresh = _refresh
    _fire_async(_status_check)
    return panel
