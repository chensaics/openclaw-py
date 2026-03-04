"""Tests for auto-reply engine."""

from __future__ import annotations

import time

from pyclaw.agents.auto_reply import (
    AutoReplyConfig,
    ConversationTimestamp,
    ReplyAction,
    StreamingSentinelFilter,
    evaluate_reply,
)


class TestEvaluateReply:
    def test_normal_reply(self) -> None:
        result = evaluate_reply("Hello, how can I help?")
        assert result.action == ReplyAction.SEND
        assert result.text == "Hello, how can I help?"

    def test_no_reply_sentinel(self) -> None:
        result = evaluate_reply("NO_REPLY")
        assert result.action == ReplyAction.SUPPRESS

    def test_no_reply_with_whitespace(self) -> None:
        result = evaluate_reply("  NO_REPLY  ")
        assert result.action == ReplyAction.SUPPRESS

    def test_trailing_no_reply(self) -> None:
        result = evaluate_reply("Some text NO_REPLY")
        assert result.action == ReplyAction.SEND
        assert result.text == "Some text"

    def test_empty_reply(self) -> None:
        result = evaluate_reply("")
        assert result.action == ReplyAction.SUPPRESS

    def test_whitespace_only(self) -> None:
        result = evaluate_reply("   ")
        assert result.action == ReplyAction.SUPPRESS

    def test_heartbeat_ping(self) -> None:
        result = evaluate_reply("HEARTBEAT_PING")
        assert result.action == ReplyAction.HEARTBEAT

    def test_heartbeat_keepalive(self) -> None:
        result = evaluate_reply("HEARTBEAT_KEEPALIVE")
        assert result.action == ReplyAction.HEARTBEAT

    def test_heartbeat_custom(self) -> None:
        result = evaluate_reply("HEARTBEAT_ABC123")
        assert result.action == ReplyAction.HEARTBEAT

    def test_disabled_suppression(self) -> None:
        cfg = AutoReplyConfig(suppress_no_reply=False)
        result = evaluate_reply("NO_REPLY", config=cfg)
        assert result.action == ReplyAction.SEND

    def test_disabled_heartbeat(self) -> None:
        cfg = AutoReplyConfig(suppress_heartbeat=False)
        result = evaluate_reply("HEARTBEAT_PING", config=cfg)
        assert result.action == ReplyAction.SEND

    def test_only_no_reply_trailing(self) -> None:
        result = evaluate_reply("NO_REPLY")
        assert result.action == ReplyAction.SUPPRESS

    def test_preserves_original(self) -> None:
        result = evaluate_reply("  hello  NO_REPLY")
        assert result.original_text == "  hello  NO_REPLY"


class TestStreamingSentinelFilter:
    def test_normal_streaming(self) -> None:
        f = StreamingSentinelFilter()
        assert f.feed("Hello ") == "Hello "
        assert f.feed("world") == "world"
        text, action = f.flush()
        assert action == ReplyAction.SEND

    def test_buffers_partial_sentinel(self) -> None:
        f = StreamingSentinelFilter()
        out1 = f.feed("Some text NO_")
        # "NO_" should be buffered
        assert "NO_" not in out1
        out2 = f.feed("more text")
        # Buffer resolved — "NO_" was not a sentinel
        assert "NO_" in out2 or "NO_" in out1

    def test_full_no_reply_suppressed(self) -> None:
        f = StreamingSentinelFilter()
        f.feed("NO_REPLY")
        text, action = f.flush()
        assert action == ReplyAction.SUPPRESS
        assert text == ""

    def test_heartbeat_detected(self) -> None:
        f = StreamingSentinelFilter()
        f.feed("HEARTBEAT_PING")
        text, action = f.flush()
        assert action == ReplyAction.HEARTBEAT

    def test_disabled_filter(self) -> None:
        cfg = AutoReplyConfig(filter_streaming_sentinels=False)
        f = StreamingSentinelFilter(cfg)
        assert f.feed("NO_REPLY") == "NO_REPLY"

    def test_empty_flush(self) -> None:
        f = StreamingSentinelFilter()
        text, action = f.flush()
        assert text == ""
        assert action == ReplyAction.SEND


class TestConversationTimestamp:
    def test_auto_timestamp(self) -> None:
        before = time.time()
        ts = ConversationTimestamp()
        after = time.time()
        assert before <= ts.unix <= after

    def test_iso_format(self) -> None:
        ts = ConversationTimestamp(unix=1709164800.0)  # 2024-02-28 16:00 UTC
        assert "2024" in ts.iso
        assert "T" in ts.iso

    def test_readable_format(self) -> None:
        ts = ConversationTimestamp(unix=1709164800.0)
        assert "2024" in ts.readable

    def test_valid_range(self) -> None:
        ts = ConversationTimestamp(unix=time.time())
        assert ts.is_valid is True

    def test_invalid_old(self) -> None:
        ts = ConversationTimestamp(unix=1000000.0)
        assert ts.is_valid is False

    def test_from_value_int(self) -> None:
        ts = ConversationTimestamp.from_value(time.time())
        assert ts is not None
        assert ts.is_valid

    def test_from_value_string(self) -> None:
        ts = ConversationTimestamp.from_value(str(time.time()))
        assert ts is not None

    def test_from_value_none(self) -> None:
        assert ConversationTimestamp.from_value(None) is None

    def test_from_value_invalid(self) -> None:
        assert ConversationTimestamp.from_value("not-a-number") is None
