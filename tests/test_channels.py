"""Tests for channel base, manager, and message routing."""

import pytest

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply
from pyclaw.channels.manager import ChannelManager


class MockChannel(ChannelPlugin):
    """A mock channel for testing the abstraction layer."""

    def __init__(self, channel_id: str = "mock") -> None:
        self._id = channel_id
        self._running = False
        self.sent_replies: list[ChannelReply] = []
        self.started = False
        self.stopped = False

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return f"Mock ({self._id})"

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True
        self.started = True

    async def stop(self) -> None:
        self._running = False
        self.stopped = True

    async def send_reply(self, reply: ChannelReply) -> None:
        self.sent_replies.append(reply)

    async def simulate_message(self, text: str, sender: str = "user1") -> None:
        """Simulate an incoming message for testing."""
        msg = ChannelMessage(
            channel_id=self.id,
            sender_id=sender,
            sender_name=sender,
            text=text,
            chat_id="chat1",
            message_id="msg1",
        )
        if self.message_callback:
            await self.message_callback(msg)


# ---------- ChannelPlugin protocol ----------


def test_mock_channel_is_channel_plugin():
    ch = MockChannel()
    assert isinstance(ch, ChannelPlugin)


@pytest.mark.asyncio
async def test_channel_start_stop():
    ch = MockChannel()
    assert not ch.is_running
    await ch.start()
    assert ch.is_running
    assert ch.started
    await ch.stop()
    assert not ch.is_running
    assert ch.stopped


@pytest.mark.asyncio
async def test_channel_send_reply():
    ch = MockChannel()
    reply = ChannelReply(text="Hello!", chat_id="chat1")
    await ch.send_reply(reply)
    assert len(ch.sent_replies) == 1
    assert ch.sent_replies[0].text == "Hello!"


# ---------- ChannelMessage ----------


def test_channel_message_fields():
    msg = ChannelMessage(
        channel_id="telegram",
        sender_id="123",
        sender_name="Alice",
        text="Hi",
        chat_id="456",
        message_id="789",
        is_group=True,
        is_owner=True,
    )
    assert msg.channel_id == "telegram"
    assert msg.is_owner is True
    assert msg.is_group is True


# ---------- ChannelManager ----------


@pytest.mark.asyncio
async def test_manager_register_and_list():
    mgr = ChannelManager()
    ch1 = MockChannel("telegram")
    ch2 = MockChannel("discord")
    mgr.register(ch1)
    mgr.register(ch2)
    channels = mgr.list_channels()
    assert len(channels) == 2
    ids = {c["id"] for c in channels}
    assert ids == {"telegram", "discord"}


@pytest.mark.asyncio
async def test_manager_start_stop_all():
    mgr = ChannelManager()
    ch1 = MockChannel("telegram")
    ch2 = MockChannel("discord")
    mgr.register(ch1)
    mgr.register(ch2)

    await mgr.start_all()
    assert ch1.is_running
    assert ch2.is_running

    await mgr.stop_all()
    assert not ch1.is_running
    assert not ch2.is_running


@pytest.mark.asyncio
async def test_manager_message_routing():
    """Messages from a channel should be routed to the handler and replies sent back."""
    mgr = ChannelManager()
    ch = MockChannel("telegram")
    mgr.register(ch)

    received_messages: list[ChannelMessage] = []

    async def handler(msg: ChannelMessage) -> str:
        received_messages.append(msg)
        return f"Echo: {msg.text}"

    mgr.set_message_handler(handler)

    await ch.simulate_message("Hello!")

    assert len(received_messages) == 1
    assert received_messages[0].text == "Hello!"
    assert len(ch.sent_replies) == 1
    assert ch.sent_replies[0].text == "Echo: Hello!"


@pytest.mark.asyncio
async def test_manager_no_handler():
    """Without a handler, messages should be dropped silently."""
    mgr = ChannelManager()
    ch = MockChannel()
    mgr.register(ch)

    # No handler set — should not raise
    await ch.simulate_message("Hello!")
    assert len(ch.sent_replies) == 0


@pytest.mark.asyncio
async def test_manager_handler_returns_none():
    """If handler returns None, no reply should be sent."""
    mgr = ChannelManager()
    ch = MockChannel()
    mgr.register(ch)

    async def handler(msg: ChannelMessage) -> str | None:
        return None

    mgr.set_message_handler(handler)
    await ch.simulate_message("Hello!")
    assert len(ch.sent_replies) == 0


@pytest.mark.asyncio
async def test_manager_handler_error():
    """Handler errors should not crash — an error reply should be sent."""
    mgr = ChannelManager()
    ch = MockChannel()
    mgr.register(ch)

    async def handler(msg: ChannelMessage) -> str:
        raise ValueError("boom")

    mgr.set_message_handler(handler)
    await ch.simulate_message("Hello!")
    assert len(ch.sent_replies) == 1
    assert "error" in ch.sent_replies[0].text.lower()


@pytest.mark.asyncio
async def test_manager_get_channel():
    mgr = ChannelManager()
    ch = MockChannel("telegram")
    mgr.register(ch)

    assert mgr.get("telegram") is ch
    assert mgr.get("nonexistent") is None


@pytest.mark.asyncio
async def test_manager_multiple_channels():
    """Messages should route to the correct channel's reply."""
    mgr = ChannelManager()
    ch_tg = MockChannel("telegram")
    ch_dc = MockChannel("discord")
    mgr.register(ch_tg)
    mgr.register(ch_dc)

    async def handler(msg: ChannelMessage) -> str:
        return f"Reply via {msg.channel_id}"

    mgr.set_message_handler(handler)

    await ch_tg.simulate_message("Hi from TG")
    await ch_dc.simulate_message("Hi from DC")

    assert len(ch_tg.sent_replies) == 1
    assert "telegram" in ch_tg.sent_replies[0].text
    assert len(ch_dc.sent_replies) == 1
    assert "discord" in ch_dc.sent_replies[0].text
