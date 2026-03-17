"""System panel — system info, doctor checks, logs tail, and backup."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import flet as ft

from pyclaw.ui.components import error_state, page_header
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme

logger = logging.getLogger(__name__)


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_system_panel(
    *,
    gateway_client: Any = None,
    on_snackbar: Any = None,
) -> ft.Column:
    gw = gateway_client
    system_info_col = ft.Column(spacing=4)
    system_logs_list = ft.ListView(spacing=2, height=300)

    def _safe_update(ctrl: ft.Control) -> None:
        try:
            ctrl.update()
        except Exception:
            pass

    def _snackbar(msg: str) -> None:
        if on_snackbar:
            on_snackbar(msg)

    async def _refresh() -> None:
        nonlocal gw
        if not gw or not gw.connected:
            system_info_col.controls = [
                error_state(
                    "请连接 Gateway 以查看系统信息",
                    on_retry=_refresh,
                ),
            ]
            _safe_update(system_info_col)
            return
        try:
            info = await gw.call("system.info")
            system_info_col.controls.clear()
            for key, val in info.items():
                system_info_col.controls.append(
                    ft.Row(
                        [
                            ft.Text(key, weight=ft.FontWeight.BOLD, size=12, width=150),
                            ft.Text(str(val), size=12),
                        ],
                        spacing=8,
                    )
                )
            _safe_update(system_info_col)
        except Exception:
            logger.warning("_refresh_system (info) failed", exc_info=True)
            system_info_col.controls = [
                error_state("加载失败", on_retry=_refresh),
            ]
            _safe_update(system_info_col)

        try:
            logs_result = await gw.call("logs.tail", {"limit": 50})
            lines = logs_result.get("lines", [])
            system_logs_list.controls.clear()
            for line in lines:
                text = line if isinstance(line, str) else str(line)
                system_logs_list.controls.append(ft.Text(text, size=10, font_family="monospace", max_lines=2))
            _safe_update(system_logs_list)
        except Exception:
            logger.warning("_refresh_system (logs) failed", exc_info=True)

    async def _export_backup() -> None:
        if gw:
            try:
                result = await gw.call("backup.export")
                path = result.get("path", "backup completed")
                _snackbar(f"Backup exported: {path}")
            except Exception as exc:
                _snackbar(f"Backup failed: {exc}")

    async def _run_doctor() -> None:
        if gw:
            try:
                cur_theme = get_theme()
                result = await gw.call("doctor.run")
                checks = result.get("checks", result)
                system_info_col.controls.clear()
                system_info_col.controls.append(ft.Text("Doctor Results", size=14, weight=ft.FontWeight.BOLD))
                if isinstance(checks, list):
                    for check in checks:
                        name = check.get("name", "")
                        status = check.get("status", "")
                        color = cur_theme.colors.success if status == "ok" else cur_theme.colors.error
                        system_info_col.controls.append(
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.CHECK_CIRCLE if status == "ok" else ft.Icons.ERROR,
                                        size=16,
                                        color=color,
                                    ),
                                    ft.Text(name, size=12, expand=True),
                                    ft.Text(status, size=12, color=color),
                                ],
                                spacing=4,
                            )
                        )
                elif isinstance(checks, dict):
                    for k, v in checks.items():
                        system_info_col.controls.append(
                            ft.Row(
                                [
                                    ft.Text(k, size=12, weight=ft.FontWeight.BOLD, width=150),
                                    ft.Text(str(v), size=12),
                                ],
                                spacing=4,
                            )
                        )
                _safe_update(system_info_col)
            except Exception:
                logger.warning("_run_doctor failed", exc_info=True)

    backup_btn = ft.OutlinedButton(
        "Export Backup",
        icon=ft.Icons.BACKUP,
        on_click=lambda e: _fire_async(_export_backup),
    )
    doctor_btn = ft.OutlinedButton(
        "Run Doctor",
        icon=ft.Icons.HEALTH_AND_SAFETY,
        on_click=lambda e: _fire_async(_run_doctor),
    )

    col = ft.Column(
        controls=[
            page_header(
                ft.Icons.MONITOR_HEART,
                t("nav.system", default="System"),
                [
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_size=20,
                        on_click=lambda e: _fire_async(_refresh),
                    )
                ],
            ),
            ft.Container(content=system_info_col, padding=ft.Padding.all(16)),
            ft.Divider(height=1),
            ft.Container(
                content=ft.Row([backup_btn, doctor_btn], spacing=8),
                padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            ),
            ft.Divider(height=1),
            ft.Container(
                content=ft.Text("Logs", size=14, weight=ft.FontWeight.BOLD),
                padding=ft.Padding.only(left=16, top=8, bottom=4),
            ),
            system_logs_list,
        ],
        spacing=0,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    col.refresh = _refresh
    return col
