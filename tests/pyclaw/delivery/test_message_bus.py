"""Tests for pyclaw.gateway.message_bus — async message routing."""

from pyclaw.gateway.message_bus import InboundMessage, MessageBus, OutboundMessage


class TestMessageBus:
    def test_publish_and_consume(self) -> None:
        bus = MessageBus()
        msg = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="hello")
        assert bus.publish_inbound(msg) is True
        assert bus.inbound_size == 1

        consumed = bus.try_consume_inbound()
        assert consumed is not None
        assert consumed.content == "hello"
        assert bus.inbound_size == 0

    def test_empty_consume(self) -> None:
        bus = MessageBus()
        assert bus.try_consume_inbound() is None

    def test_peek_for_session(self) -> None:
        bus = MessageBus()

        msg1 = InboundMessage(channel="t", sender_id="u1", chat_id="c1", content="for session A", session_key="A")
        msg2 = InboundMessage(channel="t", sender_id="u2", chat_id="c2", content="for session B", session_key="B")
        msg3 = InboundMessage(channel="t", sender_id="u3", chat_id="c3", content="also for A", session_key="A")

        bus.publish_inbound(msg1)
        bus.publish_inbound(msg2)
        bus.publish_inbound(msg3)

        found = bus.peek_inbound_for_session("A")
        assert found is not None
        assert found.content == "for session A"

        # msg2 and msg3 should still be in the queue
        assert bus.inbound_size == 2

    def test_peek_no_match(self) -> None:
        bus = MessageBus()
        msg = InboundMessage(channel="t", sender_id="u1", chat_id="c1", content="x", session_key="A")
        bus.publish_inbound(msg)

        found = bus.peek_inbound_for_session("Z")
        assert found is None
        # Original message should be put back
        assert bus.inbound_size == 1

    def test_closed_bus(self) -> None:
        bus = MessageBus()
        bus.close()
        msg = InboundMessage(channel="t", sender_id="u1", chat_id="c1", content="x")
        assert bus.publish_inbound(msg) is False

    def test_outbound(self) -> None:
        bus = MessageBus()
        msg = OutboundMessage(channel="discord", chat_id="ch1", content="reply")
        assert bus.publish_outbound(msg) is True
        assert bus.outbound_size == 1

    def test_buffer_full(self) -> None:
        bus = MessageBus(buffer_size=2)
        m1 = InboundMessage(channel="t", sender_id="u1", chat_id="c1", content="1")
        m2 = InboundMessage(channel="t", sender_id="u2", chat_id="c2", content="2")
        m3 = InboundMessage(channel="t", sender_id="u3", chat_id="c3", content="3")
        assert bus.publish_inbound(m1) is True
        assert bus.publish_inbound(m2) is True
        assert bus.publish_inbound(m3) is False  # buffer full
