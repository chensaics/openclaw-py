"""Reusable UI components — shared building blocks for Flet pages.

Provides standardised components that maintain visual consistency
across all panels, backported from Flutter reference design patterns.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import flet as ft

from pyclaw.ui.theme import get_theme


def _fire_async(handler: Any, *args: Any) -> None:
    """Schedule an async handler from a sync callback (e.g. button on_click)."""
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


def error_state(message: str, on_retry: Any = None) -> ft.Container:
    """Standard error state: icon + message + optional retry button."""
    from pyclaw.ui.i18n import t

    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=ft.Colors.ERROR),
                ft.Text(message, size=14, color=ft.Colors.ERROR),
                *(
                    [
                        ft.Button(
                            t("common.retry", default="Retry"),
                            on_click=lambda e: _fire_async(on_retry),
                        )
                    ]
                    if on_retry
                    else []
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
        ),
        alignment=ft.Alignment(0, 0),
        expand=True,
    )


def empty_state_simple(message: str, icon: str = ft.Icons.INBOX) -> ft.Container:
    """Simple empty state: icon + message, no action button."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(icon, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(message, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
        ),
        alignment=ft.Alignment(0, 0),
        expand=True,
    )


def page_header(
    icon: str,
    title: str,
    actions: list[ft.Control] | None = None,
) -> ft.Container:
    """Standard page header: icon + title + trailing actions.

    Follows the Flutter page header pattern: 16h/8v padding, bottom border,
    surface background, icon(20px, primary) + 8px gap + titleMedium title.
    """
    theme = get_theme()
    controls: list[ft.Control] = [
        ft.Icon(icon, size=20, color=theme.colors.primary),
        ft.Container(width=8),
        ft.Text(title, size=18, weight=ft.FontWeight.BOLD, expand=True),
    ]
    if actions:
        controls.extend(actions)

    return ft.Container(
        content=ft.Row(controls),
        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        border=ft.Border.only(bottom=ft.BorderSide(0.5, theme.colors.border)),
    )


def empty_state(
    icon: str,
    message: str,
    *,
    action_label: str = "",
    on_action: Any = None,
) -> ft.Container:
    """Empty state placeholder: 48px icon + message + optional action.

    Backported from Flutter feature page empty states.
    """
    theme = get_theme()
    children: list[ft.Control] = [
        ft.Icon(icon, size=48, color=ft.Colors.with_opacity(0.4, theme.colors.primary)),
        ft.Container(height=12),
        ft.Text(
            message,
            size=14,
            color=theme.colors.muted,
            text_align=ft.TextAlign.CENTER,
        ),
    ]
    if action_label and on_action:
        children.append(ft.Container(height=16))
        children.append(
            ft.OutlinedButton(action_label, on_click=on_action),
        )

    return ft.Container(
        content=ft.Column(
            children,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        expand=True,
        alignment=ft.Alignment(0, 0),
        padding=ft.Padding.all(32),
    )


def card_tile(
    content: ft.Control,
    *,
    on_click: Any = None,
    data: Any = None,
) -> ft.Container:
    """Standardised list-item card: radius 16, elevation 0, outlineVariant border.

    Follows Flutter SessionTile / list tile pattern.
    """
    theme = get_theme()
    return ft.Container(
        content=content,
        padding=ft.Padding.all(12),
        border_radius=ft.BorderRadius.all(theme.card_border_radius),
        bgcolor=theme.colors.surface_container,
        border=ft.Border.all(0.5, theme.colors.border),
        on_click=on_click,
        data=data,
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )


def status_chip(
    label: str,
    color: str,
) -> ft.Container:
    """Small coloured status chip.

    Background uses color at 20% alpha, text uses full color.
    """
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_500),
        bgcolor=ft.Colors.with_opacity(0.15, color),
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=ft.BorderRadius.all(8),
    )


def slider_input(
    label: str,
    min_val: float,
    max_val: float,
    value: float,
    *,
    step: float = 0.1,
    unit: str = "",
    tooltip: str = "",
    on_change: Callable[[float], Any] | None = None,
) -> ft.Column:
    """Slider + numeric input combo with optional tooltip."""
    theme = get_theme()
    value_field = ft.TextField(
        value=f"{value:g}{unit}",
        width=96,
        dense=True,
        text_align=ft.TextAlign.RIGHT,
    )

    def _sync_from_slider(e: ft.ControlEvent) -> None:
        current = float(e.control.value or value)
        value_field.value = f"{current:g}{unit}"
        if value_field.page:
            value_field.update()
        if on_change:
            on_change(current)

    def _sync_from_text(e: ft.ControlEvent) -> None:
        text = (e.control.value or "").strip().replace(unit, "").strip()
        try:
            parsed = float(text)
        except ValueError:
            return
        parsed = max(min_val, min(max_val, parsed))
        slider.value = parsed
        if slider.page:
            slider.update()
        if on_change:
            on_change(parsed)

    divisions = int(round((max_val - min_val) / step)) if step > 0 else None
    slider = ft.Slider(
        min=min_val,
        max=max_val,
        value=value,
        divisions=divisions,
        on_change=_sync_from_slider,
        expand=True,
    )
    value_field.on_submit = _sync_from_text
    value_field.on_blur = _sync_from_text

    title_controls: list[ft.Control] = [ft.Text(label, size=13, weight=ft.FontWeight.W_500)]
    if tooltip:
        title_controls.append(
            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=theme.colors.muted, tooltip=tooltip),
        )
    title_controls.extend([ft.Container(expand=True), value_field])

    return ft.Column(
        controls=[
            ft.Row(title_controls, spacing=6),
            slider,
        ],
        spacing=6,
        tight=True,
    )


