"""Skills panel — skill list with toggle, apiKey edit, and install."""

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


def build_skills_panel(*, gateway_client: Any = None) -> ft.Column:
    theme = get_theme()
    skill_list = ft.ListView(expand=True, spacing=6)
    search_field = ft.TextField(
        hint_text=t("skills.search", default="Search..."),
        dense=True,
        prefix_icon=ft.Icons.SEARCH,
        height=36,
        text_size=12,
        expand=True,
        on_change=lambda e: _apply_filters(),
    )
    raw_skills_ref: list[dict[str, Any]] = []

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _apply_filters() -> None:
        search_lower = (search_field.value or "").lower()
        skill_list.controls.clear()
        for skill in raw_skills_ref:
            name = (skill.get("name") or "").lower()
            desc = (skill.get("description") or "").lower()
            if search_lower and search_lower not in name and search_lower not in desc:
                continue
            skill_list.controls.append(_build_skill_tile(skill))
        _safe_update(skill_list)

    def _build_skill_tile(skill: dict[str, Any]) -> ft.Control:
        skill_id = skill.get("id", "")
        name = skill.get("name", skill_id or "?")
        description = skill.get("description", "")
        enabled = skill.get("enabled", True)
        missing_deps = skill.get("missingDeps") or []
        install_cmd = skill.get("installCommand", "")
        has_api_key_field = skill.get("apiKeyRequired", False)
        api_key_placeholder = skill.get("apiKeyPlaceholder", "API Key")

        toggle = ft.Switch(
            value=enabled,
            on_change=lambda e, sid=skill_id: _fire_async(_toggle_skill, sid, e.control.value),
        )

        expand_content = ft.Column(spacing=8, visible=False)

        if has_api_key_field:
            api_key_tf = ft.TextField(
                label=api_key_placeholder,
                password=True,
                dense=True,
                value=skill.get("apiKey", "") or "",
                on_submit=lambda e, sid=skill_id: _fire_async(_set_api_key, sid, e.control.value),
            )
            api_key_btn = ft.ElevatedButton(
                t("skills.save_key", default="Save"),
                on_click=lambda e, sid=skill_id: _fire_async(_set_api_key, sid, api_key_tf.value),
            )
            expand_content.controls.append(
                ft.Row([api_key_tf, api_key_btn], spacing=8),
            )

        def _on_expand_click(e: ft.ControlEvent) -> None:
            ref = getattr(expand_content, "_ref", None)
            if ref is None:
                ref = {"expanded": False}
                expand_content._ref = ref
            ref["expanded"] = not ref["expanded"]
            expand_content.visible = ref["expanded"]
            expand_content.update()

        row_controls: list[ft.Control] = [
            ft.Icon(ft.Icons.AUTO_AWESOME, size=18, color=theme.colors.primary),
            ft.Column(
                [
                    ft.Text(name, size=14, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        description or "-",
                        size=12,
                        color=theme.colors.muted,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=2,
                expand=True,
                tight=True,
            ),
            toggle,
        ]
        if has_api_key_field:
            expand_btn = ft.IconButton(
                icon=ft.Icons.KEY,
                tooltip=t("skills.edit_api_key", default="Edit API Key"),
                icon_size=18,
                on_click=_on_expand_click,
            )
            row_controls.append(expand_btn)
        if install_cmd:
            install_btn = ft.OutlinedButton(
                t("skills.install", default="Install"),
                icon=ft.Icons.DOWNLOAD,
                icon_size=16,
                on_click=lambda e, sid=skill_id, cmd=install_cmd: _fire_async(_show_install_hint, sid, cmd),
            )
            row_controls.append(install_btn)

        tile_content = ft.Column(
            [
                ft.Row(row_controls, spacing=8),
                ft.Container(content=expand_content),
            ],
            spacing=6,
        )

        if missing_deps:
            deps_text = ft.Text(
                t("skills.missing_deps", default="Missing deps: ") + ", ".join(missing_deps),
                size=11,
                color=theme.colors.error,
            )
            tile_content.controls.insert(1, deps_text)

        return card_tile(content=tile_content)

    async def _toggle_skill(sid: str, enabled: bool) -> None:
        if not gateway_client or not gateway_client.connected:
            return
        try:
            await gateway_client.call("skills.toggle", {"id": sid, "enabled": enabled})
            await _refresh()
        except Exception:
            pass

    async def _set_api_key(sid: str, key: str | None) -> None:
        if not gateway_client or not gateway_client.connected:
            return
        try:
            await gateway_client.call("skills.setKey", {"id": sid, "apiKey": key or ""})
            await _refresh()
        except Exception:
            pass

    async def _show_install_hint(sid: str, cmd: str) -> None:
        def _on_dialog_close(e: ft.ControlEvent) -> None:
            dlg.open = False
            if dlg.page:
                dlg.page.overlay.remove(dlg)
                dlg.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(t("skills.install_title", default="Install Command")),
            content=ft.Text(cmd),
            actions=[
                ft.TextButton(t("common.close", default="Close"), on_click=_on_dialog_close),
            ],
        )
        page = skill_list.page if skill_list else None
        if page:
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

    async def _refresh() -> None:
        skill_list.controls.clear()
        if not gateway_client or not gateway_client.connected:
            skill_list.controls.append(
                error_state(
                    t("skills.offline", default="Connect to gateway to view skills."),
                    on_retry=_refresh,
                )
            )
            _safe_update(skill_list)
            return

        try:
            result = await gateway_client.call("skills.list")
            raw_skills_ref[:] = result.get("skills", [])
            _apply_filters()
            if not raw_skills_ref:
                skill_list.controls.append(
                    empty_state_simple(
                        t("skills.empty", default="No skills."),
                        icon=ft.Icons.AUTO_AWESOME,
                    )
                )
            _safe_update(skill_list)
        except Exception as exc:
            skill_list.controls.clear()
            skill_list.controls.append(error_state(str(exc), on_retry=_refresh))
            _safe_update(skill_list)

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip=t("channels.refresh", default="Refresh"),
        icon_size=20,
        on_click=lambda e: _fire_async(_refresh),
    )

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.AUTO_AWESOME,
                t("skills.title", default="Skills"),
                actions=[refresh_btn],
            ),
            ft.Container(
                content=ft.Row([search_field, refresh_btn], spacing=8),
                padding=ft.padding.symmetric(horizontal=16, vertical=8),
            ),
            skill_list,
        ],
        expand=True,
        spacing=0,
    )

    _fire_async(_refresh)
    return panel
