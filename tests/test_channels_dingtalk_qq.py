"""Tests for DingTalk and QQ channel plugins."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pyclaw.channels.dingtalk.channel import DingTalkChannel
from pyclaw.channels.qq.channel import QQChannel


class TestDingTalkChannel:
    def test_init(self) -> None:
        ch = DingTalkChannel(client_id="app123", client_secret="secret")
        assert ch.id == "dingtalk"
        assert ch.name == "dingtalk"
        assert not ch.is_running

    def test_allow_from(self) -> None:
        ch = DingTalkChannel(
            client_id="app123",
            client_secret="secret",
            allow_from=["user1", "user2"],
        )
        assert ch._allow_from == {"user1", "user2"}

    def test_allow_from_none(self) -> None:
        ch = DingTalkChannel(client_id="app123", client_secret="secret")
        assert ch._allow_from is None

    @pytest.mark.asyncio
    async def test_start_requires_credentials(self) -> None:
        ch = DingTalkChannel()
        with pytest.raises(ValueError, match="clientId and clientSecret"):
            await ch.start()

    def test_on_message(self) -> None:
        ch = DingTalkChannel(client_id="app123", client_secret="secret")
        handler = AsyncMock()
        ch.on_message(handler)
        assert ch._handler is handler

    @pytest.mark.asyncio
    async def test_handle_callback_text(self) -> None:
        ch = DingTalkChannel(client_id="app123", client_secret="secret")
        handler = AsyncMock()
        ch.on_message(handler)

        payload = {
            "type": "CALLBACK",
            "data": '{"text":{"content":"Hello"},"senderStaffId":"uid1","senderNick":"Test","conversationId":"conv1","conversationType":"1","msgId":"m1","sessionWebhook":"https://oapi.dingtalk.com/robot/send"}',
            "headers": {},
        }
        await ch._handle_callback(payload)
        handler.assert_called_once()
        msg = handler.call_args[0][0]
        assert msg.text == "Hello"
        assert msg.sender_id == "uid1"
        assert msg.channel_id == "dingtalk"
        assert not msg.is_group

    @pytest.mark.asyncio
    async def test_handle_callback_group(self) -> None:
        ch = DingTalkChannel(client_id="app123", client_secret="secret")
        handler = AsyncMock()
        ch.on_message(handler)

        payload = {
            "type": "CALLBACK",
            "data": '{"text":{"content":"Hi group"},"senderStaffId":"uid2","senderNick":"User2","conversationId":"grp1","conversationType":"2","msgId":"m2"}',
            "headers": {},
        }
        await ch._handle_callback(payload)
        msg = handler.call_args[0][0]
        assert msg.is_group
        assert msg.chat_id == "grp1"

    @pytest.mark.asyncio
    async def test_handle_callback_filtered(self) -> None:
        ch = DingTalkChannel(client_id="app123", client_secret="secret", allow_from=["allowed"])
        handler = AsyncMock()
        ch.on_message(handler)

        payload = {
            "data": '{"text":{"content":"blocked"},"senderStaffId":"not_allowed","conversationId":"c1","conversationType":"1"}',
        }
        await ch._handle_callback(payload)
        handler.assert_not_called()


class TestQQChannel:
    def test_init(self) -> None:
        ch = QQChannel(app_id="100001", secret="sec")
        assert ch.id == "qq"
        assert ch.name == "qq"
        assert not ch.is_running

    def test_sandbox_api_base(self) -> None:
        ch = QQChannel(app_id="100001", secret="sec", sandbox=True)
        assert "sandbox" in ch._api_base

    def test_production_api_base(self) -> None:
        ch = QQChannel(app_id="100001", secret="sec")
        assert "sandbox" not in ch._api_base

    @pytest.mark.asyncio
    async def test_start_requires_credentials(self) -> None:
        ch = QQChannel()
        with pytest.raises(ValueError, match="appId and secret"):
            await ch.start()

    def test_on_message(self) -> None:
        ch = QQChannel(app_id="100001", secret="sec")
        handler = AsyncMock()
        ch.on_message(handler)
        assert ch._handler is handler

    @pytest.mark.asyncio
    async def test_handle_message_private(self) -> None:
        ch = QQChannel(app_id="100001", secret="sec")
        handler = AsyncMock()
        ch.on_message(handler)

        d = {
            "content": "Hello from QQ",
            "author": {"member_openid": "uid1", "username": "QQUser"},
            "id": "msg001",
        }
        await ch._handle_message(d, is_group=False)
        handler.assert_called_once()
        msg = handler.call_args[0][0]
        assert msg.text == "Hello from QQ"
        assert msg.sender_id == "uid1"
        assert msg.channel_id == "qq"
        assert not msg.is_group

    @pytest.mark.asyncio
    async def test_handle_message_group(self) -> None:
        ch = QQChannel(app_id="100001", secret="sec")
        handler = AsyncMock()
        ch.on_message(handler)

        d = {
            "content": "Group msg",
            "author": {"member_openid": "uid2", "username": "User2"},
            "group_openid": "grp001",
            "id": "msg002",
        }
        await ch._handle_message(d, is_group=True)
        msg = handler.call_args[0][0]
        assert msg.is_group
        assert msg.chat_id == "grp001"

    @pytest.mark.asyncio
    async def test_handle_message_filtered(self) -> None:
        ch = QQChannel(app_id="100001", secret="sec", allow_from=["allowed"])
        handler = AsyncMock()
        ch.on_message(handler)

        d = {
            "content": "blocked",
            "author": {"member_openid": "not_allowed"},
            "id": "msg003",
        }
        await ch._handle_message(d, is_group=False)
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_empty(self) -> None:
        ch = QQChannel(app_id="100001", secret="sec")
        handler = AsyncMock()
        ch.on_message(handler)

        d = {"content": "  ", "author": {"member_openid": "uid1"}, "id": "msg004"}
        await ch._handle_message(d, is_group=False)
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_event_ready(self) -> None:
        ch = QQChannel(app_id="100001", secret="sec")
        data = {"op": 0, "t": "READY", "s": 1, "d": {"session_id": "sess123"}}
        await ch._handle_event(data)
        assert ch._session_id == "sess123"
        assert ch._seq == 1
