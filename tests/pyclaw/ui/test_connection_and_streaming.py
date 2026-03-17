from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from pyclaw.constants.runtime import DEFAULT_GATEWAY_WS_URL_SLASH
from pyclaw.ui.app import ChatMessage, ChatView, PyClawApp, SettingsView
from pyclaw.ui.config_panel import _coerce_config_value
from pyclaw.ui.gateway_client import GatewayClient
from pyclaw.ui.overview_panel import build_overview_panel

ft = pytest.importorskip("flet")


def test_gateway_client_emits_connection_states() -> None:
    client = GatewayClient()
    seen: list[tuple[str, dict[str, object]]] = []
    client.on_connection_state(lambda state, meta: seen.append((state, meta)))

    client._set_connection_state("connecting")
    client._set_connection_state("reconnecting", retry_in=1.0)
    client._set_connection_state("connected")
    client._set_connection_state("error", error="boom")

    assert [s for s, _ in seen] == ["connecting", "reconnecting", "connected", "error"]
    assert client.connection_state == "error"
    assert client.last_error == "boom"


@pytest.mark.asyncio
async def test_overview_refresh_safe_without_page() -> None:
    gw = type(
        "GW", (), {"connected": True, "call": AsyncMock(return_value={"version": "1.0.0", "uptime_seconds": 0})}
    )()
    panel = build_overview_panel(get_gateway_client=lambda: gw, get_connection_state=lambda: "connected")
    assert isinstance(panel, ft.Column)
    assert hasattr(panel, "refresh")
    await panel.refresh()


def test_chat_message_can_skip_markdown_rendering() -> None:
    msg = ChatMessage("assistant", "")
    msg.update_content("stream chunk", render_markdown=False)
    assert isinstance(msg._content_control, ft.Text)


def test_chat_view_rehydrates_markdown_on_finish() -> None:
    view = ChatView()
    view.start_streaming()
    view.append_delta("hello ")
    view.append_delta("**world**")
    view.finish_streaming()
    assert view._current_assistant_msg is None


def test_chat_view_welcome_state_visibility() -> None:
    view = ChatView()
    assert view._welcome_state.visible is True
    view.add_message("user", "hello")
    assert view._welcome_state.visible is False
    view.clear_messages()
    assert view._welcome_state.visible is True


def test_session_path_resolution_prefers_gateway_path() -> None:
    app = PyClawApp()
    app._session_paths_by_id = {"abc123": "/tmp/main/sessions/abc123.jsonl"}
    assert app._resolve_session_path("abc123").endswith("abc123.jsonl")
    assert app._resolve_session_path("missing") == "missing"


def test_config_coercion_preserves_numeric_types() -> None:
    assert _coerce_config_value("3", "integer") == 3
    assert _coerce_config_value("3.5", "number") == 3.5
    assert _coerce_config_value('{"a":1}', "object") == {"a": 1}
    assert _coerce_config_value("[1,2]", "array") == [1, 2]


def test_settings_view_returns_grouped_options() -> None:
    view = SettingsView(
        current_config={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.6,
            "context_turns": 8,
            "stream_output": True,
            "max_tokens": 2048,
            "show_prompt": True,
            "message_style": "standard",
            "gateway_url": "ws://localhost:8765/ws",
            "auth_token": "secret",
            "locale": "zh-CN",
            "seed_color": "#10b981",
        }
    )
    cfg = view.get_config()
    assert cfg["temperature"] == 0.6
    assert cfg["context_turns"] == 8
    assert cfg["max_tokens"] == 2048
    assert cfg["locale"] == "zh-CN"


@pytest.mark.asyncio
async def test_save_settings_token_change_uses_default_gateway_url() -> None:
    app = PyClawApp()
    app._config.update({"gateway_url": "ws://example/ws", "auth_token": "old-token"})
    app._toolbar_obj = None
    app._gw_connected = False
    app._page = None
    app._show_snackbar = lambda _message: None  # type: ignore[assignment]

    reconnect_calls = {"count": 0}

    async def fake_connect_gateway() -> None:
        reconnect_calls["count"] += 1

    app._connect_gateway = fake_connect_gateway  # type: ignore[assignment]
    app._update_gw_indicator = lambda: None  # type: ignore[assignment]

    await app._handle_save_settings(
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "gateway_url": None,
            "auth_token": "new-token",
        }
    )

    assert app._config["gateway_url"] == DEFAULT_GATEWAY_WS_URL_SLASH
    assert app._config["auth_token"] == "new-token"
    assert reconnect_calls["count"] == 1


@pytest.mark.asyncio
async def test_gateway_client_reconnect_loop_eventually_recovers(monkeypatch) -> None:
    client = GatewayClient()
    client._should_reconnect = True
    client._connected = False
    client._reconnect_delay = 0.01

    attempts = {"n": 0}
    states: list[str] = []
    client.on_connection_state(lambda state, _meta: states.append(state))

    async def fake_connect() -> None:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        client._connected = True
        client._set_connection_state("connected")

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(client, "connect", fake_connect)
    monkeypatch.setattr("pyclaw.ui.gateway_client.asyncio.sleep", fast_sleep)

    await asyncio.wait_for(client._reconnect_loop(), timeout=2.0)

    assert attempts["n"] == 3
    assert client.connected is True
    assert "reconnecting" in states
    assert states[-1] == "connected"
