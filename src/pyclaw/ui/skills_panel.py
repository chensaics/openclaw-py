"""Skills panel — skill list with toggle, apiKey edit, and install."""

from __future__ import annotations

import asyncio
import json
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


def build_skills_panel(
    *,
    gateway_client: Any = None,
    get_gateway_client: Any = None,
    on_feedback: Any = None,
) -> ft.Column:
    theme = get_theme()
    special_skill_meta: dict[str, dict[str, Any]] = {
        "claw-wechat-article": {
            "display_name": "claw-wechat-article",
            "display_description": "微信公众号发布助手：支持本地发布、远程 wenyan-mcp 发布、视频草稿发布与凭证探测。",
            "quick_actions": [
                {"label": "本地发布向导", "preset": {"remote": False, "use_video": "auto"}},
                {"label": "远程发布向导", "preset": {"remote": True, "use_video": "false"}},
                {"label": "视频发布向导", "preset": {"remote": False, "use_video": "true"}},
            ],
        },
        "claw-redbook-auto": {
            "display_name": "claw-redbook-auto",
            "display_description": "小红书自动化助手：覆盖登录检测、发布、检索、互动与数据分析工作流。",
            "quick_actions": [
                {"label": "发布向导", "preset": {"intent": "publish", "mode": "headless"}},
                {"label": "检索向导", "preset": {"intent": "explore", "mode": "headless"}},
                {"label": "互动向导", "preset": {"intent": "interact", "mode": "headless"}},
            ],
        },
    }
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

    def _resolve_gateway_client() -> Any:
        if callable(get_gateway_client):
            try:
                return get_gateway_client()
            except Exception:
                return None
        return gateway_client

    def _safe_update(control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass

    def _notify(message: str) -> None:
        if not message:
            return
        if on_feedback:
            try:
                on_feedback(message)
            except Exception:
                pass

    def _apply_filters() -> None:
        search_lower = (search_field.value or "").lower()
        skill_list.controls.clear()
        for skill in raw_skills_ref:
            sid = str(skill.get("id", "") or "")
            meta = special_skill_meta.get(sid, {})
            name = str(meta.get("display_name") or skill.get("name") or "").lower()
            desc = str(meta.get("display_description") or skill.get("description") or "").lower()
            if search_lower and search_lower not in name and search_lower not in desc:
                continue
            skill_list.controls.append(_build_skill_tile(skill))
        _safe_update(skill_list)

    def _build_skill_tile(skill: dict[str, Any]) -> ft.Control:
        skill_id = skill.get("id", "")
        meta = special_skill_meta.get(skill_id, {})
        name = meta.get("display_name", skill.get("name", skill_id or "?"))
        description = meta.get("display_description", skill.get("description", ""))
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
            api_key_btn = ft.Button(
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
        quick_actions = meta.get("quick_actions") or []
        tile_content = ft.Column(
            [
                ft.Row(row_controls, spacing=8),
                ft.Container(content=expand_content),
            ],
            spacing=6,
        )
        if quick_actions:
            quick_buttons = ft.Row(
                controls=[
                    ft.TextButton(
                        str(action.get("label", "向导")),
                        on_click=lambda e, sid=skill_id, preset=dict(action.get("preset") or {}): _fire_async(
                            _open_publish_wizard, sid, preset
                        ),
                    )
                    for action in quick_actions
                ],
                spacing=2,
                wrap=True,
            )
            tile_content.controls.append(quick_buttons)

        if missing_deps:
            deps_text = ft.Text(
                t("skills.missing_deps", default="Missing deps: ") + ", ".join(missing_deps),
                size=11,
                color=theme.colors.error,
            )
            tile_content.controls.insert(1, deps_text)

        return card_tile(content=tile_content)

    async def _toggle_skill(sid: str, enabled: bool) -> None:
        gw = _resolve_gateway_client()
        if not gw or not gw.connected:
            _notify(t("skills.offline", default="Connect to gateway to view skills."))
            return
        try:
            await gw.call("skills.toggle", {"id": sid, "enabled": enabled})
            await _refresh()
            _notify(t("skills.toggle_saved", default="Skill status updated."))
        except Exception as exc:
            _notify(t("skills.toggle_failed", default="Failed to update skill: {error}", error=str(exc)))

    async def _set_api_key(sid: str, key: str | None) -> None:
        gw = _resolve_gateway_client()
        if not gw or not gw.connected:
            _notify(t("skills.offline", default="Connect to gateway to view skills."))
            return
        try:
            await gw.call("skills.setKey", {"id": sid, "apiKey": key or ""})
            await _refresh()
            _notify(t("skills.key_saved", default="Skill API key saved."))
        except Exception as exc:
            _notify(t("skills.key_failed", default="Failed to save API key: {error}", error=str(exc)))

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

    async def _open_publish_wizard(skill_id: str, preset: dict[str, Any]) -> None:
        page = skill_list.page if skill_list else None
        if page is None:
            return

        def _close_dialog(e: ft.ControlEvent | None = None) -> None:
            dlg.open = False
            if dlg in page.overlay:
                page.overlay.remove(dlg)
            page.update()

        def _payload_for_skill() -> dict[str, Any]:
            if skill_id == "claw-wechat-article":
                return {
                    "action": "publish",
                    "article_path": article_path_tf.value or "",
                    "remote": bool(remote_sw.value),
                    "use_video": use_video_dd.value or "auto",
                    "theme": theme_tf.value or "lapis",
                    "highlight": highlight_tf.value or "solarized-light",
                    "dry_run": bool(dry_run_sw.value),
                }
            return {
                "intent": intent_dd.value or "publish",
                "account": account_tf.value or "default",
                "mode": mode_dd.value or "headless",
            }

        async def _copy_payload(e: ft.ControlEvent) -> None:
            payload_obj = _payload_for_skill()
            payload_text = json.dumps(payload_obj, ensure_ascii=False)
            await page.set_clipboard_async(payload_text)
            _notify(f"已复制 payload：{payload_text}")

        def _show_preview(e: ft.ControlEvent) -> None:
            payload_obj = _payload_for_skill()
            payload_text = json.dumps(payload_obj, ensure_ascii=False)
            command = f"pyclaw skills run {skill_id} --payload '{payload_text}' --json"
            _notify(command)

        article_path_tf = ft.TextField(
            label="文章路径",
            hint_text="/path/to/article.md",
            dense=True,
            visible=skill_id == "claw-wechat-article",
        )
        remote_sw = ft.Switch(
            label="远程发布",
            value=bool(preset.get("remote", False)),
            visible=skill_id == "claw-wechat-article",
        )
        use_video_dd = ft.Dropdown(
            label="视频处理",
            dense=True,
            options=[
                ft.dropdown.Option("auto", "自动"),
                ft.dropdown.Option("true", "强制视频模式"),
                ft.dropdown.Option("false", "禁用视频模式"),
            ],
            value=str(preset.get("use_video", "auto")),
            visible=skill_id == "claw-wechat-article",
        )
        theme_tf = ft.TextField(
            label="主题",
            value="lapis",
            dense=True,
            visible=skill_id == "claw-wechat-article",
        )
        highlight_tf = ft.TextField(
            label="代码高亮",
            value="solarized-light",
            dense=True,
            visible=skill_id == "claw-wechat-article",
        )
        dry_run_sw = ft.Switch(
            label="仅预演（dry_run）",
            value=True,
            visible=skill_id == "claw-wechat-article",
        )

        intent_dd = ft.Dropdown(
            label="任务意图",
            dense=True,
            options=[
                ft.dropdown.Option("publish", "发布"),
                ft.dropdown.Option("explore", "检索"),
                ft.dropdown.Option("interact", "互动"),
                ft.dropdown.Option("analytics", "分析"),
            ],
            value=str(preset.get("intent", "publish")),
            visible=skill_id == "claw-redbook-auto",
        )
        account_tf = ft.TextField(
            label="账号标识",
            value="default",
            dense=True,
            visible=skill_id == "claw-redbook-auto",
        )
        mode_dd = ft.Dropdown(
            label="运行模式",
            dense=True,
            options=[
                ft.dropdown.Option("headless", "headless"),
                ft.dropdown.Option("headed", "headed"),
            ],
            value=str(preset.get("mode", "headless")),
            visible=skill_id == "claw-redbook-auto",
        )

        content = ft.Column(
            [
                ft.Text(f"{skill_id} 发布向导", weight=ft.FontWeight.BOLD),
                article_path_tf,
                remote_sw,
                use_video_dd,
                theme_tf,
                highlight_tf,
                dry_run_sw,
                intent_dd,
                account_tf,
                mode_dd,
            ],
            tight=True,
            spacing=8,
        )
        dlg = ft.AlertDialog(
            title=ft.Text("技能快捷向导"),
            content=content,
            actions=[
                ft.TextButton("复制 payload", on_click=lambda e: _fire_async(_copy_payload, e)),
                ft.TextButton("显示运行命令", on_click=_show_preview),
                ft.TextButton(t("common.close", default="Close"), on_click=_close_dialog),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    async def _refresh() -> None:
        skill_list.controls.clear()
        gw = _resolve_gateway_client()
        if not gw or not gw.connected:
            skill_list.controls.append(
                error_state(
                    t("skills.offline", default="Connect to gateway to view skills."),
                    on_retry=_refresh,
                )
            )
            _safe_update(skill_list)
            return

        try:
            result = await gw.call("skills.list")
            raw_skills_ref[:] = result.get("skills", [])
            _apply_filters()
            if not raw_skills_ref:
                skill_list.controls.append(
                    empty_state(
                        ft.Icons.AUTO_AWESOME,
                        t("skills.empty", default="No skills."),
                        action_label=t("channels.refresh", default="Refresh"),
                        on_action=lambda e: _fire_async(_refresh),
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
                padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            ),
            skill_list,
        ],
        expand=True,
        spacing=0,
    )

    _fire_async(_refresh)
    return panel
