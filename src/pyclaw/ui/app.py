"""Main Flet application — chat UI with session management, tool visualization, markdown.

Works across desktop (macOS/Windows/Linux), mobile (iOS/Android),
and web targets using a single codebase.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC
from pathlib import Path
from typing import Any

import flet as ft

from pyclaw.ui.i18n import I18n, set_i18n, t

# ─── Markdown rendering helper ───────────────────────────────────────────


def _render_markdown(text: str) -> ft.Control:
    """Render markdown text as a Flet Markdown control."""
    return ft.Markdown(
        value=text,
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        code_theme=ft.MarkdownCodeTheme.MONOKAI,
        auto_follow_links=True,
    )


# ─── Tool call visualization ─────────────────────────────────────────────


class ToolCallCard(ft.Container):
    """Visual card for a tool invocation."""

    def __init__(self, tool_name: str, arguments: dict[str, Any], result: str = "") -> None:
        # Load tool display config for emoji/title
        display = _get_tool_display(tool_name)
        emoji = display.get("emoji", "🔧")
        title = display.get("title", tool_name)

        header = ft.Row(
            [
                ft.Text(emoji, size=16),
                ft.Text(title, weight=ft.FontWeight.BOLD, size=13),
            ],
            spacing=4,
        )

        # Truncated arguments preview
        args_preview = json.dumps(arguments, indent=2)[:200]
        if len(args_preview) >= 200:
            args_preview += "..."

        args_text = ft.Text(
            args_preview,
            size=11,
            font_family="monospace",
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=4,
        )

        children: list[ft.Control] = [header, args_text]
        if result:
            result_preview = result[:150] + ("..." if len(result) > 150 else "")
            children.append(
                ft.Text(
                    result_preview,
                    size=11,
                    italic=True,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )
            )

        super().__init__(
            content=ft.Column(children, spacing=4, tight=True),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            padding=ft.padding.all(8),
            border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
        )


def _get_tool_display(tool_name: str) -> dict[str, str]:
    """Load tool display metadata from tool-display.json."""
    display_path = Path(__file__).parent.parent / "agents" / "tools" / "tool-display.json"
    try:
        if display_path.is_file():
            data = json.loads(display_path.read_text(encoding="utf-8"))
            return data.get(tool_name, {})
    except Exception:
        pass
    return {}


# ─── Chat Message ─────────────────────────────────────────────────────────


class ChatMessage(ft.Container):
    """A single chat message bubble with markdown rendering."""

    def __init__(
        self, role: str, content: str, tool_calls: list[dict[str, Any]] | None = None
    ) -> None:
        self.role = role
        self.content = content

        is_user = role == "user"
        alignment = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        bg_color = ft.Colors.BLUE_700 if is_user else ft.Colors.SURFACE_VARIANT
        text_color = ft.Colors.WHITE if is_user else None

        children: list[ft.Control] = [
            ft.Text(
                t("chat.role.user") if is_user else t("chat.role.assistant"),
                size=11,
                weight=ft.FontWeight.BOLD,
                opacity=0.7,
            ),
        ]

        # Tool call cards
        if tool_calls:
            for tc in tool_calls:
                children.append(
                    ToolCallCard(
                        tool_name=tc.get("name", ""),
                        arguments=tc.get("arguments", {}),
                        result=tc.get("result", ""),
                    )
                )

        # Detect inline media attachments (URLs ending in common media extensions)
        from pyclaw.ui.media_preview import build_media_preview

        media_extensions = (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".mp3",
            ".wav",
            ".ogg",
            ".mp4",
            ".webm",
        )
        for word in content.split():
            if word.startswith(("http://", "https://")) and any(
                word.lower().endswith(ext) for ext in media_extensions
            ):
                preview = build_media_preview(url=word)
                if preview:
                    children.append(preview)

        # Use markdown rendering for assistant messages, plain text for user
        if is_user:
            children.append(ft.Text(content, selectable=True, color=text_color))
        else:
            children.append(_render_markdown(content))

        bubble = ft.Container(
            content=ft.Column(children, spacing=4, tight=True),
            bgcolor=bg_color,
            padding=ft.padding.all(12),
            border_radius=ft.border_radius.all(12),
        )

        super().__init__(
            content=ft.Row([bubble], alignment=alignment),
        )


# ─── Session sidebar ─────────────────────────────────────────────────────


class SessionSidebar(ft.Column):
    """Sidebar for session management — list, switch, delete, rename."""

    def __init__(
        self,
        on_select: Any = None,
        on_new: Any = None,
        on_delete: Any = None,
    ) -> None:
        self._on_select = on_select
        self._on_new = on_new
        self._on_delete = on_delete
        self._sessions_list = ft.ListView(expand=True, spacing=2)
        self._selected_id: str | None = None

        header = ft.Row(
            [
                ft.Text(t("sessions.title"), size=14, weight=ft.FontWeight.BOLD, expand=True),
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    tooltip=t("sessions.new_tooltip"),
                    icon_size=18,
                    on_click=self._handle_new,
                ),
            ]
        )

        super().__init__(
            controls=[header, ft.Divider(height=1), self._sessions_list],
            width=220,
            spacing=4,
        )

    def update_sessions(self, sessions: list[dict[str, str]]) -> None:
        """Refresh the session list."""
        self._sessions_list.controls.clear()
        for s in sessions:
            sid = s.get("id", "")
            name = s.get("name", sid[:12])
            age = s.get("age", "")

            is_selected = sid == self._selected_id
            tile = ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(
                                    name,
                                    size=12,
                                    weight=ft.FontWeight.BOLD if is_selected else None,
                                ),
                                ft.Text(age, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=2,
                            expand=True,
                            tight=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=14,
                            tooltip=t("sessions.delete_tooltip"),
                            data=sid,
                            on_click=self._handle_delete,
                        ),
                    ],
                    spacing=4,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border_radius=ft.border_radius.all(6),
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_selected else None,
                data=sid,
                on_click=self._handle_select,
            )
            self._sessions_list.controls.append(tile)

        try:
            if self._sessions_list.page:
                self._sessions_list.update()
        except RuntimeError:
            pass

    def set_selected(self, session_id: str) -> None:
        self._selected_id = session_id

    async def _handle_select(self, e: Any) -> None:
        sid = e.control.data
        self._selected_id = sid
        if self._on_select:
            await self._on_select(sid)

    async def _handle_new(self, e: Any) -> None:
        if self._on_new:
            await self._on_new()

    async def _handle_delete(self, e: Any) -> None:
        sid = e.control.data
        if self._on_delete:
            await self._on_delete(sid)


# ─── Chat View ────────────────────────────────────────────────────────────


class ChatView(ft.Column):
    """The main chat interface with message list and input."""

    def __init__(self, on_send: Any = None) -> None:
        self._on_send = on_send
        self._messages_list = ft.ListView(
            expand=True,
            spacing=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            auto_scroll=True,
        )

        self._input = ft.TextField(
            hint_text=t("chat.placeholder"),
            expand=True,
            border_radius=24,
            on_submit=self._handle_submit,
            autofocus=True,
            shift_enter=True,
        )

        self._send_btn = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            on_click=self._handle_submit,
            tooltip=t("chat.send"),
        )

        self._loading = ft.ProgressBar(visible=False)
        self._progress_bar = ft.ProgressRing(visible=False, width=24, height=24)
        self._progress_text = ft.Text("", size=12, visible=False)
        self._progress_row = ft.Row(
            controls=[self._progress_bar, self._progress_text],
            spacing=8,
            visible=False,
        )

        input_row = ft.Row(controls=[self._input, self._send_btn], spacing=8)
        bottom_bar = ft.Container(
            content=ft.Column([self._loading, self._progress_row, input_row], spacing=4),
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
        )

        super().__init__(controls=[self._messages_list, bottom_bar], expand=True, spacing=0)

    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        self._messages_list.controls.append(ChatMessage(role, content, tool_calls))
        try:
            if self._messages_list.page:
                self._messages_list.update()
        except RuntimeError:
            pass

    def clear_messages(self) -> None:
        self._messages_list.controls.clear()
        try:
            if self._messages_list.page:
                self._messages_list.update()
        except RuntimeError:
            pass

    def set_loading(self, loading: bool) -> None:
        self._loading.visible = loading
        self._input.disabled = loading
        self._send_btn.disabled = loading
        try:
            if self._loading.page:
                self._loading.update()
                self._input.update()
                self._send_btn.update()
        except RuntimeError:
            pass

    def update_progress(self, event: Any) -> None:
        status_val = event.status.value if hasattr(event.status, "value") else str(event.status)

        if status_val in ("started", "progress"):
            self._progress_row.visible = True
            self._progress_bar.visible = True
            self._progress_text.visible = True
            self._progress_text.value = event.message or ""
            try:
                if self._progress_row.page:
                    self._progress_row.update()
                    self._progress_bar.update()
                    self._progress_text.update()
            except RuntimeError:
                pass
        elif status_val in ("completed", "failed"):

            async def _hide_after_delay() -> None:
                await asyncio.sleep(0.5)
                self._progress_row.visible = False
                self._progress_bar.visible = False
                self._progress_text.visible = False
                self._progress_text.value = ""
                try:
                    if self._progress_bar.page:
                        self._progress_row.update()
                        self._progress_bar.update()
                        self._progress_text.update()
                except RuntimeError:
                    pass

            page = self._progress_bar.page
            if page:
                page.run_task(_hide_after_delay())
            else:
                self._progress_row.visible = False
                self._progress_bar.visible = False
                self._progress_text.visible = False
                self._progress_text.value = ""

    async def _handle_submit(self, e: Any) -> None:
        text = self._input.value
        if not text or not text.strip():
            return
        self._input.value = ""
        self._input.update()
        if self._on_send:
            await self._on_send(text.strip())


# ─── Settings View ────────────────────────────────────────────────────────


class SettingsView(ft.Column):
    """Settings panel for configuring provider, model, API key, etc."""

    def __init__(self, on_save: Any = None) -> None:
        self._on_save = on_save

        self._provider = ft.Dropdown(
            label=t("settings.provider"),
            value="openai",
            options=[
                ft.dropdown.Option("openai", "OpenAI"),
                ft.dropdown.Option("anthropic", "Anthropic"),
                ft.dropdown.Option("google", "Google Gemini"),
                ft.dropdown.Option("ollama", "Ollama (local)"),
                ft.dropdown.Option("openrouter", "OpenRouter"),
                ft.dropdown.Option("groq", "Groq"),
                ft.dropdown.Option("deepseek", "DeepSeek"),
                ft.dropdown.Option("mistral", "Mistral"),
                ft.dropdown.Option("xai", "xAI"),
            ],
            width=250,
        )

        self._model = ft.TextField(label=t("settings.model_id"), value="gpt-4o", width=300)
        self._api_key = ft.TextField(
            label=t("settings.api_key"),
            password=True,
            can_reveal_password=True,
            width=400,
        )
        self._base_url = ft.TextField(
            label=t("settings.base_url"),
            hint_text="https://api.openai.com/v1",
            width=400,
        )

        # Theme toggle
        self._theme_toggle = ft.Switch(
            label=t("settings.dark_mode"),
            value=True,
            on_change=self._handle_theme_change,
        )

        save_btn = ft.ElevatedButton(
            t("settings.save"), icon=ft.Icons.SAVE, on_click=self._handle_save
        )

        super().__init__(
            controls=[
                ft.Text(t("settings.title"), size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text(t("settings.model_config"), size=16, weight=ft.FontWeight.W_500),
                self._provider,
                self._model,
                self._api_key,
                self._base_url,
                ft.Container(height=16),
                ft.Text(t("settings.appearance"), size=16, weight=ft.FontWeight.W_500),
                self._theme_toggle,
                ft.Container(height=16),
                save_btn,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

    def get_config(self) -> dict[str, str | None]:
        return {
            "provider": self._provider.value,
            "model": self._model.value,
            "api_key": self._api_key.value,
            "base_url": self._base_url.value or None,
        }

    async def _handle_save(self, e: Any) -> None:
        if self._on_save:
            await self._on_save(self.get_config())

    async def _handle_theme_change(self, e: Any) -> None:
        try:
            page = self._theme_toggle.page
            if page:
                page.theme_mode = (
                    ft.ThemeMode.DARK if self._theme_toggle.value else ft.ThemeMode.LIGHT
                )
                page.update()
        except RuntimeError:
            pass


# ─── Application Controller ──────────────────────────────────────────────


class PyClawApp:
    """Root application controller with session management."""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": None,
            "base_url": None,
        }
        self._current_session: str | None = None
        self._session_mgr: Any = None

    async def main(self, page: ft.Page) -> None:
        # Initialize i18n
        i18n = I18n("en")
        locales_dir = Path(__file__).parent / "locales"
        if locales_dir.is_dir():
            for locale_file in locales_dir.glob("*.json"):
                i18n.load_translations_file(locale_file)
        set_i18n(i18n)
        from pyclaw.ui.theme import get_theme

        page.title = t("app.title")
        page.theme_mode = ft.ThemeMode.DARK
        flet_theme = get_theme().to_flet_theme()
        if flet_theme:
            page.theme = flet_theme
        page.window.width = 1000
        page.window.height = 700

        self._page = page

        # Session sidebar
        self._session_sidebar = SessionSidebar(
            on_select=self._handle_session_select,
            on_new=self._handle_new_session,
            on_delete=self._handle_delete_session,
        )

        # Chat and settings views
        self._chat_view = ChatView(on_send=self._handle_send)
        self._settings_view = SettingsView(on_save=self._handle_save_settings)

        self._content_area = ft.Column(expand=True)
        self._content_area.controls = [self._chat_view]

        # Channel status panel
        from pyclaw.ui.channels_panel import ChannelStatusPanel

        self._channels_panel = ChannelStatusPanel(on_refresh=self._refresh_channels)

        from pyclaw.ui.voice import build_voice_panel

        self._voice_panel = build_voice_panel(
            api_key=self._config.get("api_key", ""),
        )

        from pyclaw.ui.agents_panel import build_agents_panel

        self._agents_panel = build_agents_panel()

        nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
                    selected_icon=ft.Icons.CHAT_BUBBLE,
                    label=t("nav.chat"),
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SMART_TOY_OUTLINED,
                    selected_icon=ft.Icons.SMART_TOY,
                    label=t("nav.agents", default="Agents"),
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.LINK,
                    selected_icon=ft.Icons.LINK,
                    label=t("nav.channels"),
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.MIC_NONE,
                    selected_icon=ft.Icons.MIC,
                    label=t("voice.title"),
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label=t("nav.settings"),
                ),
            ],
            on_change=self._handle_nav_change,
        )

        page.add(
            ft.Row(
                controls=[
                    nav_rail,
                    ft.VerticalDivider(width=1),
                    self._session_sidebar,
                    ft.VerticalDivider(width=1),
                    self._content_area,
                ],
                expand=True,
            )
        )

        from pyclaw.agents.progress import add_progress_listener

        def _on_progress(event: Any) -> None:
            self._chat_view.update_progress(event)

        self._progress_listener = _on_progress
        add_progress_listener(self._progress_listener)

        # Check onboarding
        await self._check_onboarding(page)

        # Load sessions
        await self._refresh_sessions()

    async def _handle_nav_change(self, e: Any) -> None:
        idx = e.control.selected_index
        if idx == 0:
            self._content_area.controls = [self._chat_view]
        elif idx == 1:
            if self._agents_panel:
                self._content_area.controls = [self._agents_panel]
        elif idx == 2:
            self._content_area.controls = [self._channels_panel]
            await self._refresh_channels()
        elif idx == 3:
            if self._voice_panel:
                self._content_area.controls = [self._voice_panel]
        else:
            self._content_area.controls = [self._settings_view]
        self._content_area.update()

    async def _handle_send(self, text: str) -> None:
        self._chat_view.add_message("user", text)
        self._chat_view.set_loading(True)

        self._ensure_session_manager()
        from pyclaw.agents.session import AgentMessage

        self._session_mgr.append_message(AgentMessage(role="user", content=text))

        try:
            reply = await self._get_agent_reply(text)
            self._chat_view.add_message("assistant", reply)
            self._session_mgr.append_message(AgentMessage(role="assistant", content=reply))
        except Exception as e:
            err_msg = t("chat.error", error=str(e))
            self._chat_view.add_message("assistant", err_msg)
            self._session_mgr.append_message(AgentMessage(role="assistant", content=err_msg))
        finally:
            self._chat_view.set_loading(False)

    async def _handle_save_settings(self, config: dict[str, Any]) -> None:
        self._config.update(config)
        if self._page:
            self._page.snack_bar = ft.SnackBar(content=ft.Text(t("settings.saved")), open=True)
            self._page.update()

    def _ensure_session_manager(self) -> None:
        """Ensure a persistent SessionManager exists for the current session."""
        from pyclaw.agents.session import SessionManager
        from pyclaw.config.paths import resolve_sessions_dir

        if self._session_mgr is not None and self._session_mgr.session_id == self._current_session:
            return

        if not self._current_session:
            import uuid

            self._current_session = uuid.uuid4().hex[:8]

        sessions_dir = resolve_sessions_dir("main")
        sessions_dir.mkdir(parents=True, exist_ok=True)
        session_path = sessions_dir / f"{self._current_session}.jsonl"

        if session_path.exists():
            self._session_mgr = SessionManager.open(session_path)
        else:
            self._session_mgr = SessionManager(path=session_path, session_id=self._current_session)
            self._session_mgr.write_header()

    async def _handle_session_select(self, session_id: str) -> None:
        self._current_session = session_id
        self._session_mgr = None
        self._session_sidebar.set_selected(session_id)
        self._chat_view.clear_messages()
        self._load_session_messages(session_id)
        await self._refresh_sessions()

    def _load_session_messages(self, session_id: str) -> None:
        """Load messages from a session JSONL file into the chat view."""
        from pyclaw.agents.session import SessionManager
        from pyclaw.config.paths import resolve_agents_dir

        agents_dir = resolve_agents_dir()
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            sessions_dir = agent_dir / "sessions"
            if not sessions_dir.is_dir():
                continue
            for jsonl in sessions_dir.glob("*.jsonl"):
                if session_id in jsonl.stem:
                    mgr = SessionManager.open(jsonl)
                    for msg in mgr.messages:
                        self._chat_view.add_message(msg.role, msg.content or "")
                    return

    async def _handle_new_session(self) -> None:
        import uuid

        new_id = uuid.uuid4().hex[:8]
        self._current_session = new_id
        self._session_mgr = None
        self._chat_view.clear_messages()
        await self._refresh_sessions()

    async def _handle_delete_session(self, session_id: str) -> None:
        self._delete_session_file(session_id)
        if self._current_session == session_id:
            self._current_session = None
            self._chat_view.clear_messages()
        await self._refresh_sessions()

    def _delete_session_file(self, session_id: str) -> None:
        """Delete a session JSONL file from disk."""
        from pyclaw.config.paths import resolve_agents_dir

        agents_dir = resolve_agents_dir()
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            sessions_dir = agent_dir / "sessions"
            if not sessions_dir.is_dir():
                continue
            for jsonl in sessions_dir.glob("*.jsonl"):
                if session_id in jsonl.stem:
                    jsonl.unlink(missing_ok=True)
                    return

    async def _refresh_sessions(self) -> None:
        """Reload session list from disk."""
        from datetime import datetime

        from pyclaw.config.paths import resolve_agents_dir

        agents_dir = resolve_agents_dir()
        sessions: list[dict[str, str]] = []

        main_sessions = agents_dir / "main" / "sessions"
        if main_sessions.is_dir():
            for f in sorted(
                main_sessions.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
            )[:20]:
                mtime = f.stat().st_mtime
                delta = datetime.now(UTC).timestamp() - mtime
                if delta < 60:
                    age = f"{int(delta)}s ago"
                elif delta < 3600:
                    age = f"{int(delta / 60)}m ago"
                elif delta < 86400:
                    age = f"{int(delta / 3600)}h ago"
                else:
                    age = f"{int(delta / 86400)}d ago"

                sessions.append({"id": f.stem, "name": f.stem[:16], "age": age})

        self._session_sidebar.update_sessions(sessions)

    async def _check_onboarding(self, page: ft.Page) -> None:
        """Show onboarding wizard if this is a first-time launch."""
        from pyclaw.config.paths import resolve_config_path

        config_path = resolve_config_path()
        if config_path.exists():
            return

        from pyclaw.ui.onboarding import OnboardingWizard

        async def on_complete(config: dict[str, Any]) -> None:
            self._config.update(config)
            from pyclaw.config.io import save_config
            from pyclaw.config.schema import (
                AgentDefaultsConfig,
                AgentsConfig,
                ChannelsConfig,
                ModelProviderConfig,
                ModelsConfig,
                PyClawConfig,
            )

            provider = config.get("provider", "openai")
            api_key = config.get("api_key")
            model_id = config.get("model", "gpt-4o")

            provider_cfg = ModelProviderConfig(baseUrl="", apiKey=api_key) if api_key else None
            providers = {provider: provider_cfg} if provider_cfg else None

            channels_selected = config.get("channels", [])
            channels_data: dict[str, Any] = {}
            for ch_name in channels_selected:
                channels_data[ch_name] = {"enabled": True}

            cfg = PyClawConfig(
                models=ModelsConfig(providers=providers) if providers else None,
                agents=AgentsConfig(
                    defaults=AgentDefaultsConfig(model=model_id, provider=provider)
                ),
                channels=ChannelsConfig(**channels_data) if channels_data else None,
            )
            save_config(cfg, config_path)
            dialog.open = False
            page.update()

        wizard = OnboardingWizard(on_complete=on_complete)
        dialog = ft.AlertDialog(
            content=ft.Container(content=wizard, width=500, height=500),
            modal=True,
            open=True,
        )
        page.overlay.append(dialog)
        page.update()

    async def _refresh_channels(self) -> None:
        """Load channel status from config."""
        from pyclaw.config.io import load_config
        from pyclaw.config.paths import resolve_config_path

        channels: list[dict[str, Any]] = []
        try:
            config = load_config(resolve_config_path())
            ch_cfg = config.channels
            if ch_cfg:
                channel_map = {
                    "telegram": ch_cfg.telegram,
                    "discord": ch_cfg.discord,
                    "slack": ch_cfg.slack,
                    "whatsapp": ch_cfg.whatsapp,
                    "signal": ch_cfg.signal,
                    "imessage": ch_cfg.imessage,
                }
                for name, cfg_val in channel_map.items():
                    if cfg_val is not None:
                        enabled = (
                            cfg_val.get("enabled", True) if isinstance(cfg_val, dict) else True
                        )
                        channels.append(
                            {
                                "name": name,
                                "enabled": enabled,
                                "status": "configured" if enabled else "disabled",
                            }
                        )
        except Exception:
            pass

        self._channels_panel.update_channels(channels)

    async def _get_agent_reply(self, message: str) -> str:
        """Run agent and return the reply text."""
        from pyclaw.agents.runner import run_agent
        from pyclaw.agents.types import ModelConfig

        self._ensure_session_manager()
        model = ModelConfig(
            provider=self._config.get("provider", "openai"),
            model_id=self._config.get("model", "gpt-4o"),
            api_key=self._config.get("api_key"),
            base_url=self._config.get("base_url"),
        )

        reply_parts: list[str] = []
        async for event in run_agent(prompt=message, session=self._session_mgr, model=model):
            if event.type == "message_update" and event.delta:
                reply_parts.append(event.delta)

        return "".join(reply_parts) or t("chat.no_response")


def run_app() -> None:
    """Launch the Flet desktop application."""
    app = PyClawApp()
    ft.app(target=app.main)


def run_web(port: int = 8550) -> None:
    """Launch the Flet web application."""
    app = PyClawApp()
    ft.app(target=app.main, view=ft.AppView.WEB_BROWSER, port=port)
