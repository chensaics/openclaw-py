"""Media preview — inline preview for images, audio, and video attachments."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import flet as ft

from pyclaw.ui.i18n import t


def build_media_preview(
    url: str | None = None,
    path: str | None = None,
    mime: str | None = None,
    max_width: int = 400,
    max_height: int = 300,
) -> ft.Control | None:
    """Build an inline media preview control.

    Returns None if the media type is not previewable.
    """
    if not mime:
        if path:
            mime, _ = mimetypes.guess_type(path)
        elif url:
            mime, _ = mimetypes.guess_type(url)

    if not mime:
        return None

    source = url or path or ""

    if mime.startswith("image/"):
        return _build_image_preview(source, max_width, max_height)
    if mime.startswith("audio/"):
        return _build_audio_preview(source)
    if mime.startswith("video/"):
        return _build_video_preview(source, max_width, max_height)

    return None


def _build_image_preview(source: str, max_width: int, max_height: int) -> ft.Control:
    """Build an image preview with click-to-expand."""
    return ft.Container(
        content=ft.Image(
            src=source,
            width=max_width,
            height=max_height,
            fit=ft.ImageFit.CONTAIN,
            border_radius=ft.border_radius.all(8),
        ),
        on_click=lambda e: _open_lightbox(e, source),
        tooltip=t("media.expand"),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        border_radius=ft.border_radius.all(8),
        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
    )


def _build_audio_preview(source: str) -> ft.Control:
    """Build an audio player control."""
    filename = Path(source).name if not source.startswith("http") else source.split("/")[-1]
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.AUDIOTRACK, size=24, color=ft.Colors.PRIMARY),
                ft.Column(
                    [
                        ft.Text(filename, size=12, weight=ft.FontWeight.BOLD),
                        ft.Text(t("media.audio_file"), size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=2,
                    tight=True,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.PLAY_ARROW,
                    tooltip="Play audio",
                    icon_size=20,
                ),
            ],
            spacing=8,
        ),
        padding=ft.padding.all(8),
        border_radius=ft.border_radius.all(8),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
        width=300,
    )


def _build_video_preview(source: str, max_width: int, max_height: int) -> ft.Control:
    """Build a video placeholder preview."""
    filename = Path(source).name if not source.startswith("http") else source.split("/")[-1]
    return ft.Container(
        content=ft.Stack(
            [
                ft.Container(
                    width=max_width,
                    height=max_height // 2,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    border_radius=ft.border_radius.all(8),
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE, size=48, color=ft.Colors.PRIMARY),
                            ft.Text(filename, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    alignment=ft.Alignment.CENTER,
                    width=max_width,
                    height=max_height // 2,
                ),
            ]
        ),
        border_radius=ft.border_radius.all(8),
        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


def _open_lightbox(e: Any, source: str) -> None:
    """Open a full-size image dialog."""
    try:
        page = e.control.page
    except RuntimeError:
        return
    if not page:
        return

    dialog: ft.AlertDialog = ft.AlertDialog(
        content=ft.Image(src=source, fit=ft.ImageFit.CONTAIN),
        actions=[ft.TextButton(t("media.close"), on_click=lambda _: page.close(dialog))],
    )
    page.open(dialog)
