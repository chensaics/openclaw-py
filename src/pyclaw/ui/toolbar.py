"""Chat toolbar — action buttons above the input area.

Provides quick-access buttons for common actions: attach file,
voice input, model selector, clear session.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from pyclaw.config.defaults import DEFAULT_PROVIDER
from pyclaw.ui.i18n import t

logger = logging.getLogger(__name__)


def build_toolbar(
    *,
    on_attach: Callable[[], Coroutine[Any, Any, None]] | None = None,
    on_voice: Callable[[], Coroutine[Any, Any, None]] | None = None,
    on_clear: Callable[[], Coroutine[Any, Any, None]] | None = None,
    on_model_change: Callable[[str], Coroutine[Any, Any, None]] | None = None,
    current_model: str = "",
    current_provider: str = "",
    available_models: list[str] | None = None,
) -> Any:
    """Build a toolbar Row for the chat input area.

    Returns a ``ft.Row`` control, or ``None`` if Flet is unavailable.
    """
    try:
        import flet as ft
    except ImportError:
        return None

    if available_models:
        models = available_models
    else:
        from pyclaw.agents.model_catalog import ModelCatalog
        catalog = ModelCatalog()
        provider = current_provider or DEFAULT_PROVIDER
        provider_models = catalog.list_models(provider)
        models = [m.model_id for m in provider_models]
        if not current_model:
            current_model = catalog.default_model_for_provider(provider)

    if not current_model and models:
        current_model = models[0]

    model_dropdown = ft.Dropdown(
        value=current_model,
        options=[ft.dropdown.Option(m) for m in models],
        width=220,
        dense=True,
        content_padding=ft.padding.symmetric(horizontal=8, vertical=4),
    )
    model_dropdown.on_select = lambda e: _fire_model_change(e)

    async def _fire_model_change(e: Any) -> None:
        if on_model_change and e.control.value:
            await on_model_change(e.control.value)

    attach_btn = ft.IconButton(
        icon=ft.Icons.ATTACH_FILE,
        tooltip=t("toolbar.attach", default="Attach file"),
        on_click=lambda e: _fire(on_attach),
    )

    voice_btn = ft.IconButton(
        icon=ft.Icons.MIC_NONE,
        tooltip=t("toolbar.voice", default="Voice input"),
        on_click=lambda e: _fire(on_voice),
    )

    clear_btn = ft.IconButton(
        icon=ft.Icons.DELETE_OUTLINE,
        tooltip=t("toolbar.clear", default="Clear session"),
        on_click=lambda e: _fire(on_clear),
    )

    def _fire(handler: Any) -> None:
        if handler:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(handler())
            except RuntimeError:
                pass

    return ft.Row(
        controls=[model_dropdown, attach_btn, voice_btn, clear_btn],
        spacing=4,
        alignment=ft.MainAxisAlignment.START,
    )
