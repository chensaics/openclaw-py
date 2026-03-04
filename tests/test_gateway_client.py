"""Tests for the UI gateway WebSocket client."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from pyclaw.ui.gateway_client import GatewayClient, GatewayError


class TestGatewayClient:
    """Unit tests for GatewayClient."""

    def test_init_defaults(self) -> None:
        client = GatewayClient()
        assert client._url == "ws://127.0.0.1:18789/"
        assert client._client_name == "pyclaw-flet-ui"
        assert not client.connected

    def test_init_custom(self) -> None:
        client = GatewayClient(
            url="ws://localhost:9999/",
            auth_token="test-token",
            client_name="test-client",
        )
        assert client._url == "ws://localhost:9999/"
        assert client._auth_token == "test-token"

    def test_on_event_registers_listener(self) -> None:
        client = GatewayClient()
        cb = MagicMock()
        client.on_event("chat.delta", cb)
        assert "chat.delta" in client._event_listeners
        assert cb in client._event_listeners["chat.delta"]

    def test_off_event_removes_listener(self) -> None:
        client = GatewayClient()
        cb = MagicMock()
        client.on_event("chat.delta", cb)
        client.off_event("chat.delta", cb)
        assert cb not in client._event_listeners["chat.delta"]

    def test_off_event_nonexistent(self) -> None:
        client = GatewayClient()
        cb = MagicMock()
        client.off_event("no.such.event", cb)

    def test_on_any_event(self) -> None:
        client = GatewayClient()
        cb = MagicMock()
        client.on_any_event(cb)
        assert cb in client._global_listeners

    def test_handle_response_resolves_future(self) -> None:
        client = GatewayClient()
        loop = asyncio.new_event_loop()
        fut = loop.create_future()
        client._pending["req-123"] = fut

        client._handle_response(
            {
                "type": "res",
                "id": "req-123",
                "ok": True,
                "payload": {"result": "hello"},
            }
        )

        assert fut.done()
        assert fut.result() == {"result": "hello"}
        loop.close()

    def test_handle_response_rejects_on_error(self) -> None:
        client = GatewayClient()
        loop = asyncio.new_event_loop()
        fut = loop.create_future()
        client._pending["req-456"] = fut

        client._handle_response(
            {
                "type": "res",
                "id": "req-456",
                "ok": False,
                "error": {"code": "not_found", "message": "Not found"},
            }
        )

        assert fut.done()
        with pytest.raises(GatewayError) as exc_info:
            fut.result()
        assert exc_info.value.code == "not_found"
        loop.close()

    def test_handle_response_ok_no_payload(self) -> None:
        client = GatewayClient()
        loop = asyncio.new_event_loop()
        fut = loop.create_future()
        client._pending["req-789"] = fut

        client._handle_response(
            {
                "type": "res",
                "id": "req-789",
                "ok": True,
            }
        )

        assert fut.result() == {}
        loop.close()

    def test_handle_response_ignores_unknown_id(self) -> None:
        client = GatewayClient()
        client._handle_response(
            {
                "type": "res",
                "id": "unknown",
                "ok": True,
            }
        )

    def test_handle_event_fires_listeners(self) -> None:
        client = GatewayClient()
        received: list[str] = []

        def on_test(payload: dict) -> None:
            received.append(payload.get("text", ""))

        client.on_event("test.event", on_test)
        asyncio.get_event_loop().run_until_complete(
            client._handle_event(
                {
                    "type": "event",
                    "event": "test.event",
                    "payload": {"text": "hello"},
                }
            )
        )
        assert received == ["hello"]

    def test_handle_event_fires_global_listeners(self) -> None:
        client = GatewayClient()
        received: list[tuple] = []

        def on_any(event_name: str, payload: dict) -> None:
            received.append((event_name, payload))

        client.on_any_event(on_any)
        asyncio.get_event_loop().run_until_complete(
            client._handle_event(
                {
                    "type": "event",
                    "event": "test.global",
                    "payload": {"x": 1},
                }
            )
        )
        assert len(received) == 1
        assert received[0] == ("test.global", {"x": 1})

    def test_call_raises_when_not_connected(self) -> None:
        client = GatewayClient()
        with pytest.raises(GatewayError) as exc_info:
            asyncio.get_event_loop().run_until_complete(client.call("health"))
        assert exc_info.value.code == "not_connected"

    def test_disconnect_clears_state(self) -> None:
        client = GatewayClient()
        client._connected = True
        client._should_reconnect = True
        asyncio.get_event_loop().run_until_complete(client.disconnect())
        assert not client._connected
        assert not client._should_reconnect

    def test_multiple_event_listeners(self) -> None:
        client = GatewayClient()
        results: list[int] = []
        client.on_event("multi", lambda p: results.append(1))
        client.on_event("multi", lambda p: results.append(2))
        asyncio.get_event_loop().run_until_complete(
            client._handle_event({"type": "event", "event": "multi", "payload": {}})
        )
        assert results == [1, 2]

    def test_handle_response_error_with_details(self) -> None:
        client = GatewayClient()
        loop = asyncio.new_event_loop()
        fut = loop.create_future()
        client._pending["detail-req"] = fut

        client._handle_response(
            {
                "type": "res",
                "id": "detail-req",
                "ok": False,
                "error": {
                    "code": "rate_limit",
                    "message": "Too many requests",
                    "details": {"retryAfterMs": 5000},
                },
            }
        )

        with pytest.raises(GatewayError) as exc_info:
            fut.result()
        assert exc_info.value.code == "rate_limit"
        assert exc_info.value.details == {"retryAfterMs": 5000}
        loop.close()


class TestGatewayError:
    def test_error_fields(self) -> None:
        err = GatewayError("test_code", "Test message", {"detail": 1})
        assert err.code == "test_code"
        assert str(err) == "Test message"
        assert err.details == {"detail": 1}

    def test_error_no_details(self) -> None:
        err = GatewayError("err", "msg")
        assert err.details is None


class TestTheme:
    def test_theme_defaults(self) -> None:
        from pyclaw.ui.theme import get_theme

        theme = get_theme()
        assert theme.colors.primary == "#6366f1"
        assert theme.border_radius == 12
        assert theme.breakpoint_mobile == 600
        assert theme.nav_rail_width == 72

    def test_set_seed_color(self) -> None:
        from pyclaw.ui.theme import get_theme, set_seed_color

        set_seed_color("#ff0000")
        assert get_theme().colors.primary == "#ff0000"
        set_seed_color("#6366f1")

    def test_toggle_theme(self) -> None:
        from pyclaw.ui.theme import LIGHT_THEME, set_theme, toggle_theme

        set_theme(LIGHT_THEME)
        dark = toggle_theme()
        assert dark.name == "dark"
        light = toggle_theme()
        assert light.name == "light"

    def test_dark_color_scheme(self) -> None:
        from pyclaw.ui.theme import DarkColorScheme

        dark = DarkColorScheme()
        assert dark.surface == "#1e293b"
        assert dark.background == "#0f172a"
        assert dark.surface_container == "#1e293b"


class TestI18n:
    def test_new_keys_exist(self) -> None:
        from pyclaw.ui.i18n import I18n

        i18n = I18n("en")
        assert i18n.t("nav.plans") == "Plans"
        assert i18n.t("nav.cron") == "Cron"
        assert i18n.t("nav.system") == "System"
        assert i18n.t("chat.abort") == "Stop"
        assert i18n.t("chat.edit") == "Edit"
        assert i18n.t("sessions.search") == "Search sessions..."
        assert i18n.t("settings.gateway") == "Gateway"
        assert i18n.t("settings.seed_color") == "Theme Color"

    def test_zh_cn_keys(self) -> None:
        from pyclaw.ui.i18n import I18n

        i18n = I18n("zh-CN")
        assert i18n.t("nav.plans") == "计划"
        assert i18n.t("nav.cron") == "定时任务"
        assert i18n.t("nav.system") == "系统"
        assert i18n.t("chat.abort") == "停止"
        assert i18n.t("settings.seed_color") == "主题色"

    def test_ja_keys(self) -> None:
        from pyclaw.ui.i18n import I18n

        i18n = I18n("ja")
        assert i18n.t("nav.plans") == "プラン"
        assert i18n.t("nav.system") == "システム"
        assert i18n.t("chat.abort") == "停止"
        assert i18n.t("settings.seed_color") == "テーマカラー"

    def test_fallback_to_english(self) -> None:
        from pyclaw.ui.i18n import I18n

        i18n = I18n("de")
        assert i18n.t("nav.plans") == "Plans"

    def test_missing_key_returns_key(self) -> None:
        from pyclaw.ui.i18n import I18n

        i18n = I18n("en")
        assert i18n.t("nonexistent.key") == "nonexistent.key"
