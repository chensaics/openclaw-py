"""Main Flet application — chat UI with session management, tool visualization, markdown.

Works across desktop (macOS/Windows/Linux), mobile (iOS/Android),
and web targets using a single codebase.  Connects to the pyclaw
gateway via WebSocket v3 protocol for all backend interactions.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import flet as ft

from pyclaw.config.defaults import DEFAULT_MODEL, DEFAULT_PROVIDER
from pyclaw.ui.i18n import I18n, set_i18n, t

logger = logging.getLogger(__name__)

# ─── Markdown rendering helper ───────────────────────────────────────────


def _render_markdown(text: str) -> ft.Control:
    """Render markdown text as a Flet Markdown control with themed code blocks."""
    from pyclaw.ui.theme import get_theme

    theme = get_theme()
    code_theme = ft.MarkdownCodeTheme.MONOKAI if theme.name == "dark" else ft.MarkdownCodeTheme.GITHUB
    return ft.Markdown(
        value=text,
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        code_theme=code_theme,
        code_style_sheet=ft.MarkdownStyleSheet(
            code_text_style=ft.TextStyle(
                font_family=theme.typography.mono_family,
                size=13,
            ),
        ),
        auto_follow_links=True,
    )


# ─── Tool call visualization ─────────────────────────────────────────────


class ToolCallCard(ft.Container):
    """Visual card for a tool invocation with expandable result."""

    def __init__(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: str = "",
        *,
        is_running: bool = False,
    ) -> None:
        from pyclaw.ui.theme import StatusColors, get_theme

        theme = get_theme()
        display = _get_tool_display(tool_name)
        emoji = display.get("emoji", "🔧")
        title = display.get("title", tool_name)

        status_icon = (
            ft.ProgressRing(width=14, height=14, stroke_width=2)
            if is_running
            else ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=StatusColors.SUCCESS)
            if result
            else ft.Icon(ft.Icons.CIRCLE_OUTLINED, size=14)
        )

        header = ft.Row(
            [
                ft.Text(emoji, size=16),
                ft.Text(title, weight=ft.FontWeight.BOLD, size=13, expand=True),
                status_icon,
            ],
            spacing=6,
        )

        args_preview = json.dumps(arguments, indent=2, ensure_ascii=False)[:200]
        if len(args_preview) >= 200:
            args_preview += "..."

        args_text = ft.Text(
            args_preview,
            size=11,
            font_family="monospace",
            color=theme.colors.muted,
            max_lines=4,
        )

        children: list[ft.Control] = [header, args_text]
        if result:
            result_preview = result[:300] + ("..." if len(result) > 300 else "")
            children.append(
                ft.Container(
                    content=ft.Text(
                        result_preview,
                        size=11,
                        font_family="monospace",
                        color=theme.colors.muted,
                    ),
                    bgcolor=theme.colors.surface_container_high,
                    padding=ft.padding.all(6),
                    border_radius=ft.border_radius.all(8),
                )
            )

        super().__init__(
            content=ft.Column(children, spacing=4, tight=True),
            bgcolor=theme.colors.surface_container,
            padding=ft.padding.all(10),
            border_radius=ft.border_radius.all(12),
            border=ft.border.all(0.5, theme.colors.border),
        )

    def set_result(self, result: str) -> None:
        """Update the card with a tool result (replaces spinner with check)."""
        from pyclaw.ui.theme import StatusColors, get_theme

        theme = get_theme()
        col = self.content
        if isinstance(col, ft.Column):
            header_row = col.controls[0]
            if isinstance(header_row, ft.Row) and header_row.controls:
                header_row.controls[-1] = ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=StatusColors.SUCCESS)
            if result:
                result_preview = result[:300] + ("..." if len(result) > 300 else "")
                col.controls.append(
                    ft.Container(
                        content=ft.Text(
                            result_preview,
                            size=11,
                            font_family="monospace",
                            color=theme.colors.muted,
                        ),
                        bgcolor=theme.colors.surface_container_high,
                        padding=ft.padding.all(6),
                        border_radius=ft.border_radius.all(8),
                    )
                )


def _get_tool_display(tool_name: str) -> dict[str, str]:
    """Load tool display metadata from tool-display.json."""
    display_path = Path(__file__).parent.parent / "agents" / "tools" / "tool-display.json"
    try:
        if display_path.is_file():
            data = json.loads(display_path.read_text(encoding="utf-8"))
            tools = data.get("tools", data)
            result = tools.get(tool_name, {})
            if not result:
                fallback = data.get("fallback", {})
                if fallback:
                    return cast(dict[str, str], fallback)
            return cast(dict[str, str], result)
    except Exception:
        pass
    return {}


# ─── Chat Message ─────────────────────────────────────────────────────────


class ChatMessage(ft.Container):
    """A single chat message bubble with markdown rendering and avatar."""

    def __init__(
        self,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        *,
        on_edit: Any = None,
        on_resend: Any = None,
        msg_id: str = "",
    ) -> None:
        self.role = role
        self._message_text = content
        self._message_content = content
        self.msg_id = msg_id
        self._content_control: ft.Control | None = None
        self._tool_cards: dict[str, ToolCallCard] = {}

        from pyclaw.ui.theme import RoleColors, get_theme

        is_user = role == "user"
        theme = get_theme()
        alignment = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        bg_color = ft.Colors.PRIMARY_CONTAINER if is_user else theme.colors.surface_container
        avatar_icon = ft.Icons.PERSON if is_user else ft.Icons.SMART_TOY
        avatar_bg = RoleColors.USER if is_user else RoleColors.ASSISTANT

        avatar = ft.CircleAvatar(
            content=ft.Icon(avatar_icon, size=18, color="#ffffff"),
            radius=18,
            bgcolor=avatar_bg,
        )

        role_label = ft.Text(
            t("chat.role.user") if is_user else t("chat.role.assistant"),
            size=11,
            weight=ft.FontWeight.BOLD,
            opacity=0.7,
        )

        children: list[ft.Control] = [role_label]

        if tool_calls:
            for tc in tool_calls:
                card = ToolCallCard(
                    tool_name=tc.get("name", ""),
                    arguments=tc.get("arguments", {}),
                    result=tc.get("result", ""),
                )
                self._tool_cards[tc.get("toolCallId", tc.get("name", ""))] = card
                children.append(card)

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
            if word.startswith(("http://", "https://")) and any(word.lower().endswith(ext) for ext in media_extensions):
                preview = build_media_preview(url=word)
                if preview:
                    children.append(preview)

        if is_user:
            self._content_control = ft.Text(content, selectable=True)
        else:
            self._content_control = _render_markdown(content) if content else ft.Text("")

        children.append(self._content_control)

        action_buttons: list[ft.Control] = []
        if is_user and on_edit:
            action_buttons.append(
                ft.IconButton(
                    icon=ft.Icons.EDIT,
                    icon_size=14,
                    tooltip=t("chat.edit", default="Edit"),
                    on_click=lambda e: _fire_async(on_edit, content),
                )
            )
        if not is_user and on_resend:
            action_buttons.append(
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_size=14,
                    tooltip=t("chat.retry"),
                    on_click=lambda e: _fire_async(on_resend),
                )
            )

        bubble_content_controls: list[ft.Control] = [ft.Column(children, spacing=4, tight=True)]
        if action_buttons:
            bubble_content_controls.append(ft.Row(action_buttons, spacing=0, alignment=ft.MainAxisAlignment.END))

        bubble_radius = (
            ft.border_radius.only(
                top_left=18,
                top_right=18,
                bottom_left=4,
                bottom_right=18,
            )
            if is_user
            else ft.border_radius.only(
                top_left=18,
                top_right=18,
                bottom_left=18,
                bottom_right=4,
            )
        )

        bubble = ft.Container(
            content=ft.Column(bubble_content_controls, spacing=2, tight=True),
            bgcolor=bg_color,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            border_radius=bubble_radius,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            width=None,
        )

        bubble_wrapper = ft.Container(
            content=bubble,
            expand=3,
        )
        spacer = ft.Container(expand=1)

        if is_user:
            msg_row_controls: list[ft.Control] = [spacer, bubble_wrapper, avatar]
        else:
            msg_row_controls = [avatar, bubble_wrapper, spacer]

        super().__init__(
            content=ft.Row(
                msg_row_controls,
                alignment=alignment,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=8,
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=2),
            animate_opacity=ft.Animation(350, ft.AnimationCurve.EASE_OUT),
        )

    def update_content(self, new_content: str) -> None:
        """Update the message content (used for streaming)."""
        self._message_content = new_content
        if self._content_control is not None:
            col = self.content_row_column
            if col and self._content_control in col.controls:
                idx = col.controls.index(self._content_control)
                if self.role == "user":
                    self._content_control = ft.Text(new_content, selectable=True)
                else:
                    self._content_control = _render_markdown(new_content) if new_content else ft.Text("")
                col.controls[idx] = self._content_control

    @property
    def content_row_column(self) -> ft.Column | None:
        """Access the inner Column holding message children."""
        try:
            row = super().content
            if isinstance(row, ft.Row):
                for ctrl in row.controls:
                    if isinstance(ctrl, ft.Container):
                        inner = ctrl.content
                        if isinstance(inner, ft.Column) and inner.controls:
                            first = inner.controls[0]
                            if isinstance(first, ft.Column):
                                return first
        except Exception:
            pass
        return None

    def add_tool_card(self, tool_call_id: str, tool_name: str) -> ToolCallCard:
        """Add a running tool call card and return it."""
        card = ToolCallCard(tool_name=tool_name, arguments={}, is_running=True)
        self._tool_cards[tool_call_id] = card
        col = self.content_row_column
        if col:
            col.controls.insert(-1, card)
        return card

    def finish_tool_card(self, tool_call_id: str, result: str | None, error: str | None) -> None:
        """Update a tool card with its result."""
        card = self._tool_cards.get(tool_call_id)
        if card:
            card.set_result(result or error or "")


def _fire_async(handler: Any, *args: Any) -> None:
    if handler:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(handler(*args))
        except RuntimeError:
            pass


# ─── Session sidebar ─────────────────────────────────────────────────────


class SessionSidebar(ft.Column):
    """Sidebar for session management — list, switch, delete, search, grouping."""

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
        self._all_sessions: list[dict[str, str]] = []

        self._search_field = ft.TextField(
            hint_text=t("sessions.search", default="Search sessions..."),
            dense=True,
            border_radius=20,
            prefix_icon=ft.Icons.SEARCH,
            height=36,
            text_size=12,
        )
        self._search_field.on_change = self._handle_search

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
            controls=[header, self._search_field, ft.Divider(height=1), self._sessions_list],
            width=240,
            spacing=4,
        )

    def update_sessions(self, sessions: list[dict[str, str]]) -> None:
        """Refresh the session list with grouping by date."""
        self._all_sessions = sessions
        self._render_filtered(sessions)

    def _render_filtered(self, sessions: list[dict[str, str]]) -> None:
        self._sessions_list.controls.clear()

        groups: dict[str, list[dict[str, str]]] = {}
        for s in sessions:
            group = s.get("group", "")
            if group not in groups:
                groups[group] = []
            groups[group].append(s)

        for group_name, items in groups.items():
            if group_name:
                self._sessions_list.controls.append(
                    ft.Container(
                        content=ft.Text(
                            group_name,
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        padding=ft.padding.only(left=8, top=8, bottom=2),
                    )
                )
            for s in items:
                self._sessions_list.controls.append(self._build_session_tile(s))

        self._safe_update(self._sessions_list)

    def _build_session_tile(self, s: dict[str, str]) -> ft.Control:
        sid = s.get("id", "")
        name = s.get("name", sid[:12])
        age = s.get("age", "")
        is_selected = sid == self._selected_id

        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(
                                name,
                                size=12,
                                weight=ft.FontWeight.BOLD if is_selected else None,
                                max_lines=1,
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
            border_radius=ft.border_radius.all(8),
            bgcolor=ft.Colors.PRIMARY_CONTAINER if is_selected else None,
            data=sid,
            on_click=self._handle_select,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    def set_selected(self, session_id: str) -> None:
        self._selected_id = session_id

    async def _handle_search(self, e: Any) -> None:
        query = (self._search_field.value or "").strip().lower()
        if not query:
            self._render_filtered(self._all_sessions)
            return
        filtered = [
            s for s in self._all_sessions if query in s.get("name", "").lower() or query in s.get("id", "").lower()
        ]
        self._render_filtered(filtered)

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

    def _safe_update(self, control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass


# ─── Chat View ────────────────────────────────────────────────────────────


class ChatView(ft.Column):
    """The main chat interface with streaming, abort, and tool call visualization."""

    def __init__(
        self,
        on_send: Any = None,
        on_abort: Any = None,
        on_edit: Any = None,
        on_resend: Any = None,
    ) -> None:
        self._on_send = on_send
        self._on_abort = on_abort
        self._on_edit = on_edit
        self._on_resend = on_resend
        self._is_streaming = False
        self._current_assistant_msg: ChatMessage | None = None

        self._search_bar = ft.TextField(
            hint_text=t("chat.search", default="Search messages..."),
            dense=True,
            border_radius=20,
            prefix_icon=ft.Icons.SEARCH,
            height=32,
            text_size=12,
            visible=False,
        )
        self._search_bar.on_change = self._handle_search

        self._messages_list = ft.ListView(
            expand=True,
            spacing=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            auto_scroll=True,
        )

        self._plan_progress = ft.Container(visible=False)

        self._input = ft.TextField(
            hint_text=t("chat.placeholder"),
            expand=True,
            border_radius=24,
            autofocus=True,
            shift_enter=True,
        )
        self._input.on_submit = self._handle_submit

        self._send_btn = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            on_click=self._handle_submit,
            tooltip=t("chat.send"),
            scale=ft.Scale(1.0),
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_IN_OUT),
        )

        self._abort_btn = ft.IconButton(
            icon=ft.Icons.STOP_CIRCLE,
            on_click=self._handle_abort,
            tooltip=t("chat.abort", default="Stop"),
            visible=False,
            icon_color=ft.Colors.ERROR,
        )

        self._search_toggle = ft.IconButton(
            icon=ft.Icons.SEARCH,
            icon_size=18,
            tooltip=t("chat.search", default="Search"),
            on_click=self._toggle_search,
        )

        self._loading = ft.ProgressBar(visible=False)
        self._progress_bar = ft.ProgressRing(visible=False, width=24, height=24)
        self._progress_text = ft.Text("", size=12, visible=False)
        self._progress_row = ft.Row(
            controls=[self._progress_bar, self._progress_text],
            spacing=8,
            visible=False,
        )

        self._scroll_to_bottom_btn = ft.FloatingActionButton(
            icon=ft.Icons.KEYBOARD_ARROW_DOWN,
            mini=True,
            visible=False,
            on_click=self._scroll_to_bottom,
            opacity=0.8,
        )

        input_row = ft.Row(
            controls=[self._input, self._abort_btn, self._send_btn],
            spacing=4,
        )
        bottom_bar = ft.Container(
            content=ft.Column([self._loading, self._progress_row, input_row], spacing=4),
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
        )

        chat_area = ft.Stack(
            controls=[
                self._messages_list,
                ft.Container(
                    content=self._scroll_to_bottom_btn,
                    alignment=ft.Alignment(0, 1),
                    padding=ft.padding.only(bottom=8),
                ),
            ],
            expand=True,
        )

        super().__init__(
            controls=[
                self._search_bar,
                self._plan_progress,
                chat_area,
                bottom_bar,
            ],
            expand=True,
            spacing=0,
        )

    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        msg_id: str = "",
    ) -> ChatMessage:
        msg = ChatMessage(
            role,
            content,
            tool_calls,
            on_edit=self._on_edit,
            on_resend=self._on_resend,
            msg_id=msg_id,
        )
        msg.opacity = 0
        msg.offset = ft.Offset(0, 0.05)
        msg.animate_opacity = ft.Animation(350, ft.AnimationCurve.EASE_OUT)
        msg.animate_offset = ft.Animation(350, ft.AnimationCurve.EASE_OUT)
        self._messages_list.controls.append(msg)
        self._safe_update(self._messages_list)
        msg.opacity = 1
        msg.offset = ft.Offset(0, 0)
        self._safe_update(msg)
        return msg

    def start_streaming(self) -> ChatMessage:
        """Create an empty assistant message bubble for streaming into."""
        from pyclaw.ui.components import pulse_streaming_dots, streaming_indicator

        msg = self.add_message("assistant", "")
        self._current_assistant_msg = msg
        self._is_streaming = True
        self._abort_btn.visible = True
        self._send_btn.visible = False

        self._typing_dots = streaming_indicator()
        col = msg.content_row_column
        if col:
            col.controls.append(self._typing_dots)
            self._safe_update(self._messages_list)

        async def _run_dots() -> None:
            await pulse_streaming_dots(self._typing_dots, running=self._is_streaming)

        try:
            loop = asyncio.get_running_loop()
            self._dots_task = loop.create_task(_run_dots())
        except RuntimeError:
            pass

        self._safe_update(self._abort_btn)
        self._safe_update(self._send_btn)
        return msg

    def append_delta(self, delta: str) -> None:
        """Append a text delta to the current streaming message."""
        if self._current_assistant_msg:
            col = self._current_assistant_msg.content_row_column
            if col and hasattr(self, "_typing_dots") and self._typing_dots in col.controls:
                col.controls.remove(self._typing_dots)
            new_content = (self._current_assistant_msg._message_content or "") + delta
            self._current_assistant_msg._message_content = new_content
            self._current_assistant_msg.update_content(new_content)
            self._safe_update(self._messages_list)

    def finish_streaming(self, usage: dict[str, Any] | None = None) -> None:
        """Finalize the current streaming message."""
        self._is_streaming = False
        if hasattr(self, "_dots_task") and self._dots_task:
            self._dots_task.cancel()
            self._dots_task = None
        if hasattr(self, "_typing_dots") and self._typing_dots:
            if self._current_assistant_msg:
                col = self._current_assistant_msg.content_row_column
                if col and self._typing_dots in col.controls:
                    col.controls.remove(self._typing_dots)
            self._typing_dots = None
        self._current_assistant_msg = None
        self._abort_btn.visible = False
        self._send_btn.visible = True
        self._safe_update(self._abort_btn)
        self._safe_update(self._send_btn)

    def add_tool_start(self, tool_name: str, tool_call_id: str) -> None:
        if self._current_assistant_msg:
            self._current_assistant_msg.add_tool_card(tool_call_id, tool_name)
            self._safe_update(self._messages_list)

    def add_tool_end(self, tool_name: str, result: str | None, error: str | None, tool_call_id: str = "") -> None:
        if self._current_assistant_msg:
            if tool_call_id and tool_call_id in self._current_assistant_msg._tool_cards:
                self._current_assistant_msg.finish_tool_card(tool_call_id, result, error)
            else:
                for tc_id, card in reversed(list(self._current_assistant_msg._tool_cards.items())):
                    col = card.content
                    if isinstance(col, ft.Column) and col.controls:
                        header = col.controls[0]
                        if isinstance(header, ft.Row) and header.controls:
                            last = header.controls[-1]
                            if isinstance(last, ft.ProgressRing):
                                self._current_assistant_msg.finish_tool_card(tc_id, result, error)
                                break
            self._safe_update(self._messages_list)

    def show_plan_progress(self, steps: list[dict[str, Any]], current_index: int) -> None:
        """Display plan step progress at the top of the chat."""
        total = len(steps)
        completed = sum(1 for s in steps if s.get("status") == "completed")

        step_indicators: list[ft.Control] = []
        for i, step in enumerate(steps):
            status = step.get("status", "pending")
            color = (
                ft.Colors.GREEN
                if status == "completed"
                else ft.Colors.BLUE
                if status == "running"
                else ft.Colors.ON_SURFACE_VARIANT
            )
            icon = (
                ft.Icons.CHECK_CIRCLE
                if status == "completed"
                else ft.Icons.PLAY_CIRCLE
                if status == "running"
                else ft.Icons.CIRCLE_OUTLINED
            )
            step_indicators.append(
                ft.Container(
                    content=ft.Icon(icon, size=16, color=color),
                    tooltip=step.get("description", f"Step {i + 1}"),
                )
            )
            if i < total - 1:
                step_indicators.append(ft.Container(width=16, height=2, bgcolor=color))

        self._plan_progress.content = ft.Container(
            content=ft.Column(
                [
                    ft.Row(step_indicators, spacing=2, alignment=ft.MainAxisAlignment.CENTER),
                    ft.Text(f"{completed}/{total} steps", size=11, text_align=ft.TextAlign.CENTER),
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=ft.border_radius.all(8),
        )
        self._plan_progress.visible = True
        self._safe_update(self._plan_progress)

    def hide_plan_progress(self) -> None:
        self._plan_progress.visible = False
        self._safe_update(self._plan_progress)

    def clear_messages(self) -> None:
        self._messages_list.controls.clear()
        self._current_assistant_msg = None
        self.hide_plan_progress()
        self._safe_update(self._messages_list)

    def set_loading(self, loading: bool) -> None:
        self._loading.visible = loading
        self._input.disabled = loading
        self._send_btn.disabled = loading

        if loading and not hasattr(self, "_shimmer") or not self._shimmer:
            from pyclaw.ui.shimmer import ShimmerContainer, shimmer_chat_skeleton

            self._shimmer = ShimmerContainer(content=shimmer_chat_skeleton(3))
            self._messages_list.controls.append(self._shimmer)
            self._shimmer.start()
        elif not loading and hasattr(self, "_shimmer") and self._shimmer:
            self._shimmer.stop()
            if self._shimmer in self._messages_list.controls:
                self._messages_list.controls.remove(self._shimmer)
            self._shimmer = None

        for ctrl in (self._loading, self._input, self._send_btn, self._messages_list):
            self._safe_update(ctrl)

    def update_progress(self, event: Any) -> None:
        status_val = event.status.value if hasattr(event.status, "value") else str(event.status)

        if status_val in ("started", "progress"):
            self._progress_row.visible = True
            self._progress_bar.visible = True
            self._progress_text.visible = True
            self._progress_text.value = event.message or ""
            for ctrl in (self._progress_row, self._progress_bar, self._progress_text):
                self._safe_update(ctrl)
        elif status_val in ("completed", "failed"):

            async def _hide_after_delay() -> None:
                await asyncio.sleep(0.5)
                self._progress_row.visible = False
                self._progress_bar.visible = False
                self._progress_text.visible = False
                self._progress_text.value = ""
                for ctrl in (self._progress_row, self._progress_bar, self._progress_text):
                    self._safe_update(ctrl)

            page = self._progress_bar.page
            if page:
                page.run_task(_hide_after_delay)  # type: ignore[attr-defined]
            else:
                self._progress_row.visible = False
                self._progress_bar.visible = False
                self._progress_text.visible = False
                self._progress_text.value = ""

    async def _handle_submit(self, e: Any) -> None:
        text = self._input.value
        if not text or not text.strip():
            return
        self._send_btn.scale = ft.Scale(0.85)
        self._safe_update(self._send_btn)
        await asyncio.sleep(0.1)
        self._send_btn.scale = ft.Scale(1.0)
        self._safe_update(self._send_btn)
        self._input.value = ""
        self._safe_update(self._input)
        if self._on_send:
            await self._on_send(text.strip())

    async def _handle_abort(self, e: Any) -> None:
        if self._on_abort:
            await self._on_abort()

    async def _scroll_to_bottom(self, e: Any = None) -> None:
        self._messages_list.auto_scroll = True
        self._scroll_to_bottom_btn.visible = False
        self._safe_update(self._messages_list)
        self._safe_update(self._scroll_to_bottom_btn)

    def show_scroll_to_bottom(self) -> None:
        """Show the scroll-to-bottom FAB when user scrolls up."""
        self._scroll_to_bottom_btn.visible = True
        self._safe_update(self._scroll_to_bottom_btn)

    async def _toggle_search(self, e: Any) -> None:
        self._search_bar.visible = not self._search_bar.visible
        self._safe_update(self._search_bar)

    async def _handle_search(self, e: Any) -> None:
        query = (self._search_bar.value or "").strip().lower()
        for ctrl in self._messages_list.controls:
            if isinstance(ctrl, ChatMessage):
                msg_content = ctrl._message_content or ""
                ctrl.visible = not query or query in msg_content.lower()
        self._safe_update(self._messages_list)

    def _safe_update(self, control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass


# ─── Settings View ────────────────────────────────────────────────────────


class SettingsView(ft.Column):
    """Enhanced settings panel with dynamic models, locale, and theme customization."""

    def __init__(
        self,
        on_save: Any = None,
        gateway_client: Any = None,
        current_config: dict[str, Any] | None = None,
    ) -> None:
        self._on_save = on_save
        self._gw = gateway_client

        from pyclaw.agents.model_catalog import ModelCatalog

        self._catalog = ModelCatalog()

        cfg = current_config or {}
        _active_provider = cfg.get("provider") or DEFAULT_PROVIDER

        provider_options = [ft.dropdown.Option(p["id"], p["name"]) for p in self._catalog.list_providers()]
        self._provider = ft.Dropdown(
            label=t("settings.provider"),
            value=_active_provider,
            options=provider_options,
            width=250,
        )
        self._provider.on_select = self._handle_provider_change

        _initial_model = cfg.get("model") or self._catalog.default_model_for_provider(_active_provider)
        self._model = ft.Dropdown(
            label=t("settings.model_id"),
            value=_initial_model,
            options=self._build_model_options(_active_provider),
            width=300,
        )
        _initial_env_key = self._catalog.provider_env_key(_active_provider)
        self._api_key = ft.TextField(
            label=t("settings.api_key"),
            password=True,
            can_reveal_password=True,
            width=400,
            value=cfg.get("api_key") or "",
            hint_text=_initial_env_key or "",
        )
        _initial_base_url = cfg.get("base_url") or self._catalog.provider_base_url(_active_provider)
        self._base_url = ft.TextField(
            label=t("settings.base_url"),
            value=_initial_base_url,
            hint_text=self._catalog.provider_base_url(_active_provider) or "https://api.openai.com/v1",
            width=400,
        )

        self._theme_toggle = ft.Switch(
            label=t("settings.dark_mode"),
            value=True,
        )
        self._theme_toggle.on_change = self._handle_theme_change

        self._locale_dropdown = ft.Dropdown(
            label=t("settings.language"),
            value="en",
            options=[
                ft.dropdown.Option("en", "English"),
                ft.dropdown.Option("zh-CN", "简体中文"),
                ft.dropdown.Option("ja", "日本語"),
                ft.dropdown.Option("de", "Deutsch"),
            ],
            width=200,
        )
        self._locale_dropdown.on_select = self._handle_locale_change

        self._seed_color_field = ft.TextField(
            label=t("settings.seed_color", default="Theme Color"),
            value="#6366f1",
            width=150,
        )
        self._seed_color_field.on_submit = self._handle_seed_color_change

        from pyclaw.ui.theme import PRESET_SEED_COLORS

        self._color_swatches = ft.Row(
            controls=[
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=20,
                    bgcolor=color,
                    border=ft.border.all(
                        3 if color == "#6366f1" else 1.5,
                        ft.Colors.ON_SURFACE if color == "#6366f1" else ft.Colors.OUTLINE,
                    ),
                    data=color,
                    on_click=self._handle_swatch_click,
                    tooltip=name.capitalize(),
                    animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
                    shadow=ft.BoxShadow(
                        blur_radius=8,
                        spread_radius=2,
                        color=ft.Colors.with_opacity(0.3, color),
                    )
                    if color == "#6366f1"
                    else None,
                )
                for name, color in PRESET_SEED_COLORS.items()
            ],
            spacing=8,
            wrap=True,
        )

        self._gateway_url = ft.TextField(
            label=t("settings.gateway_url", default="Gateway URL"),
            value=cfg.get("gateway_url") or "ws://127.0.0.1:18789/",
            width=400,
        )

        save_btn = ft.Button(
            t("settings.save"),
            icon=ft.Icons.SAVE,
            on_click=self._handle_save,
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
                ft.Text(t("settings.gateway", default="Gateway"), size=16, weight=ft.FontWeight.W_500),
                self._gateway_url,
                ft.Container(height=16),
                ft.Text(t("settings.appearance"), size=16, weight=ft.FontWeight.W_500),
                ft.Row([self._theme_toggle, self._locale_dropdown, self._seed_color_field], spacing=16),
                self._color_swatches,
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
            "gateway_url": self._gateway_url.value or None,
        }

    def _build_model_options(self, provider: str) -> list[Any]:
        """Build dropdown options for models belonging to a provider."""
        models = self._catalog.list_models(provider)
        return [ft.dropdown.Option(m.model_id, m.display_name or m.model_id) for m in models]

    async def load_models_from_gateway(self) -> None:
        """Fetch model list from gateway and populate the dropdown.

        Falls back to the local catalog if gateway is unavailable.
        """
        provider = self._provider.value or DEFAULT_PROVIDER

        new_options: list[Any] = []
        default_model = ""

        if self._gw and getattr(self._gw, "connected", False):
            try:
                result = await self._gw.call("models.list", {"provider": provider})
                models = result.get("models", [])
                if models:
                    new_options = [
                        ft.dropdown.Option(
                            m.get("model_id") or m.get("key", ""),
                            m.get("display_name") or m.get("model_id", ""),
                        )
                        if isinstance(m, dict)
                        else ft.dropdown.Option(str(m))
                        for m in models
                    ]
                    catalog_default = self._catalog.default_model_for_provider(provider)
                    model_ids = [
                        (m.get("model_id") or m.get("key", "")) if isinstance(m, dict) else str(m) for m in models
                    ]
                    default_model = (
                        catalog_default if catalog_default in model_ids else (model_ids[0] if model_ids else "")
                    )
            except Exception:
                pass

        if not new_options:
            new_options = self._build_model_options(provider)
            default_model = self._catalog.default_model_for_provider(provider)

        self._model.value = None
        self._model.options = new_options
        self._model.value = default_model
        self._safe_update(self._model)

    async def _handle_provider_change(self, e: Any) -> None:
        provider = self._provider.value or DEFAULT_PROVIDER

        await self.load_models_from_gateway()

        base_url = self._catalog.provider_base_url(provider)
        self._base_url.value = base_url
        self._safe_update(self._base_url)

        env_key = self._catalog.provider_env_key(provider)
        if env_key:
            self._api_key.hint_text = env_key
        else:
            self._api_key.hint_text = ""
        self._safe_update(self._api_key)

    async def _handle_save(self, e: Any) -> None:
        cfg = self.get_config()
        provider = cfg.get("provider") or DEFAULT_PROVIDER
        model = cfg.get("model") or ""
        if model and not self._catalog.validate_model_for_provider(provider, model):
            fallback = self._catalog.default_model_for_provider(provider)
            cfg["model"] = fallback
            self._model.value = fallback
            self._safe_update(self._model)
        if self._on_save:
            await self._on_save(cfg)

    async def _handle_theme_change(self, e: Any) -> None:
        try:
            page = self._theme_toggle.page
            if page:
                page.theme_mode = ft.ThemeMode.DARK if self._theme_toggle.value else ft.ThemeMode.LIGHT
                page.update()
        except RuntimeError:
            pass

    async def _handle_locale_change(self, e: Any) -> None:
        from pyclaw.ui.i18n import get_i18n

        i18n = get_i18n()
        i18n.locale = self._locale_dropdown.value or "en"

    async def _handle_swatch_click(self, e: Any) -> None:
        color = e.control.data
        if not color:
            return
        self._seed_color_field.value = color
        self._safe_update(self._seed_color_field)

        for swatch in self._color_swatches.controls:
            if isinstance(swatch, ft.Container):
                is_selected = swatch.data == color
                swatch.border = ft.border.all(
                    3 if is_selected else 1.5,
                    ft.Colors.ON_SURFACE if is_selected else ft.Colors.OUTLINE,
                )
                swatch.shadow = (
                    ft.BoxShadow(
                        blur_radius=8,
                        spread_radius=2,
                        color=ft.Colors.with_opacity(0.3, swatch.data),
                    )
                    if is_selected
                    else None
                )
        self._safe_update(self._color_swatches)

        await self._handle_seed_color_change(e)

    async def _handle_seed_color_change(self, e: Any) -> None:
        color = self._seed_color_field.value or "#6366f1"
        try:
            from pyclaw.ui.theme import get_theme, set_seed_color

            set_seed_color(color)
            page = self._seed_color_field.page
            if page:
                page.theme = get_theme().to_flet_theme()
                page.update()
        except Exception:
            pass

    def _safe_update(self, control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass


# ─── Application Controller ──────────────────────────────────────────────


class PyClawApp:
    """Root application controller with Gateway WebSocket integration."""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {
            "provider": DEFAULT_PROVIDER,
            "model": DEFAULT_MODEL,
            "api_key": None,
            "base_url": None,
            "gateway_url": "ws://127.0.0.1:18789/",
        }
        self._current_session: str | None = None
        self._session_mgr: Any = None
        self._gw: Any = None
        self._gw_connected = False

    async def main(self, page: ft.Page) -> None:
        i18n = I18n("en")
        locales_dir = Path(__file__).parent / "locales"
        if locales_dir.is_dir():
            for locale_file in locales_dir.glob("*.json"):
                i18n.load_translations_file(locale_file)
        set_i18n(i18n)
        from pyclaw.ui.theme import get_theme

        page.title = t("app.title")
        page.theme_mode = ft.ThemeMode.DARK

        page.fonts = {
            "Noto Sans SC": "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap",
        }

        flet_theme = get_theme().to_flet_theme()
        if flet_theme:
            page.theme = flet_theme
        page.window = ft.Window(width=1100, height=750)

        self._page = page

        await self._connect_gateway()

        self._session_sidebar = SessionSidebar(
            on_select=self._handle_session_select,
            on_new=self._handle_new_session,
            on_delete=self._handle_delete_session,
        )

        self._chat_view = ChatView(
            on_send=self._handle_send,
            on_abort=self._handle_abort,
            on_edit=self._handle_edit_message,
            on_resend=self._handle_resend,
        )
        self._settings_view = SettingsView(
            on_save=self._handle_save_settings,
            gateway_client=self._gw,
            current_config=self._config,
        )

        self._content_area = ft.Column(
            expand=True,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )
        self._content_area.controls = [self._chat_view]

        from pyclaw.ui.channels_panel import ChannelStatusPanel

        self._channels_panel = ChannelStatusPanel(on_refresh=self._refresh_channels)

        from pyclaw.ui.voice import build_voice_panel

        self._voice_panel = build_voice_panel(
            api_key=self._config.get("api_key", ""),
        )

        from pyclaw.ui.agents_panel import build_agents_panel

        self._agents_panel = build_agents_panel()

        self._plan_panel = self._build_plan_panel()
        self._cron_panel = self._build_cron_panel()
        self._system_panel = self._build_system_panel()

        nav_items = [
            (ft.Icons.CHAT_BUBBLE_OUTLINE, ft.Icons.CHAT_BUBBLE, t("nav.chat")),
            (ft.Icons.SMART_TOY_OUTLINED, ft.Icons.SMART_TOY, t("nav.agents", default="Agents")),
            (ft.Icons.LINK, ft.Icons.LINK, t("nav.channels")),
            (ft.Icons.CHECKLIST, ft.Icons.CHECKLIST, t("nav.plans", default="Plans")),
            (ft.Icons.SCHEDULE, ft.Icons.SCHEDULE, t("nav.cron", default="Cron")),
            (ft.Icons.MIC_NONE, ft.Icons.MIC, t("voice.title")),
            (ft.Icons.MONITOR_HEART_OUTLINED, ft.Icons.MONITOR_HEART, t("nav.system", default="System")),
            (ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, t("nav.settings")),
        ]

        nav_destinations = [
            ft.NavigationRailDestination(icon=ic, selected_icon=sel, label=lbl) for ic, sel, lbl in nav_items
        ]

        self._nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            destinations=nav_destinations,
            on_change=self._handle_nav_change,
            min_width=72,
        )

        # Bottom navigation bar for mobile (<600px)
        self._bottom_nav = ft.NavigationBar(
            selected_index=0,
            destinations=[
                ft.NavigationBarDestination(icon=ic, selected_icon=sel, label=lbl) for ic, sel, lbl in nav_items
            ],
            on_change=self._handle_nav_change,
            visible=False,
        )

        from pyclaw.ui.toolbar import build_toolbar

        self._toolbar_obj = build_toolbar(
            on_attach=self._handle_attach,
            on_voice=self._handle_voice_toggle,
            on_clear=self._handle_clear_session,
            on_model_change=self._handle_model_change,
            current_model=self._config.get("model", DEFAULT_MODEL),
            current_provider=self._config.get("provider", DEFAULT_PROVIDER),
        )
        self._toolbar = self._toolbar_obj.control if self._toolbar_obj else None

        from pyclaw.ui.menubar import build_menubar

        self._menubar = build_menubar(
            on_new_session=self._handle_new_session,
            on_export=self._handle_export_chat,
            on_toggle_theme=self._toggle_theme,
            on_quit=lambda: page.window.close() if page.window else None,  # type: ignore[no-untyped-call]
        )

        gw_indicator = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        width=8,
                        height=8,
                        border_radius=4,
                        bgcolor=ft.Colors.GREEN if self._gw_connected else ft.Colors.RED,
                    ),
                    ft.Text(
                        "Gateway" if self._gw_connected else "Offline",
                        size=10,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.padding.all(8),
        )
        self._gw_indicator = gw_indicator

        # Top bar: menubar (desktop only) + toolbar + gateway indicator
        top_bar_controls: list[ft.Control] = []
        if self._menubar:
            top_bar_controls.append(self._menubar)
        if self._toolbar:
            top_bar_controls.append(self._toolbar)
        top_bar_controls.append(gw_indicator)

        self._top_bar = (
            ft.Row(
                top_bar_controls,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            if top_bar_controls
            else None
        )

        main_content = ft.Column(
            controls=[c for c in [self._top_bar, self._content_area] if c],
            expand=True,
            spacing=0,
        )

        self._sidebar_divider1 = ft.VerticalDivider(width=1)
        self._sidebar_divider2 = ft.VerticalDivider(width=1)

        from pyclaw.ui.responsive_shell import ResponsiveShell

        self._shell = ResponsiveShell(
            nav_rail=self._nav_rail,
            bottom_nav=self._bottom_nav,
            session_sidebar=self._session_sidebar,
            sidebar_divider1=self._sidebar_divider1,
            sidebar_divider2=self._sidebar_divider2,
            top_bar=self._top_bar,
            menubar=self._menubar,
            main_content=main_content,
        )

        self._root_column = self._shell.build()
        page.add(self._root_column)

        page.on_resize = self._handle_resize
        page.on_keyboard_event = self._handle_keyboard
        self._shell.apply(page.width or 1100)

        from pyclaw.agents.progress import add_progress_listener

        def _on_progress(event: Any) -> None:
            self._chat_view.update_progress(event)

        self._progress_listener = _on_progress
        add_progress_listener(self._progress_listener)

        await self._check_permissions(page)
        await self._check_onboarding(page)
        await self._refresh_sessions()

    # ─── Gateway connection ──────────────────────────────────────────

    async def _connect_gateway(self) -> None:
        """Try connecting to the gateway; fall back to in-process mode."""
        from pyclaw.ui.gateway_client import GatewayClient

        url = self._config.get("gateway_url", "ws://127.0.0.1:18789/")
        self._gw = GatewayClient(url=url, auth_token=self._config.get("auth_token"))
        try:
            await asyncio.wait_for(self._gw.connect(), timeout=5.0)
            self._gw_connected = self._gw.connected
        except Exception:
            logger.info("Gateway not available, running in local mode")
            self._gw_connected = False

    # ─── Navigation ──────────────────────────────────────────────────

    _NAV_MAP = {
        0: "_chat_view",
        1: "_agents_panel",
        2: "_channels_panel",
        3: "_plan_panel",
        4: "_cron_panel",
        5: "_voice_panel",
        6: "_system_panel",
        7: "_settings_view",
    }

    async def _handle_nav_change(self, e: Any) -> None:
        idx = e.control.selected_index
        attr = self._NAV_MAP.get(idx, "_chat_view")
        panel = getattr(self, attr, self._chat_view)
        if panel:
            self._content_area.opacity = 0
            self._safe_update(self._content_area)
            await asyncio.sleep(0.05)
            self._content_area.controls = [panel]
            self._content_area.opacity = 1
            self._safe_update(self._content_area)

        if idx == 2:
            await self._refresh_channels()
        elif idx == 3:
            await self._refresh_plans()
        elif idx == 4:
            await self._refresh_cron()
        elif idx == 6:
            await self._refresh_system()

    async def _handle_keyboard(self, e: Any) -> None:
        """Handle global keyboard shortcuts: Cmd/Ctrl+K search, +N new, +E export."""
        if not e.ctrl and not e.meta:
            return
        key = e.key.lower() if hasattr(e, "key") else ""
        if key == "k":
            self._chat_view._search_bar.visible = not self._chat_view._search_bar.visible
            self._safe_update(self._chat_view._search_bar)
            if self._chat_view._search_bar.visible:
                self._chat_view._search_bar.focus()
        elif key == "n":
            await self._handle_new_session()
        elif key == "e":
            await self._handle_export_chat()

    async def _handle_resize(self, e: Any) -> None:
        """Adapt layout for responsive design across Web/Desktop/Mobile."""
        if not self._page:
            return
        self._shell.apply(self._page.width or 1100)
        self._page.update()

    # ─── Chat handlers ───────────────────────────────────────────────

    async def _handle_send(self, text: str) -> None:
        self._chat_view.add_message("user", text)

        if self._gw_connected and self._gw:
            await self._send_via_gateway(text)
        else:
            await self._send_via_local(text)

    async def _send_via_gateway(self, text: str) -> None:
        """Send message through gateway with streaming events."""
        from pyclaw.ui.gateway_client import chat_send

        self._chat_view.start_streaming()
        try:
            await chat_send(
                self._gw,
                text,
                on_delta=lambda delta: self._chat_view.append_delta(delta),
                on_tool_start=lambda name, tid: self._chat_view.add_tool_start(name, tid),
                on_tool_end=lambda name, res, err: self._chat_view.add_tool_end(name, res, err),
                on_error=lambda err: self._chat_view.add_message("assistant", f"Error: {err}"),
                provider=self._config.get("provider"),
                model=self._config.get("model"),
                api_key=self._config.get("api_key"),
                session_id=self._current_session,
            )
        except Exception as exc:
            self._chat_view.add_message("assistant", t("chat.error", error=str(exc)))
        finally:
            self._chat_view.finish_streaming()

    async def _send_via_local(self, text: str) -> None:
        """Fall back to in-process agent execution."""
        self._chat_view.set_loading(True)
        self._ensure_session_manager()
        from pyclaw.agents.session import AgentMessage

        self._session_mgr.append_message(AgentMessage(role="user", content=text))

        try:
            reply = await self._get_agent_reply(text)
            self._chat_view.add_message("assistant", reply)
            self._session_mgr.append_message(AgentMessage(role="assistant", content=reply))
        except Exception as exc:
            err_msg = t("chat.error", error=str(exc))
            self._chat_view.add_message("assistant", err_msg)
            self._session_mgr.append_message(AgentMessage(role="assistant", content=err_msg))
        finally:
            self._chat_view.set_loading(False)

    async def _handle_abort(self) -> None:
        if self._gw_connected and self._gw:
            try:
                await self._gw.call("chat.abort", {"sessionId": self._current_session or ""})
            except Exception:
                pass
        self._chat_view.finish_streaming()

    async def _handle_edit_message(self, original_content: str) -> None:
        if self._gw_connected and self._gw:
            self._chat_view.start_streaming()
            try:
                # chat.edit re-runs from the edited message
                await self._gw.call(
                    "chat.edit",
                    {
                        "message": original_content,
                        "sessionId": self._current_session or "",
                        "provider": self._config.get("provider"),
                        "model": self._config.get("model"),
                    },
                )
            except Exception:
                pass
            finally:
                self._chat_view.finish_streaming()

    async def _handle_resend(self) -> None:
        if self._gw_connected and self._gw:
            self._chat_view.start_streaming()
            try:
                from pyclaw.ui.gateway_client import chat_send

                await chat_send(
                    self._gw,
                    "",
                    on_delta=lambda delta: self._chat_view.append_delta(delta),
                    provider=self._config.get("provider"),
                    model=self._config.get("model"),
                    session_id=self._current_session,
                )
            except Exception:
                pass
            finally:
                self._chat_view.finish_streaming()

    # ─── Settings ────────────────────────────────────────────────────

    async def _handle_save_settings(self, config: dict[str, Any]) -> None:
        self._config.update(config)

        provider = config.get("provider") or DEFAULT_PROVIDER
        model = config.get("model") or ""
        if self._toolbar_obj:
            self._toolbar_obj.update_provider(provider, model)

        gw_url = config.get("gateway_url")
        if gw_url and gw_url != (self._gw._url if self._gw else ""):
            self._config["gateway_url"] = gw_url
            await self._connect_gateway()
            self._update_gw_indicator()

        if self._gw_connected and self._gw:
            try:
                await self._gw.call(
                    "config.patch",
                    {
                        "patch": {
                            "agents": {
                                "defaults": {
                                    "model": model,
                                    "provider": provider,
                                }
                            }
                        }
                    },
                )
            except Exception:
                pass

        self._show_snackbar(t("settings.saved"))

    def _update_gw_indicator(self) -> None:
        if hasattr(self, "_gw_indicator"):
            row = self._gw_indicator.content
            if isinstance(row, ft.Row) and len(row.controls) >= 2:
                dot = row.controls[0]
                label = row.controls[1]
                if isinstance(dot, ft.Container):
                    dot.bgcolor = ft.Colors.GREEN if self._gw_connected else ft.Colors.RED
                if isinstance(label, ft.Text):
                    label.value = "Gateway" if self._gw_connected else "Offline"
            try:
                if self._gw_indicator.page:
                    self._gw_indicator.update()
            except RuntimeError:
                pass

    # ─── Toolbar callbacks ───────────────────────────────────────────

    async def _handle_attach(self) -> None:
        """Open file picker and attach files to next message."""
        picker = ft.FilePicker()
        self._page.overlay.append(picker)
        self._page.update()

        result = await picker.pick_files_async(
            dialog_title=t("toolbar.attach_dialog", default="Select files to attach"),
            allow_multiple=True,
        )

        if result and result.files:
            if not hasattr(self, "_pending_attachments"):
                self._pending_attachments: list[dict[str, str]] = []
            for f in result.files:
                self._pending_attachments.append(
                    {
                        "name": f.name,
                        "path": f.path or "",
                        "size": str(f.size or 0),
                    }
                )
            names = ", ".join(f.name for f in result.files)
            self._show_snackbar(t("toolbar.attached", default="Attached: {names}", names=names))

        if picker in self._page.overlay:
            self._page.overlay.remove(picker)
            self._page.update()

    async def _handle_export_chat(self) -> None:
        """Export current chat session to a Markdown file."""
        messages = self._chat_view._messages_list.controls
        if not messages:
            self._show_snackbar(t("export.empty", default="No messages to export."))
            return

        lines: list[str] = [
            f"# Chat Export — {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}",
            "",
        ]
        for ctrl in messages:
            if isinstance(ctrl, ChatMessage):
                role = ctrl.role.capitalize()
                content = ctrl._message_content or ctrl._message_text or ""
                lines.append(f"### {role}")
                lines.append("")
                lines.append(content)
                lines.append("")

        export_text = "\n".join(lines)
        picker = ft.FilePicker()
        self._page.overlay.append(picker)
        self._page.update()

        result = await picker.save_file_async(
            dialog_title=t("export.save_title", default="Export chat"),
            file_name=f"chat-export-{datetime.now(UTC).strftime('%Y%m%d-%H%M')}.md",
            allowed_extensions=["md", "txt"],
        )

        if result:
            try:
                Path(result).write_text(export_text, encoding="utf-8")
                self._show_snackbar(t("export.saved", default="Chat exported to {path}", path=result))
            except Exception as exc:
                self._show_snackbar(f"Export failed: {exc}")

        if picker in self._page.overlay:
            self._page.overlay.remove(picker)
            self._page.update()

    async def _handle_voice_toggle(self) -> None:
        self._nav_rail.selected_index = 5
        await self._handle_nav_change(type("E", (), {"control": self._nav_rail})())

    async def _handle_clear_session(self) -> None:
        self._chat_view.clear_messages()

    async def _handle_model_change(self, model: str) -> None:
        self._config["model"] = model

    def _toggle_theme(self) -> None:
        if self._page:
            self._page.theme_mode = (
                ft.ThemeMode.LIGHT if self._page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
            )
            self._page.update()

    # ─── Session management ──────────────────────────────────────────

    def _ensure_session_manager(self) -> None:
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

        if self._gw_connected and self._gw:
            try:
                result = await self._gw.call("sessions.preview", {"path": session_id, "limit": 100})
                messages = result.get("messages", [])
                for msg in messages:
                    raw_content = msg.get("content", "")
                    content_str = (
                        raw_content if isinstance(raw_content, str) else str(raw_content) if raw_content else ""
                    )
                    self._chat_view.add_message(
                        msg.get("role", "user"),
                        content_str,
                        msg.get("tool_calls"),
                    )
            except Exception:
                self._load_session_messages(session_id)
        else:
            self._load_session_messages(session_id)

        await self._refresh_sessions()

    def _load_session_messages(self, session_id: str) -> None:
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
                        content = msg.content if isinstance(msg.content, str) else ""
                        self._chat_view.add_message(msg.role, content)
                    return

    async def _handle_new_session(self) -> None:
        import uuid

        new_id = uuid.uuid4().hex[:8]
        self._current_session = new_id
        self._session_mgr = None
        self._chat_view.clear_messages()
        await self._refresh_sessions()

    async def _handle_delete_session(self, session_id: str) -> None:
        if self._gw_connected and self._gw:
            try:
                await self._gw.call("sessions.delete", {"path": session_id})
            except Exception:
                self._delete_session_file(session_id)
        else:
            self._delete_session_file(session_id)

        if self._current_session == session_id:
            self._current_session = None
            self._chat_view.clear_messages()
        await self._refresh_sessions()

    def _delete_session_file(self, session_id: str) -> None:
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
        if self._gw_connected and self._gw:
            try:
                result = await self._gw.call("sessions.list")
                sessions_data = result.get("sessions", [])
                sessions: list[dict[str, str]] = []
                now = datetime.now(UTC)
                for s in sessions_data[:30]:
                    sid = s.get("id", s.get("path", ""))
                    name = s.get("name", sid[:16])
                    mtime = s.get("modified", "")
                    group = self._session_date_group(mtime, now) if mtime else ""
                    sessions.append({"id": sid, "name": name, "age": mtime, "group": group})
                self._session_sidebar.update_sessions(sessions)
                return
            except Exception:
                pass

        self._refresh_sessions_local()

    def _refresh_sessions_local(self) -> None:
        from pyclaw.config.paths import resolve_agents_dir

        agents_dir = resolve_agents_dir()
        sessions: list[dict[str, str]] = []
        now = datetime.now(UTC)

        main_sessions = agents_dir / "main" / "sessions"
        if main_sessions.is_dir():
            for f in sorted(main_sessions.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                mtime = f.stat().st_mtime
                delta = now.timestamp() - mtime
                if delta < 60:
                    age = f"{int(delta)}s ago"
                elif delta < 3600:
                    age = f"{int(delta / 60)}m ago"
                elif delta < 86400:
                    age = f"{int(delta / 3600)}h ago"
                else:
                    age = f"{int(delta / 86400)}d ago"

                group = ""
                if delta < 86400:
                    group = "Today"
                elif delta < 172800:
                    group = "Yesterday"
                elif delta < 604800:
                    group = "This Week"
                else:
                    group = "Earlier"

                sessions.append({"id": f.stem, "name": f.stem[:16], "age": age, "group": group})

        self._session_sidebar.update_sessions(sessions)

    # ─── UI state helpers ────────────────────────────────────────────────

    def _error_state(self, message: str, on_retry=None) -> ft.Container:
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
            alignment=ft.alignment.center,
            expand=True,
        )

    def _empty_state(self, message: str, icon=ft.Icons.INBOX) -> ft.Container:
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
            alignment=ft.alignment.center,
            expand=True,
        )

    @staticmethod
    def _session_date_group(mtime_str: str, now: datetime) -> str:
        try:
            mtime = datetime.fromisoformat(mtime_str)
            delta = (now - mtime).total_seconds()
        except Exception:
            return ""
        if delta < 86400:
            return "Today"
        elif delta < 172800:
            return "Yesterday"
        elif delta < 604800:
            return "This Week"
        return "Earlier"

    # ─── Plan panel ──────────────────────────────────────────────────

    def _build_plan_panel(self) -> ft.Column:
        from pyclaw.ui.components import page_header

        self._plan_list = ft.ListView(expand=True, spacing=6)
        refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Refresh",
            icon_size=20,
            on_click=lambda e: _fire_async(self._refresh_plans),
        )
        return ft.Column(
            controls=[
                page_header(ft.Icons.CHECKLIST, t("nav.plans", default="Plans"), [refresh_btn]),
                self._plan_list,
            ],
            spacing=0,
            expand=True,
        )

    async def _refresh_plans(self) -> None:
        from pyclaw.ui.components import card_tile, status_chip
        from pyclaw.ui.theme import StatusColors

        if not self._gw_connected or not self._gw:
            self._plan_list.controls = [
                self._error_state(
                    t("plans.offline", default="Connect to gateway to view plans."),
                    on_retry=self._refresh_plans,
                ),
            ]
            self._safe_update(self._plan_list)
            return
        try:
            result = await self._gw.call("plan.list")
            plans = result.get("plans", [])
            self._plan_list.controls.clear()
            if not plans:
                self._plan_list.controls.append(
                    self._empty_state("暂无执行计划", icon=ft.Icons.CHECKLIST),
                )
            for p in plans:
                status = p.get("status", "pending")
                color = {
                    "completed": StatusColors.SUCCESS,
                    "running": StatusColors.INFO,
                    "paused": StatusColors.WARNING,
                    "failed": StatusColors.ERROR,
                }.get(status, "#94a3b8")

                steps = p.get("steps", [])
                total = len(steps)
                done = sum(1 for s in steps if s.get("status") == "completed")

                actions: list[ft.Control] = []
                if status == "paused":
                    actions.append(
                        ft.IconButton(
                            icon=ft.Icons.PLAY_ARROW,
                            icon_size=16,
                            tooltip="Resume",
                            data=p.get("id"),
                            on_click=lambda e: _fire_async(self._resume_plan, e.control.data),
                        )
                    )
                actions.append(
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=16,
                        tooltip="Delete",
                        data=p.get("id"),
                        on_click=lambda e: _fire_async(self._delete_plan, e.control.data),
                    )
                )

                tile_content = ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECKLIST, color=color, size=20),
                        ft.Column(
                            [
                                ft.Text(p.get("goal", "Plan"), weight=ft.FontWeight.BOLD, size=13),
                                ft.Row(
                                    [
                                        status_chip(status, color),
                                        ft.Text(f"{done}/{total} steps", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            spacing=4,
                            expand=True,
                            tight=True,
                        ),
                        ft.Row(actions, spacing=0),
                    ],
                    spacing=8,
                )
                self._plan_list.controls.append(card_tile(tile_content))
            self._safe_update(self._plan_list)
        except Exception:
            logger.warning("_refresh_plans failed", exc_info=True)
            self._plan_list.controls = [
                self._error_state("加载失败", on_retry=self._refresh_plans),
            ]
            self._safe_update(self._plan_list)

    async def _resume_plan(self, plan_id: str) -> None:
        if self._gw:
            try:
                await self._gw.call("plan.resume", {"planId": plan_id})
                await self._refresh_plans()
            except Exception:
                logger.warning("_resume_plan failed", exc_info=True)

    async def _delete_plan(self, plan_id: str) -> None:
        if self._gw:
            try:
                await self._gw.call("plan.delete", {"planId": plan_id})
                await self._refresh_plans()
            except Exception:
                logger.warning("_delete_plan failed", exc_info=True)

    # ─── Cron panel ──────────────────────────────────────────────────

    def _build_cron_panel(self) -> ft.Column:
        from pyclaw.ui.components import page_header

        self._cron_list = ft.ListView(expand=True, spacing=6)
        self._cron_history_list = ft.ListView(spacing=4, height=200)

        add_name = ft.TextField(label="Name", dense=True, width=200, border_radius=12)
        add_schedule = ft.TextField(label="Schedule (cron)", dense=True, width=200, border_radius=12)
        add_message = ft.TextField(label="Message", dense=True, width=300, border_radius=12)

        async def _add_job(e: Any) -> None:
            if self._gw and add_name.value and add_schedule.value:
                try:
                    await self._gw.call(
                        "cron.add",
                        {
                            "name": add_name.value,
                            "schedule": add_schedule.value,
                            "message": add_message.value or "",
                        },
                    )
                    add_name.value = ""
                    add_schedule.value = ""
                    add_message.value = ""
                    await self._refresh_cron()
                except Exception:
                    pass

        add_btn = ft.Button("Add Job", icon=ft.Icons.ADD, on_click=_add_job)

        return ft.Column(
            controls=[
                page_header(
                    ft.Icons.SCHEDULE,
                    t("nav.cron", default="Scheduled Tasks"),
                    [
                        ft.IconButton(
                            icon=ft.Icons.REFRESH, icon_size=20, on_click=lambda e: _fire_async(self._refresh_cron)
                        )
                    ],
                ),
                self._cron_list,
                ft.Divider(height=1),
                ft.ExpansionTile(
                    title=ft.Text("Add Job", size=14),
                    controls=[
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row([add_name, add_schedule], spacing=8),
                                    add_message,
                                    add_btn,
                                ],
                                spacing=8,
                            ),
                            padding=12,
                        )
                    ],
                ),
                ft.Divider(height=1),
                ft.Container(
                    content=ft.Text("Execution History", size=14, weight=ft.FontWeight.BOLD),
                    padding=ft.padding.only(left=16, top=8, bottom=4),
                ),
                self._cron_history_list,
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    async def _refresh_cron(self) -> None:
        from pyclaw.ui.components import card_tile, status_chip
        from pyclaw.ui.theme import StatusColors

        if not self._gw_connected or not self._gw:
            self._cron_list.controls = [
                self._error_state(
                    "请连接 Gateway 以查看定时任务",
                    on_retry=self._refresh_cron,
                ),
            ]
            self._safe_update(self._cron_list)
            return
        try:
            result = await self._gw.call("cron.list")
            jobs = result.get("jobs", [])
            self._cron_list.controls.clear()
            if not jobs:
                self._cron_list.controls.append(
                    self._empty_state("暂无定时任务", icon=ft.Icons.SCHEDULE),
                )
            for job in jobs:
                enabled = job.get("enabled", True)
                job_color = StatusColors.SUCCESS if enabled else "#94a3b8"
                tile_content = ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.TIMER if enabled else ft.Icons.TIMER_OFF,
                            size=18,
                            color=job_color,
                        ),
                        ft.Column(
                            [
                                ft.Text(job.get("name", job.get("title", "Job")), weight=ft.FontWeight.BOLD, size=13),
                                ft.Row(
                                    [
                                        status_chip("enabled" if enabled else "disabled", job_color),
                                        ft.Text(job.get("schedule", ""), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            spacing=4,
                            expand=True,
                            tight=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=16,
                            data=job.get("id"),
                            on_click=lambda e: _fire_async(self._delete_cron_job, e.control.data),
                        ),
                    ],
                    spacing=8,
                )
                self._cron_list.controls.append(card_tile(tile_content))
            self._safe_update(self._cron_list)
        except Exception:
            logger.warning("_refresh_cron (jobs) failed", exc_info=True)
            self._cron_list.controls = [
                self._error_state("加载失败", on_retry=self._refresh_cron),
            ]
            self._safe_update(self._cron_list)
            return

        try:
            history = await self._gw.call("cron.history", {"limit": 20})
            records = history.get("records", [])
            self._cron_history_list.controls.clear()
            for rec in records:
                status = rec.get("status", "")
                color = {
                    "completed": StatusColors.SUCCESS,
                    "running": StatusColors.INFO,
                    "failed": StatusColors.ERROR,
                }.get(status, "#94a3b8")
                self._cron_history_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(width=8, height=8, border_radius=4, bgcolor=color),
                                ft.Text(rec.get("job_title", ""), size=12, expand=True),
                                ft.Text(rec.get("started_at", "")[:19], size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                status_chip(status, color),
                            ],
                            spacing=6,
                        ),
                        padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    )
                )
            self._safe_update(self._cron_history_list)
        except Exception:
            logger.warning("_refresh_cron (history) failed", exc_info=True)

    async def _delete_cron_job(self, job_id: str) -> None:
        if self._gw:
            try:
                await self._gw.call("cron.remove", {"id": job_id})
                await self._refresh_cron()
            except Exception:
                logger.warning("_delete_cron_job failed", exc_info=True)

    # ─── System panel ────────────────────────────────────────────────

    def _build_system_panel(self) -> ft.Column:
        from pyclaw.ui.components import page_header

        self._system_info_col = ft.Column(spacing=4)
        self._system_logs_list = ft.ListView(spacing=2, height=300)

        backup_btn = ft.OutlinedButton(
            "Export Backup",
            icon=ft.Icons.BACKUP,
            on_click=lambda e: _fire_async(self._export_backup),
        )
        doctor_btn = ft.OutlinedButton(
            "Run Doctor",
            icon=ft.Icons.HEALTH_AND_SAFETY,
            on_click=lambda e: _fire_async(self._run_doctor),
        )

        return ft.Column(
            controls=[
                page_header(
                    ft.Icons.MONITOR_HEART,
                    t("nav.system", default="System"),
                    [
                        ft.IconButton(
                            icon=ft.Icons.REFRESH, icon_size=20, on_click=lambda e: _fire_async(self._refresh_system)
                        )
                    ],
                ),
                ft.Container(content=self._system_info_col, padding=ft.padding.all(16)),
                ft.Divider(height=1),
                ft.Container(
                    content=ft.Row([backup_btn, doctor_btn], spacing=8),
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                ),
                ft.Divider(height=1),
                ft.Container(
                    content=ft.Text("Logs", size=14, weight=ft.FontWeight.BOLD),
                    padding=ft.padding.only(left=16, top=8, bottom=4),
                ),
                self._system_logs_list,
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    async def _refresh_system(self) -> None:
        if not self._gw_connected or not self._gw:
            self._system_info_col.controls = [
                self._error_state(
                    "请连接 Gateway 以查看系统信息",
                    on_retry=self._refresh_system,
                ),
            ]
            self._safe_update(self._system_info_col)
            return
        try:
            info = await self._gw.call("system.info")
            self._system_info_col.controls.clear()
            for key, val in info.items():
                self._system_info_col.controls.append(
                    ft.Row(
                        [
                            ft.Text(key, weight=ft.FontWeight.BOLD, size=12, width=150),
                            ft.Text(str(val), size=12),
                        ],
                        spacing=8,
                    )
                )
            self._safe_update(self._system_info_col)
        except Exception:
            logger.warning("_refresh_system (info) failed", exc_info=True)
            self._system_info_col.controls = [
                self._error_state("加载失败", on_retry=self._refresh_system),
            ]
            self._safe_update(self._system_info_col)

        try:
            logs_result = await self._gw.call("logs.tail", {"limit": 50})
            lines = logs_result.get("lines", [])
            self._system_logs_list.controls.clear()
            for line in lines:
                text = line if isinstance(line, str) else str(line)
                self._system_logs_list.controls.append(ft.Text(text, size=10, font_family="monospace", max_lines=2))
            self._safe_update(self._system_logs_list)
        except Exception:
            logger.warning("_refresh_system (logs) failed", exc_info=True)

    async def _export_backup(self) -> None:
        if self._gw:
            try:
                result = await self._gw.call("backup.export")
                path = result.get("path", "backup completed")
                self._show_snackbar(f"Backup exported: {path}")
            except Exception as exc:
                self._show_snackbar(f"Backup failed: {exc}")

    async def _run_doctor(self) -> None:
        if self._gw:
            try:
                result = await self._gw.call("doctor.run")
                checks = result.get("checks", result)
                self._system_info_col.controls.clear()
                self._system_info_col.controls.append(ft.Text("Doctor Results", size=14, weight=ft.FontWeight.BOLD))
                if isinstance(checks, list):
                    for check in checks:
                        name = check.get("name", "")
                        status = check.get("status", "")
                        color = ft.Colors.GREEN if status == "ok" else ft.Colors.RED
                        self._system_info_col.controls.append(
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.CHECK_CIRCLE if status == "ok" else ft.Icons.ERROR,
                                        size=16,
                                        color=color,
                                    ),
                                    ft.Text(name, size=12, expand=True),
                                    ft.Text(status, size=12, color=color),
                                ],
                                spacing=4,
                            )
                        )
                elif isinstance(checks, dict):
                    for k, v in checks.items():
                        self._system_info_col.controls.append(
                            ft.Row(
                                [
                                    ft.Text(k, size=12, weight=ft.FontWeight.BOLD, width=150),
                                    ft.Text(str(v), size=12),
                                ],
                                spacing=4,
                            )
                        )
                self._safe_update(self._system_info_col)
            except Exception:
                logger.warning("_run_doctor failed", exc_info=True)

    # ─── Channel refresh ─────────────────────────────────────────────

    async def _refresh_channels(self) -> None:
        if self._gw_connected and self._gw:
            try:
                result = await self._gw.call("channels.list")
                gw_channels = result.get("channels", [])
                self._channels_panel.update_channels(gw_channels)
                return
            except Exception:
                logger.warning("_refresh_channels failed", exc_info=True)
                self._channels_panel.update_channels(
                    [],
                    error="加载失败",
                    on_retry=self._refresh_channels,
                )
                return

        from pyclaw.config.io import load_config
        from pyclaw.config.paths import resolve_config_path

        channels: list[dict[str, Any]] = []
        try:
            config = load_config(resolve_config_path())
            ch_cfg = config.channels
            if ch_cfg:
                cfg_dict = ch_cfg.model_dump(by_alias=True, exclude_none=True)
                for name, cfg_val in cfg_dict.items():
                    if name == "defaults" or not isinstance(cfg_val, dict):
                        continue
                    enabled = cfg_val.get("enabled", True)
                    entry_meta = self._get_catalog_meta(name)
                    info: dict[str, Any] = {
                        "id": name,
                        "name": entry_meta.get("display_name", name.title()),
                        "enabled": enabled,
                        "status": "configured" if enabled else "disabled",
                    }
                    info.update(entry_meta)
                    channels.append(info)
        except Exception:
            self._channels_panel.update_channels(
                [],
                error="加载失败",
                on_retry=self._refresh_channels,
            )
            return
        self._channels_panel.update_channels(channels)

    @staticmethod
    def _get_catalog_meta(channel_type: str) -> dict[str, Any]:
        try:
            from pyclaw.channels.plugins.catalog import BUILTIN_CATALOG

            entry = BUILTIN_CATALOG.get(channel_type)
            if entry:
                spec = entry.action_spec
                return {
                    "display_name": entry.display_name,
                    "color": entry.color,
                    "capabilities": {
                        "typing": spec.supports_typing,
                        "reactions": spec.supports_reactions,
                        "threads": spec.supports_threads,
                        "editing": spec.supports_editing,
                        "buttons": spec.supports_buttons,
                        "pins": spec.supports_pins,
                    },
                }
        except Exception:
            pass
        return {}

    # ─── Permissions ─────────────────────────────────────────────────

    async def _check_permissions(self, page: ft.Page) -> None:
        """Show permission guard on mobile platforms before proceeding."""
        from pyclaw.ui.permissions import _IS_MOBILE, build_permission_guard_panel

        if not _IS_MOBILE:
            return

        guard = build_permission_guard_panel()
        if guard is None:
            return

        completed = asyncio.Event()

        async def on_continue() -> None:
            dialog.open = False
            page.update()
            completed.set()

        guard_panel = build_permission_guard_panel(on_continue=on_continue)
        dialog = ft.AlertDialog(
            content=ft.Container(content=guard_panel, width=400, height=400),
            modal=True,
            open=True,
        )
        page.overlay.append(dialog)
        page.update()
        await completed.wait()

    # ─── Onboarding ──────────────────────────────────────────────────

    async def _check_onboarding(self, page: ft.Page) -> None:
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
            model_id = config.get("model", DEFAULT_MODEL)

            provider_cfg = ModelProviderConfig(baseUrl="", apiKey=api_key) if api_key else None
            providers = {provider: provider_cfg} if provider_cfg else None

            channels_selected = config.get("channels", [])
            channels_data: dict[str, Any] = {}
            for ch_name in channels_selected:
                channels_data[ch_name] = {"enabled": True}

            cfg = PyClawConfig(
                models=ModelsConfig(default=None, providers=providers) if providers else None,
                agents=AgentsConfig(defaults=AgentDefaultsConfig(model=model_id, provider=provider, workspaceDir=None)),
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

    # ─── Local agent fallback ────────────────────────────────────────

    async def _get_agent_reply(self, message: str) -> str:
        from pyclaw.agents.runner import run_agent
        from pyclaw.agents.types import ModelConfig

        self._ensure_session_manager()
        model = ModelConfig(
            provider=self._config.get("provider", "openai"),
            model_id=self._config.get("model", DEFAULT_MODEL),
            api_key=self._config.get("api_key"),
            base_url=self._config.get("base_url"),
        )

        reply_parts: list[str] = []
        async for event in run_agent(prompt=message, session=self._session_mgr, model=model):
            if event.type == "message_update" and event.delta:
                reply_parts.append(event.delta)

        return "".join(reply_parts) or t("chat.no_response")

    def _show_snackbar(self, message: str) -> None:
        if self._page:
            sb = ft.SnackBar(content=ft.Text(message), open=True)
            self._page.overlay.append(sb)
            self._page.update()

    def _safe_update(self, control: ft.Control) -> None:
        try:
            if control.page:
                control.update()
        except RuntimeError:
            pass


def run_app() -> None:
    """Launch the Flet desktop application."""
    app = PyClawApp()
    ft.run(app.main)


def run_web(port: int = 8550) -> None:
    """Launch the Flet web application."""
    app = PyClawApp()
    ft.run(app.main, view=ft.AppView.WEB_BROWSER, port=port)
