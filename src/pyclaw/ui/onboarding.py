"""Onboarding wizard — first-time setup flow in the UI."""

from __future__ import annotations

from typing import Any

import flet as ft

from pyclaw.ui.i18n import t


class OnboardingWizard(ft.Column):
    """Multi-step setup wizard for first-time users."""

    def __init__(self, on_complete: Any = None) -> None:
        self._on_complete = on_complete
        self._step = 0
        self._config: dict[str, Any] = {}

        self._content = ft.Container(expand=True)
        self._progress = ft.ProgressBar(value=0, visible=True)
        self._step_label = ft.Text(
            t("onboarding.step", current=1, total=4), size=11, color=ft.Colors.ON_SURFACE_VARIANT
        )

        nav = ft.Row(
            [
                ft.TextButton(t("onboarding.back"), on_click=self._handle_back, visible=False),
                ft.Container(expand=True),
                self._step_label,
                ft.Container(expand=True),
                ft.ElevatedButton(t("onboarding.next"), on_click=self._handle_next),
            ]
        )

        super().__init__(
            controls=[
                ft.Text(t("onboarding.welcome"), size=28, weight=ft.FontWeight.BOLD),
                ft.Text(
                    t("onboarding.subtitle"),
                    size=14,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Divider(),
                self._progress,
                self._content,
                nav,
            ],
            expand=True,
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Step-specific controls
        self._provider_dropdown = ft.Dropdown(
            label=t("onboarding.provider_label"),
            value="openai",
            options=[
                ft.dropdown.Option("openai", "OpenAI"),
                ft.dropdown.Option("anthropic", "Anthropic"),
                ft.dropdown.Option("google", "Google Gemini"),
                ft.dropdown.Option("ollama", "Ollama (local)"),
            ],
            width=300,
        )
        self._api_key_field = ft.TextField(
            label=t("settings.api_key"),
            password=True,
            can_reveal_password=True,
            width=400,
        )
        self._model_field = ft.TextField(
            label=t("onboarding.default_model"),
            value="gpt-4o",
            width=300,
        )
        self._channel_checks = {
            "telegram": ft.Checkbox(label="Telegram", value=False),
            "discord": ft.Checkbox(label="Discord", value=False),
            "slack": ft.Checkbox(label="Slack", value=False),
            "whatsapp": ft.Checkbox(label="WhatsApp", value=False),
            "imessage": ft.Checkbox(label="iMessage", value=False),
        }

        self._update_step_ui()

    def _update_step_ui(self) -> None:
        total = 4
        self._progress.value = (self._step + 1) / total
        self._step_label.value = t("onboarding.step", current=self._step + 1, total=total)

        # Find back button
        nav_row = self.controls[-1]
        if isinstance(nav_row, ft.Row) and nav_row.controls:
            nav_row.controls[0].visible = self._step > 0
            # Change "Next" to "Finish" on last step
            finish_btn = nav_row.controls[-1]
            if isinstance(finish_btn, ft.ElevatedButton):
                finish_btn.text = (
                    t("onboarding.finish") if self._step == total - 1 else t("onboarding.next")
                )

        if self._step == 0:
            self._content.content = ft.Column(
                [
                    ft.Text(t("onboarding.choose_provider"), size=18, weight=ft.FontWeight.W_500),
                    ft.Container(height=8),
                    self._provider_dropdown,
                    ft.Container(height=16),
                    ft.Text(
                        t("onboarding.change_later"),
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=4,
            )

        elif self._step == 1:
            self._content.content = ft.Column(
                [
                    ft.Text(t("onboarding.enter_api_key"), size=18, weight=ft.FontWeight.W_500),
                    ft.Container(height=8),
                    self._api_key_field,
                    ft.Container(height=8),
                    ft.Text(
                        t("onboarding.key_stored_locally"),
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=4,
            )

        elif self._step == 2:
            self._content.content = ft.Column(
                [
                    ft.Text(t("onboarding.select_model"), size=18, weight=ft.FontWeight.W_500),
                    ft.Container(height=8),
                    self._model_field,
                ],
                spacing=4,
            )

        elif self._step == 3:
            self._content.content = ft.Column(
                [
                    ft.Text(t("onboarding.connect_channels"), size=18, weight=ft.FontWeight.W_500),
                    ft.Container(height=8),
                    *self._channel_checks.values(),
                    ft.Container(height=8),
                    ft.Text(
                        t("onboarding.channels_later"),
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=4,
            )

        try:
            if self._content.page:
                self._content.update()
                if isinstance(self.controls[-1], ft.Row):
                    self.controls[-1].update()
                self._progress.update()
                self._step_label.update()
        except RuntimeError:
            pass

    async def _handle_next(self, e: Any) -> None:
        # Save current step data
        if self._step == 0:
            self._config["provider"] = self._provider_dropdown.value
        elif self._step == 1:
            self._config["api_key"] = self._api_key_field.value
        elif self._step == 2:
            self._config["model"] = self._model_field.value
        elif self._step == 3:
            self._config["channels"] = [
                name for name, cb in self._channel_checks.items() if cb.value
            ]
            # Complete
            if self._on_complete:
                await self._on_complete(self._config)
            return

        self._step += 1
        self._update_step_ui()

    async def _handle_back(self, e: Any) -> None:
        if self._step > 0:
            self._step -= 1
            self._update_step_ui()
