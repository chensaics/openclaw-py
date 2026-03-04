"""Reusable UI components — shared building blocks for Flet pages.

Provides standardised components that maintain visual consistency
across all panels, backported from Flutter reference design patterns.
"""

from __future__ import annotations

import asyncio
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
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=ft.Colors.ERROR),
                ft.Text(message, size=14, color=ft.Colors.ERROR),
                *([ft.ElevatedButton("重试", on_click=lambda e: _fire_async(on_retry))] if on_retry else []),
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
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        border=ft.border.only(bottom=ft.BorderSide(0.5, theme.colors.border)),
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
        padding=ft.padding.all(32),
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
        padding=ft.padding.all(12),
        border_radius=ft.border_radius.all(theme.card_border_radius),
        bgcolor=theme.colors.surface_container,
        border=ft.border.all(0.5, theme.colors.border),
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
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
        border_radius=ft.border_radius.all(8),
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