def switch_with_info(
    label: str,
    value: bool,
    *,
    description: str = "",
    tooltip: str = "",
    on_change: Callable[[bool], Any] | None = None,
) -> ft.Row:
    """Switch row with supporting description and info tooltip."""
    theme = get_theme()

    def _on_toggle(e: ft.ControlEvent) -> None:
        if on_change:
            on_change(bool(e.control.value))

    switch = ft.Switch(value=value, on_change=_on_toggle)
    title_row_controls: list[ft.Control] = [ft.Text(label, size=13, weight=ft.FontWeight.W_500)]
    if tooltip:
        title_row_controls.append(
            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=theme.colors.muted, tooltip=tooltip),
        )

    text_controls: list[ft.Control] = [ft.Row(title_row_controls, spacing=6)]
    if description:
        text_controls.append(
            ft.Text(description, size=11, color=theme.colors.muted),
        )

    return ft.Row(
        controls=[
            switch,
            ft.Column(text_controls, spacing=2, tight=True, expand=True),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.START,
        spacing=10,
    )


def expandable_section(
    title: str,
    icon: str,
    content: ft.Control,
    *,
    initially_expanded: bool = False,
    on_expand: Callable[[bool], Any] | None = None,
) -> ft.Container:
    """Collapsible section container used by Settings."""
    theme = get_theme()
    expanded_state = {"value": initially_expanded}

    arrow = ft.Icon(
        ft.Icons.EXPAND_LESS if initially_expanded else ft.Icons.EXPAND_MORE,
        size=20,
        color=theme.colors.muted,
    )
    body = ft.Container(content=content, visible=initially_expanded, padding=ft.Padding.all(12))

    def _toggle(_e: ft.ControlEvent) -> None:
        expanded_state["value"] = not expanded_state["value"]
        body.visible = expanded_state["value"]
        arrow.icon = ft.Icons.EXPAND_LESS if expanded_state["value"] else ft.Icons.EXPAND_MORE
        if body.page:
            body.update()
        if arrow.page:
            arrow.update()
        if on_expand:
            on_expand(expanded_state["value"])

    header = ft.Container(
        content=ft.Row(
            [
                arrow,
                ft.Icon(icon, size=18, color=theme.colors.primary),
                ft.Text(title, size=14, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        on_click=_toggle,
    )

    return ft.Container(
        content=ft.Column([header, body], spacing=0, tight=True),
        border=ft.Border.all(0.5, theme.colors.border),
        border_radius=10,
    )


def quick_action_card(
    icon: str,
    title: str,
    description: str,
    actions: list[dict[str, Any]],
    *,
    on_click: Any = None,
) -> ft.Container:
    """Quick action card with one-line action chips."""
    theme = get_theme()
    action_controls = [
        ft.OutlinedButton(
            a.get("label", ""),
            icon=a.get("icon"),
            on_click=a.get("on_click"),
        )
        for a in actions
    ]
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [ft.Icon(icon, size=20, color=theme.colors.primary), ft.Text(title, weight=ft.FontWeight.W_600)]
                ),
                ft.Text(description, size=12, color=theme.colors.muted),
                ft.Row(action_controls, spacing=8, wrap=True),
            ],
            spacing=8,
            tight=True,
        ),
        padding=ft.Padding.all(12),
        border=ft.Border.all(0.5, theme.colors.border),
        border_radius=12,
        bgcolor=theme.colors.surface_container,
        on_click=on_click,
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )


def streaming_indicator() -> ft.Row:
    """Three-dot typing indicator for streaming responses.

    Backported from Flutter message_bubble.dart streaming indicator.
    Returns a Row with three animated dots.
    """
    theme = get_theme()
    dots: list[ft.Control] = []
    for _i in range(3):
        dots.append(
            ft.Container(
                width=7,
                height=7,
                border_radius=4,
                bgcolor=theme.colors.muted,
                opacity=0.4,
                animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
            )
        )
    return ft.Row(dots, spacing=4, alignment=ft.MainAxisAlignment.START)


async def pulse_streaming_dots(dots_row: ft.Row, *, running: bool = True) -> None:
    """Animate the three dots in sequence to create a typing pulse."""
    import asyncio

    dots = [c for c in dots_row.controls if isinstance(c, ft.Container)]
    if len(dots) < 3:
        return

    step = 0
    while running:
        for i, dot in enumerate(dots):
            dot.opacity = 1.0 if i == step % 3 else 0.4
        if dots_row.page:
            dots_row.update()
        step += 1
        await asyncio.sleep(0.4)
