"""Tests for gateway channels.list / channels.status handlers.

Validates:
- Handler creation and registration
- Config fallback when no ChannelManager is present
- Runtime channel info with catalog metadata overlay
- Metrics recording and retrieval
"""

from __future__ import annotations

from typing import Any

import pytest

from pyclaw.channels.base import ChannelPlugin, ChannelReply
from pyclaw.channels.manager import ChannelManager
from pyclaw.gateway.methods.channels import (
    _channel_metrics,
    create_channels_handlers,
    handle_channels_list,
    handle_channels_status,
    record_channel_metric,
    set_channel_manager,
    set_config_path,
)


class _MockConn:
    """Minimal mock for GatewayConnection."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, Any]] = []
        self.errors: list[tuple[str, str, str]] = []

    async def send_ok(self, frame_id: str, payload: Any) -> None:
        self.sent.append((frame_id, payload))

    async def send_error(self, frame_id: str, code: str, message: str) -> None:
        self.errors.append((frame_id, code, message))


class _MockChannel(ChannelPlugin):
    def __init__(self, cid: str = "telegram") -> None:
        self._id = cid
        self._running = True

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._id.title()

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send_reply(self, reply: ChannelReply) -> None:
        pass


@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset module-level state between tests."""
    set_channel_manager(None)
    set_config_path(None)
    _channel_metrics.clear()
    yield
    set_channel_manager(None)
    set_config_path(None)
    _channel_metrics.clear()


class TestCreateHandlers:
    def test_returns_dict_with_expected_keys(self):
        handlers = create_channels_handlers()
        assert "channels.list" in handlers
        assert "channels.status" in handlers
        for h in handlers.values():
            assert callable(h)


class TestHandleChannelsList:
    @pytest.mark.asyncio
    async def test_empty_when_no_manager_no_config(self):
        conn = _MockConn()
        await handle_channels_list(None, conn)
        assert len(conn.sent) == 1
        frame_id, payload = conn.sent[0]
        assert frame_id == "channels.list"
        assert payload["channels"] == []

    @pytest.mark.asyncio
    async def test_with_channel_manager(self):
        mgr = ChannelManager()
        ch = _MockChannel("telegram")
        mgr.register(ch)
        set_channel_manager(mgr)

        conn = _MockConn()
        await handle_channels_list(None, conn)
        assert len(conn.sent) == 1
        channels = conn.sent[0][1]["channels"]
        assert len(channels) >= 1
        tg = next(c for c in channels if c["id"] == "telegram")
        assert tg["running"] is True
        assert tg["source"] == "runtime"
        assert "display_name" in tg  # from catalog


class TestHandleChannelsStatus:
    @pytest.mark.asyncio
    async def test_not_found(self):
        conn = _MockConn()
        await handle_channels_status({"channel_id": "nonexistent"}, conn)
        assert len(conn.errors) == 1
        assert conn.errors[0][1] == "not_found"

    @pytest.mark.asyncio
    async def test_runtime_channel(self):
        mgr = ChannelManager()
        ch = _MockChannel("discord")
        mgr.register(ch)
        set_channel_manager(mgr)

        conn = _MockConn()
        await handle_channels_status({"channel_id": "discord"}, conn)
        assert len(conn.sent) == 1
        result = conn.sent[0][1]
        assert result["channel_id"] == "discord"
        assert result["running"] is True


class TestMetrics:
    def test_record_and_retrieve(self):
        record_channel_metric("telegram", "msg_sent")
        record_channel_metric("telegram", "msg_sent")
        record_channel_metric("telegram", "msg_failed")
        record_channel_metric("telegram", "connect")

        assert _channel_metrics["telegram"]["messages_sent"] == 2
        assert _channel_metrics["telegram"]["messages_failed"] == 1
        assert _channel_metrics["telegram"]["connected_since"] is not None

    def test_disconnect_clears_connected_since(self):
        record_channel_metric("slack", "connect")
        assert _channel_metrics["slack"]["connected_since"] is not None

        record_channel_metric("slack", "disconnect")
        assert _channel_metrics["slack"]["connected_since"] is None

    @pytest.mark.asyncio
    async def test_metrics_in_channels_list(self):
        mgr = ChannelManager()
        ch = _MockChannel("telegram")
        mgr.register(ch)
        set_channel_manager(mgr)

        record_channel_metric("telegram", "msg_sent")

        conn = _MockConn()
        await handle_channels_list(None, conn)
        channels = conn.sent[0][1]["channels"]
        tg = next(c for c in channels if c["id"] == "telegram")
        assert "metrics" in tg
        assert tg["metrics"]["messages_sent"] == 1
