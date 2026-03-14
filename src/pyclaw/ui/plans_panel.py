"""Plans panel — execution plan management with status tracking."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import flet as ft

from pyclaw.ui.components import card_tile, empty_state_simple, error_state, page_header, status_chip
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import StatusColors, get_theme

logger = logging.getLogger(__name__)


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_plans_panel(*, gateway_client: Any = None) -> ft.Column:
    plan_list = ft.ListView(expand=True, spacing=6)

    gw = gateway_client

    def _safe_update(ctrl: ft.Control) -> None:
        try:
            ctrl.update()
        except Exception:
            pass

    async def _refresh() -> None:
        nonlocal gw
        if not gw or not gw.connected:
            plan_list.controls = [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.WIFI_OFF, size=36, color="#94a3b8"),
                            ft.Text(
                                t("plans.offline", default="Connect to gateway to view plans."),
                                size=13,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.OutlinedButton(
                                t("common.retry", default="Retry"),
                                icon=ft.Icons.REFRESH,
                                on_click=lambda e: _fire_async(_refresh),
                            ),
                        ],
                        spacing=12,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    alignment=ft.Alignment(0, 0),
                    padding=40,
                ),
            ]
            _safe_update(plan_list)
            return
        try:
            result = await gw.call("plan.list")
            plans = result.get("plans", [])
            plan_list.controls.clear()
            if not plans:
                plan_list.controls.append(
                    empty_state_simple("暂无执行计划", icon=ft.Icons.CHECKLIST),
                )
            cur_theme = get_theme()
            for p in plans:
                status = p.get("status", "pending")
                color = {
                    "completed": StatusColors.SUCCESS,
                    "running": StatusColors.INFO,
                    "paused": StatusColors.WARNING,
                    "failed": StatusColors.ERROR,
                }.get(status, "#94a3b8")

                steps = p.get("steps", [])
                total = len(steps)
                done = sum(1 for s in steps if s.get("status") == "completed")

                actions: list[ft.Control] = []
                if status == "paused":
                    actions.append(
                        ft.IconButton(
                            icon=ft.Icons.PLAY_ARROW,
                            icon_size=16,
                            tooltip="Resume",
                            data=p.get("id"),
                            on_click=lambda e: _fire_async(_resume_plan, e.control.data),
                        )
                    )
                actions.append(
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=16,
                        tooltip="Delete",
                        data=p.get("id"),
                        on_click=lambda e: _fire_async(_delete_plan, e.control.data),
                    )
                )

                tile_content = ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECKLIST, color=color, size=20),
                        ft.Column(
                            [
                                ft.Text(p.get("goal", "Plan"), weight=ft.FontWeight.BOLD, size=13),
                                ft.Row(
                                    [
                                        status_chip(status, color),
                                        ft.Text(f"{done}/{total} steps", size=11, color=cur_theme.colors.muted),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            spacing=4,
                            expand=True,
                            tight=True,
                        ),
                        ft.Row(actions, spacing=0),
                    ],
                    spacing=8,
                )
                plan_list.controls.append(card_tile(tile_content))
            _safe_update(plan_list)
        except Exception:
            logger.warning("_refresh_plans failed", exc_info=True)
            plan_list.controls = [
                error_state("加载失败", on_retry=_refresh),
            ]
            _safe_update(plan_list)

    async def _resume_plan(plan_id: str) -> None:
        if gw:
            try:
                await gw.call("plan.resume", {"planId": plan_id})
                await _refresh()
            except Exception:
                logger.warning("_resume_plan failed", exc_info=True)

    async def _delete_plan(plan_id: str) -> None:
        if gw:
            try:
                await gw.call("plan.delete", {"planId": plan_id})
                await _refresh()
            except Exception:
                logger.warning("_delete_plan failed", exc_info=True)

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip="Refresh",
        icon_size=20,
        on_click=lambda e: _fire_async(_refresh),
    )

    col = ft.Column(
        controls=[
            page_header(ft.Icons.CHECKLIST, t("nav.plans", default="Plans"), [refresh_btn]),
            plan_list,
        ],
        spacing=0,
        expand=True,
    )

    col.refresh = _refresh  # type: ignore[attr-defined]
    return col
