"""Shimmer loading skeletons and animation helpers for Flet UI.

Backported from Flutter App reference design (flutter_app/lib/widgets/).
Uses Flet's animation system (ft.Animation / ft.AnimatedOpacity) to create
pulse/shimmer effects for loading placeholders.
"""

from __future__ import annotations

import asyncio

try:
    import flet as ft
except ImportError:
    ft = None  # type: ignore[assignment]

from pyclaw.ui.theme import get_theme


def _skeleton_rect(
    *,
    width: int | None = None,
    height: int = 14,
    border_radius: int = 6,
) -> ft.Container:
    """Single rounded rectangle placeholder block."""
    theme = get_theme()
    return ft.Container(
        width=width,
        height=height,
        border_radius=border_radius,
        bgcolor=theme.colors.surface_container_high,
    )


def _skeleton_circle(radius: int = 18) -> ft.Container:
    """Circular avatar placeholder."""
    theme = get_theme()
    return ft.Container(
        width=radius * 2,
        height=radius * 2,
        border_radius=radius,
        bgcolor=theme.colors.surface_container_high,
    )


def shimmer_chat_skeleton(item_count: int = 4) -> ft.Column:
    """Chat-style shimmer skeleton (alternating left/right message bubbles).

    Mimics the Flutter ShimmerLoading widget layout.
    """
    rows: list[ft.Control] = []
    for i in range(item_count):
        is_even = i % 2 == 0
        alignment = ft.MainAxisAlignment.START if is_even else ft.MainAxisAlignment.END
        cross = ft.CrossAxisAlignment.START if is_even else ft.CrossAxisAlignment.END

        bubble_height = 48 + (i % 3) * 16
        row_children: list[ft.Control] = [
            _skeleton_circle(18),
            ft.Container(width=12),
            ft.Column(
                [
                    _skeleton_rect(width=80, height=12),
                    ft.Container(height=8),
                    _skeleton_rect(height=bubble_height, border_radius=16),
                ],
                horizontal_alignment=cross,
                expand=True,
            ),
        ]
        if not is_even:
            row_children = row_children[::-1]

        rows.append(
            ft.Container(
                content=ft.Row(row_children, alignment=alignment),
                padding=ft.padding.only(bottom=16),
            )
        )

    return ft.Column(rows, spacing=0)


def shimmer_list_tile(count: int = 5) -> ft.Column:
    """List-tile style shimmer skeleton (icon + two text lines).

    Mimics the Flutter ShimmerListTile widget.
    """
    tiles: list[ft.Control] = []
    for _ in range(count):
        tiles.append(
            ft.Container(
                content=ft.Row(
                    [
                        _skeleton_circle(20),
                        ft.Container(width=12),
                        ft.Column(
                            [
                                _skeleton_rect(width=150, height=14, border_radius=4),
                                ft.Container(height=6),
                                _skeleton_rect(width=220, height=10, border_radius=4),
                            ],
                            spacing=0,
                        ),
                    ],
                ),
                padding=ft.padding.symmetric(vertical=6, horizontal=16),
            )
        )
    return ft.Column(tiles, spacing=0)


class ShimmerContainer(ft.Container if ft else object):
    """Container with a pulsing opacity animation (shimmer effect).

    Wraps any skeleton layout and toggles opacity between 0.3 and 1.0
    to simulate a shimmer/loading animation.

    Usage::

        shimmer = ShimmerContainer(content=shimmer_chat_skeleton())
        page.add(shimmer)
        shimmer.start()  # begin animation loop
    """

    def __init__(
        self,
        content: ft.Control | None = None,
        pulse_duration_ms: int = 1200,
        **kwargs: object,
    ):
        super().__init__(
            content=content,
            opacity=1.0,
            animate_opacity=ft.Animation(pulse_duration_ms, ft.AnimationCurve.EASE_IN_OUT),
            **kwargs,
        )
        self._running = False
        self._pulse_duration = pulse_duration_ms / 1000.0

    async def _pulse_loop(self) -> None:
        while self._running:
            self.opacity = 0.35
            if self.page:
                self.update()
            await asyncio.sleep(self._pulse_duration)
            if not self._running:
                break
            self.opacity = 1.0
            if self.page:
                self.update()
            await asyncio.sleep(self._pulse_duration)

    def start(self) -> None:
        """Start the shimmer animation loop."""
        if not self._running:
            self._running = True
            asyncio.ensure_future(self._pulse_loop())

    def stop(self) -> None:
        """Stop the shimmer animation and reset opacity."""
        self._running = False
        self.opacity = 1.0
        if self.page:
            self.update()


# ---------------------------------------------------------------------------
# Stagger animation helper
# ---------------------------------------------------------------------------


async def stagger_fade_in(
    controls: list[ft.Control],
    *,
    page: ft.Page | None = None,
    delay_ms: int = 50,
    duration_ms: int = 300,
) -> None:
    """Animate a list of controls with staggered fade + slide-in.

    Backported from Flutter StaggerList widget. Each control gets its
    opacity set to 0 and offset.y set to 20, then fades in sequentially.

    The controls must already be added to the page/container.
    """
    for ctrl in controls:
        if isinstance(ctrl, ft.Container):
            ctrl.opacity = 0
            ctrl.offset = ft.Offset(0, 0.05)
            ctrl.animate_opacity = ft.Animation(duration_ms, ft.AnimationCurve.EASE_OUT)
            ctrl.animate_offset = ft.Animation(duration_ms, ft.AnimationCurve.EASE_OUT)

    target = page
    if target:
        target.update()

    for ctrl in controls:
        if isinstance(ctrl, ft.Container):
            ctrl.opacity = 1
            ctrl.offset = ft.Offset(0, 0)
        if target:
            target.update()
        await asyncio.sleep(delay_ms / 1000.0)
