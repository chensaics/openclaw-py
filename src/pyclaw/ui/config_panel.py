"""Config panel — raw JSON and form-based config editor."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import flet as ft

from pyclaw.ui.components import empty_state_simple, page_header
from pyclaw.ui.i18n import t
from pyclaw.ui.theme import get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def build_config_panel(
    *,
    gateway_client: Any = None,
    get_gateway_client: Any = None,
    on_feedback: Any = None,
) -> ft.Column:
    theme = get_theme()
    raw_text = ft.TextField(
        multiline=True,
        min_lines=12,
        expand=True,
        border=ft.InputBorder.NONE,
        filled=False,
        hint_text=t("config.raw_hint", default="JSON config..."),
        text_size=12,
    )
    raw_container = ft.Container(content=raw_text, expand=True)
    form_container = ft.Container(expand=True)
    schema_ref: dict[str, Any] = {}
    config_ref: dict[str, Any] = {}
    form_section_ref: dict[str, str] = {"current": ""}

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

    async def _load_config() -> None:
        gw = _resolve_gateway_client()
        if not gw or not gw.connected:
            _notify(t("config.offline", default="Connect to gateway to load config."))
            return
        try:
            result = await gw.call("config.get")
            config_ref.clear()
            config_ref.update(result.get("config", result))
            raw_text.value = json.dumps(config_ref, indent=2, ensure_ascii=False)
            raw_text.error_text = ""
            _safe_update(raw_text)
        except Exception as exc:
            _notify(t("config.load_failed", default="Failed to load config: {error}", error=str(exc)))

    async def _save_config() -> None:
        gw = _resolve_gateway_client()
        if not gw or not gw.connected:
            _notify(t("config.offline", default="Connect to gateway to load config."))
            return
        try:
            text = raw_text.value or "{}"
            obj = json.loads(text)
            await gw.call("config.save", {"config": obj})
            config_ref.clear()
            config_ref.update(obj)
            raw_text.error_text = ""
            _notify(t("config.saved", default="Config saved."))
        except json.JSONDecodeError as e:
            raw_text.error_text = str(e)
            _safe_update(raw_text)
            _notify(t("config.invalid_json", default="Invalid JSON: {error}", error=str(e)))
        except Exception as exc:
            _notify(t("config.save_failed", default="Failed to save config: {error}", error=str(exc)))

    async def _apply_config() -> None:
        gw = _resolve_gateway_client()
        if not gw or not gw.connected:
            _notify(t("config.offline", default="Connect to gateway to load config."))
            return
        try:
            await gw.call("config.apply")
            _notify(t("config.applied", default="Config applied."))
        except Exception as exc:
            _notify(t("config.apply_failed", default="Failed to apply config: {error}", error=str(exc)))

    def _build_form_controls(section: str, schema: dict[str, Any], config: dict[str, Any]) -> list[ft.Control]:
        controls: list[ft.Control] = []
        props = schema.get("properties", {})
        for key, prop in props.items():
            val = config.get(section, {}).get(key)
            ptype = prop.get("type", "string")
            desc = prop.get("description", "")
            if ptype == "boolean":
                sw = ft.Switch(
                    label=key,
                    value=bool(val),
                    on_change=lambda e, s=section, k=key: _on_form_change(s, k, e.control.value),
                )
                if desc:
                    sw.label = f"{key}: {desc}"
                controls.append(sw)
            elif prop.get("enum"):
                dd = ft.Dropdown(
                    label=key,
                    value=str(val) if val is not None else None,
                    options=[ft.dropdown.Option(str(o)) for o in prop["enum"]],
                    on_change=lambda e, s=section, k=key, p=ptype: _on_form_change(s, k, e.control.value, p),
                )
                controls.append(dd)
            else:
                tf = ft.TextField(
                    label=key,
                    value=str(val) if val is not None else "",
                    dense=True,
                    on_change=lambda e, s=section, k=key, p=ptype: _on_form_change(s, k, e.control.value, p),
                )
                controls.append(tf)
        return controls

    def _on_form_change(section: str, key: str, value: Any, value_type: str = "string") -> None:
        if section not in config_ref:
            config_ref[section] = {}
        config_ref[section][key] = _coerce_config_value(value, value_type)

    async def _save_form_and_sync() -> None:
        gw = _resolve_gateway_client()
        if not gw or not gw.connected:
            _notify(t("config.offline", default="Connect to gateway to load config."))
            return
        try:
            await gw.call("config.save", {"config": config_ref})
            raw_text.value = json.dumps(config_ref, indent=2, ensure_ascii=False)
            _safe_update(raw_text)
            _notify(t("config.saved", default="Config saved."))
        except Exception as exc:
            _notify(t("config.save_failed", default="Failed to save config: {error}", error=str(exc)))

    async def _load_schema() -> bool:
        gw = _resolve_gateway_client()
        if not gw or not gw.connected:
            return False
        try:
            result = await gw.call("config.schema")
            schema_ref.clear()
            schema_ref.update(result)
            return True
        except Exception:
            return False

    def _build_form_view() -> ft.Control:
        schema = schema_ref.get("sections", schema_ref)
        if not schema:
            return empty_state_simple(
                t("config.no_schema", default="Schema not available. Use Raw mode."),
                icon=ft.Icons.SCHEMA,
            )
        sections = list(schema.keys()) if isinstance(schema, dict) else []
        if not sections:
            return empty_state_simple(
                t("config.no_sections", default="No config sections."),
                icon=ft.Icons.SCHEMA,
            )

        nav_items: list[ft.Control] = []
        for sec in sections:
            btn = ft.TextButton(
                sec,
                on_click=lambda e, s=sec: _on_section_click(s),
            )
            btn.data = sec
            nav_items.append(btn)

        form_content = ft.Column(spacing=12, expand=True, scroll=ft.ScrollMode.AUTO)
        form_content_ref: dict[str, ft.Column] = {"col": form_content}

        def _on_section_click(sec: str) -> None:
            form_section_ref["current"] = sec
            form_content_ref["col"].controls.clear()
            section_schema = schema.get(sec, {}) if isinstance(schema, dict) else {}
            form_content_ref["col"].controls.extend(
                _build_form_controls(sec, section_schema, config_ref),
            )
            _safe_update(form_content_ref["col"])

        default_sec = sections[0] if sections else ""
        if default_sec and not form_section_ref["current"]:
            form_section_ref["current"] = default_sec
            form_content.controls.extend(
                _build_form_controls(default_sec, schema.get(default_sec, {}), config_ref),
            )

        return ft.Row(
            [
                ft.Container(
                    content=ft.Column(
                        [ft.Text(t("config.sections", default="Sections"), size=12, weight=ft.FontWeight.W_500)]
                        + nav_items,
                        spacing=4,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=160,
                    border=ft.Border.only(right=ft.BorderSide(0.5, theme.colors.border)),
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            form_content,
                            ft.Button(
                                t("config.save", default="Save"),
                                icon=ft.Icons.SAVE,
                                on_click=lambda e: _fire_async(_save_form_and_sync),
                            ),
                        ],
                        spacing=12,
                        expand=True,
                    ),
                    padding=16,
                    expand=True,
                ),
            ],
            expand=True,
        )

    async def _init_form() -> None:
        has_schema = await _load_schema()
        if has_schema:
            await _load_config()
        form_container.content = _build_form_view()
        _safe_update(form_container)

    raw_content = ft.Column(
        [
            ft.Row(
                [
                    ft.Button(
                        t("config.load", default="Load"),
                        icon=ft.Icons.DOWNLOAD,
                        on_click=lambda e: _fire_async(_load_config),
                    ),
                    ft.Button(
                        t("config.save", default="Save"),
                        icon=ft.Icons.SAVE,
                        on_click=lambda e: _fire_async(_save_config),
                    ),
                    ft.OutlinedButton(
                        t("config.apply", default="Apply"),
                        icon=ft.Icons.PLAY_ARROW,
                        on_click=lambda e: _fire_async(_apply_config),
                    ),
                ],
                spacing=8,
            ),
            raw_container,
        ],
        expand=True,
        spacing=12,
    )
    form_content = form_container

    tab_pages = [raw_content, form_content]
    tab_content_area = ft.Column(controls=[raw_content], expand=True)

    def _on_tab_change(e: Any) -> None:
        idx = e.control.selected_index if hasattr(e.control, "selected_index") else 0
        tab_content_area.controls = [tab_pages[idx]] if idx < len(tab_pages) else [tab_pages[0]]
        _safe_update(tab_content_area)

    tabs = ft.Tabs(
        content=ft.Column(controls=[], expand=True),
        length=2,
        selected_index=0,
        on_change=_on_tab_change,
        expand=True,
    )
    tabs.content = tab_content_area

    tab_bar = ft.Row(
        [
            ft.TextButton(
                t("config.raw_tab", default="Raw JSON"),
                on_click=lambda e: _switch_tab(0),
            ),
            ft.TextButton(
                t("config.form_tab", default="Form"),
                on_click=lambda e: _switch_tab(1),
            ),
        ],
        spacing=4,
    )

    def _switch_tab(idx: int) -> None:
        tab_content_area.controls = [tab_pages[idx]] if idx < len(tab_pages) else [tab_pages[0]]
        _safe_update(tab_content_area)

    panel = ft.Column(
        controls=[
            page_header(
                ft.Icons.SETTINGS,
                t("config.title", default="Config"),
                actions=[],
            ),
            ft.Container(
                content=ft.Column(
                    [tab_bar, tab_content_area],
                    expand=True,
                    spacing=8,
                ),
                padding=16,
                expand=True,
            ),
        ],
        expand=True,
        spacing=0,
    )

    _fire_async(_load_config)
    _fire_async(_init_form)
    return panel


def _coerce_config_value(value: Any, value_type: str) -> Any:
    tpe = (value_type or "string").lower()
    if tpe == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off", ""}:
                return False
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)
    if tpe == "integer":
        try:
            return int(str(value).strip())
        except Exception:
            return value
    if tpe == "number":
        try:
            return float(str(value).strip())
        except Exception:
            return value
    if tpe in {"array", "object"}:
        if isinstance(value, str):
            text = value.strip()
            if text:
                try:
                    return json.loads(text)
                except Exception:
                    return value
        return value
    return value
