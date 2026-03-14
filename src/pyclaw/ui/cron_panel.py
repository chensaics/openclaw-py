"""Cron panel — scheduled tasks with add form and execution history."""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft

from pyclaw.ui.components import card_tile, empty_state_simple, error_state, page_header, status_chip
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import StatusColors, get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_cron_panel(*, gateway_client: Any = None) -> ft.Column:
    theme = get_theme()
    cron_list = ft.ListView(expand=True, spacing=6)
    cron_history_list = ft.ListView(spacing=4, height=200)
    filter_enabled_dropdown = ft.Dropdown(
        label=t("cron.filter_enabled", default="Status"),
        value="all",
        width=100,
        dense=True,
        options=[
            ft.dropdown.Option("all", t("cron.filter_all", default="All")),
            ft.dropdown.Option("enabled", t("cron.filter_enabled_only", default="Enabled")),
            ft.dropdown.Option("disabled", t("cron.filter_disabled_only", default="Disabled")),
        ],
    )
    filter_name_field = ft.TextField(
        hint_text=t("cron.filter_name", default="Filter by name..."),
        dense=True,
        width=180,
        on_change=lambda e: _fire_async(_refresh),
    )
    add_name = ft.TextField(label=t("cron.name", default="Name"), dense=True, width=180)
    add_schedule = ft.TextField(label=t("cron.schedule", default="Schedule (cron)"), dense=True, width=180)
    add_message = ft.TextField(label=t("cron.message", default="Message"), dense=True, width=280)
    add_agent_dropdown = ft.Dropdown(
        label=t("cron.agent", default="Agent"),
        value="main",
        width=140,
        dense=True,
        options=[ft.dropdown.Option("main", "main")],
    )
    jobs_ref: list[dict[str, Any]] = []
    agents_ref: list[dict[str, Any]] = []

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _apply_filters() -> list[dict[str, Any]]:
        filtered = jobs_ref.copy()
        enabled_val = filter_enabled_dropdown.value or "all"
        if enabled_val == "enabled":
            filtered = [j for j in filtered if j.get("enabled", True)]
        elif enabled_val == "disabled":
            filtered = [j for j in filtered if not j.get("enabled", True)]
        name_val = (filter_name_field.value or "").strip().lower()
        if name_val:
            filtered = [j for j in filtered if name_val in (j.get("name", "") or "").lower()]
        return filtered

    async def _load_agents() -> None:
        if not gateway_client or not gateway_client.connected:
            return
        try:
            result = await gateway_client.call("agents.list", timeout=5.0)
            agents_ref[:] = result.get("agents", [])
            opts = [ft.dropdown.Option(a.get("id", "main"), a.get("id", "main")) for a in agents_ref]
            if not any(o.key == "main" for o in opts):
                opts.insert(0, ft.dropdown.Option("main", "main"))
            add_agent_dropdown.options = opts or [ft.dropdown.Option("main", "main")]
            add_agent_dropdown.value = add_agent_dropdown.value or "main"
            _safe_update(add_agent_dropdown)
        except Exception:
            add_agent_dropdown.options = [ft.dropdown.Option("main", "main")]
            _safe_update(add_agent_dropdown)

    async def _refresh() -> None:
        cron_list.controls.clear()
        if not gateway_client or not gateway_client.connected:
            cron_list.controls.append(
                error_state(
                    t("cron.offline", default="Connect to gateway to view scheduled tasks."),
                    on_retry=_refresh,
                )
            )
            _safe_update(cron_list)
            return

        try:
            await _load_agents()
            result = await gateway_client.call("cron.list", timeout=10.0)
            jobs_ref[:] = result.get("jobs", [])
            filtered_jobs = _apply_filters()

            if not filtered_jobs:
                cron_list.controls.append(
                    empty_state_simple(
                        t("cron.empty", default="No scheduled tasks."),
                        icon=ft.Icons.SCHEDULE,
                    )
                )
            else:
                for job in filtered_jobs:
                    job_id = job.get("id", "")
                    enabled = job.get("enabled", True)
                    job_color = StatusColors.SUCCESS if enabled else theme.colors.muted
                    name = job.get("name", job.get("title", "Job"))
                    schedule = job.get("schedule", "")

                    async def _toggle_cb(jid: str, en: bool) -> None:
                        if gateway_client:
                            try:
                                await gateway_client.call("cron.toggle", {"id": jid, "enabled": not en})
                                await _refresh()
                            except Exception:
                                await _refresh()

                    toggle_btn = ft.IconButton(
                        icon=ft.Icons.TIMER if enabled else ft.Icons.TIMER_OFF,
                        icon_size=18,
                        tooltip=t("cron.toggle", default="Toggle") if enabled else t("cron.enable", default="Enable"),
                        on_click=lambda e, jid=job_id, en=enabled: _fire_async(_toggle_cb, jid, en),
                    )

                    async def _delete_cb(jid: str) -> None:
                        if gateway_client:
                            try:
                                await gateway_client.call("cron.remove", {"id": jid})
                                await _refresh()
                            except Exception:
                                pass

                    delete_btn = ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=16,
                        tooltip=t("cron.delete", default="Delete"),
                        on_click=lambda e, jid=job_id: _fire_async(_delete_cb, jid),
                    )

                    tile_content = ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.TIMER if enabled else ft.Icons.TIMER_OFF,
                                size=18,
                                color=job_color,
                            ),
                            ft.Column(
                                [
                                    ft.Text(name, weight=ft.FontWeight.BOLD, size=13),
                                    ft.Row(
                                        [
                                            status_chip(
                                                "enabled" if enabled else "disabled",
                                                job_color,
                                            ),
                                            ft.Text(schedule, size=11, color=theme.colors.muted),
                                            ft.Text(job.get("agentId", "main"), size=10, color=theme.colors.muted),
                                        ],
                                        spacing=8,
                                    ),
                                ],
                                spacing=4,
                                expand=True,
                                tight=True,
                            ),
                            toggle_btn,
                            delete_btn,
                        ],
                        spacing=8,
                    )
                    cron_list.controls.append(card_tile(tile_content))
            _safe_update(cron_list)
        except Exception as exc:
            cron_list.controls.clear()
            cron_list.controls.append(error_state(str(exc), on_retry=_refresh))
            _safe_update(cron_list)

        try:
            history = await gateway_client.call("cron.history", {"limit": 20}, timeout=10.0)
            records = history.get("records", [])
            cron_history_list.controls.clear()
            for rec in records:
                status = rec.get("status", "")
                color = {
                    "completed": StatusColors.SUCCESS,
                    "running": StatusColors.INFO,
                    "failed": StatusColors.ERROR,
                }.get(status, theme.colors.muted)
                started = rec.get("startedAt", rec.get("started_at", ""))
                if isinstance(started, int | float):
                    from datetime import UTC, datetime

                    started = datetime.fromtimestamp(started, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    started = str(started)[:19] if started else "-"
                cron_history_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(width=8, height=8, border_radius=4, bgcolor=color),
                                ft.Text(rec.get("jobTitle", rec.get("job_title", "")), size=12, expand=True),
                                ft.Text(started, size=10, color=theme.colors.muted),
                                status_chip(status, color),
                            ],
                            spacing=6,
                        ),
                        padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    )
                )
            _safe_update(cron_history_list)
        except Exception:
            cron_history_list.controls.clear()
            _safe_update(cron_history_list)

    async def _add_job(e: Any) -> None:
        if not gateway_client or not add_name.value or not add_schedule.value:
            return
        try:
            await gateway_client.call(
                "cron.add",
                {
                    "name": add_name.value,
                    "schedule": add_schedule.value,
                    "message": add_message.value or "",
                    "agentId": add_agent_dropdown.value or "main",
                },
            )
            add_name.value = ""
            add_schedule.value = ""
            add_message.value = ""
            await _refresh()
        except Exception:
            pass

    filter_enabled_dropdown.on_change = lambda e: _fire_async(_refresh)

    add_btn = ft.ElevatedButton(
        t("cron.add", default="Add Job"),
        icon=ft.Icons.ADD,
        on_click=lambda e: _fire_async(_add_job),
    )
    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        icon_size=20,
        on_click=lambda e: _fire_async(_refresh),
    )

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.SCHEDULE,
                t("nav.cron", default="Scheduled Tasks"),
                actions=[refresh_btn],
            ),
            ft.Container(
                content=ft.Row([filter_enabled_dropdown, filter_name_field], spacing=12),
                padding=ft.padding.symmetric(horizontal=16, vertical=8),
            ),
            cron_list,
            ft.Divider(height=1),
            ft.ExpansionTile(
                title=ft.Text(t("cron.add_job", default="Add Job"), size=14),
                controls=[
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Row([add_name, add_schedule, add_agent_dropdown], spacing=8),
                                add_message,
                                add_btn,
                            ],
                            spacing=8,
                        ),
                        padding=12,
                    )
                ],
            ),
            ft.Divider(height=1),
            ft.Container(
                content=ft.Text(t("cron.history", default="Execution History"), size=14, weight=ft.FontWeight.BOLD),
                padding=ft.padding.only(left=16, top=8, bottom=4),
            ),
            cron_history_list,
        ],
        spacing=0,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    _fire_async(_refresh)
    return panel
