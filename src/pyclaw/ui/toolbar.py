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


class ChatToolbar:
    """Manages the toolbar Row and exposes the model dropdown for external updates."""

    def __init__(
        self,
        *,
        on_attach: Callable[[], Coroutine[Any, Any, None]] | None = None,
        on_voice: Callable[[], Coroutine[Any, Any, None]] | None = None,
        on_clear: Callable[[], Coroutine[Any, Any, None]] | None = None,
        on_model_change: Callable[[str], Coroutine[Any, Any, None]] | None = None,
        current_model: str = "",
        current_provider: str = "",
    ) -> None:
        import flet as ft

        from pyclaw.agents.model_catalog import ModelCatalog

        self._catalog = ModelCatalog()
        self._on_model_change = on_model_change

        provider = current_provider or DEFAULT_PROVIDER
        if not current_model:
            current_model = self._catalog.default_model_for_provider(provider)

        self.model_dropdown = ft.Dropdown(
            value=current_model,
            options=self._build_options(provider),
            width=220,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        )
        self.model_dropdown.on_select = self._fire_model_change

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

        self.control = ft.Row(
            controls=[self.model_dropdown, attach_btn, voice_btn, clear_btn],
            spacing=4,
            alignment=ft.MainAxisAlignment.START,
        )

    def _build_options(self, provider: str) -> list[Any]:
        import flet as ft

        models = self._catalog.list_models(provider)
        return [ft.dropdown.Option(m.model_id, m.display_name or m.model_id) for m in models]

    def update_provider(self, provider: str, model: str = "") -> None:
        """Rebuild model options for a new provider."""
        self.model_dropdown.options = self._build_options(provider)
        default = model or self._catalog.default_model_for_provider(provider)
        self.model_dropdown.value = default
        try:
            if self.model_dropdown.page:
                self.model_dropdown.update()
        except RuntimeError:
            pass

    async def _fire_model_change(self, e: Any) -> None:
        if self._on_model_change and e.control.value:
            await self._on_model_change(e.control.value)


def _fire(handler: Any) -> None:
    if handler:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler())
        except RuntimeError:
            pass


def build_toolbar(**kwargs: Any) -> Any:
    """Build a toolbar Row. Returns a ``ChatToolbar`` instance."""
    try:
        return ChatToolbar(**kwargs)
    except ImportError:
        return None
