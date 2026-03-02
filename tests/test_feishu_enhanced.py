"""Tests for Feishu enhanced features — reactions, routing, messages, runtime."""

from __future__ import annotations

import time

import pytest

from pyclaw.channels.feishu.reactions import (
    ReactionEvent,
    ReactionNotificationMode,
    create_synthetic_turn,
    parse_reaction_event,
    should_process_reaction,
)
from pyclaw.channels.feishu.routing import (
    FeishuRoutingConfig,
    GroupSessionScope,
    ReplyInThread,
    is_sender_allowed_in_group,
    resolve_feishu_session_key,
    resolve_reply_params,
)
from pyclaw.channels.feishu.messages import (
    parse_feishu_message,
    parse_merge_forward,
    parse_rich_text,
    parse_share_chat,
    resolve_media_type,
    resolve_send_msg_type,
)
from pyclaw.channels.feishu.runtime import (
    ProbeCache,
    TypingBackoff,
    WebhookRateLimiter,
)


class TestReactionParsing:
    def test_parse_created(self) -> None:
        body = {
            "header": {"event_type": "im.message.reaction.created_v1"},
            "event": {
                "message_id": "msg_123",
                "reaction_type": {"emoji_type": "THUMBSUP"},
                "operator": {
                    "operator_id": {"open_id": "ou_abc"},
                    "operator_type": "user",
                },
            },
        }
        event = parse_reaction_event(body)
        assert event is not None
        assert event.action == "created"
        assert event.reaction_type == "THUMBSUP"
        assert event.user_id == "ou_abc"

    def test_parse_deleted(self) -> None:
        body = {
            "header": {"event_type": "im.message.reaction.deleted_v1"},
            "event": {
                "message_id": "msg_123",
                "reaction_type": {"emoji_type": "HEART"},
                "operator": {"operator_id": {"open_id": "ou_abc"}, "operator_type": "user"},
            },
        }
        event = parse_reaction_event(body)
        assert event is not None
        assert event.action == "deleted"

    def test_parse_non_reaction(self) -> None:
        body = {"header": {"event_type": "im.message.receive_v1"}, "event": {}}
        assert parse_reaction_event(body) is None


class TestReactionShouldProcess:
    def test_off_mode(self) -> None:
        event = ReactionEvent(message_id="m1", reaction_type="LIKE", user_id="u1", action="created")
        assert should_process_reaction(event, mode=ReactionNotificationMode.OFF) is False

    def test_own_mode_bot_message(self) -> None:
        event = ReactionEvent(message_id="m1", reaction_type="LIKE", user_id="u1", action="created")
        assert should_process_reaction(event, mode=ReactionNotificationMode.OWN, is_bot_message=True) is True

    def test_own_mode_non_bot(self) -> None:
        event = ReactionEvent(message_id="m1", reaction_type="LIKE", user_id="u1", action="created")
        assert should_process_reaction(event, mode=ReactionNotificationMode.OWN, is_bot_message=False) is False

    def test_skip_self_reaction(self) -> None:
        event = ReactionEvent(message_id="m1", reaction_type="LIKE", user_id="bot1", action="created")
        assert should_process_reaction(event, bot_user_id="bot1", is_bot_message=True) is False

    def test_all_mode(self) -> None:
        event = ReactionEvent(message_id="m1", reaction_type="LIKE", user_id="u1", action="created")
        assert should_process_reaction(event, mode=ReactionNotificationMode.ALL) is True


class TestSyntheticTurn:
    def test_created_with_text(self) -> None:
        event = ReactionEvent(message_id="m1", reaction_type="THUMBSUP", user_id="u1", action="created")
        turn = create_synthetic_turn(event, message_text="Hello world")
        assert "reacted with" in turn.text
        assert "THUMBSUP" in turn.text
        assert "Hello world" in turn.text

    def test_deleted(self) -> None:
        event = ReactionEvent(message_id="m1", reaction_type="HEART", user_id="u1", action="deleted")
        turn = create_synthetic_turn(event)
        assert "removed reaction" in turn.text


class TestFeishuRouting:
    def test_dm_session_key(self) -> None:
        key = resolve_feishu_session_key(chat_id="c1", sender_id="u1", chat_type="p2p")
        assert "dm:u1" in key

    def test_group_session_key(self) -> None:
        key = resolve_feishu_session_key(chat_id="c1", sender_id="u1", chat_type="group")
        assert "group:c1" in key

    def test_group_sender_scope(self) -> None:
        cfg = FeishuRoutingConfig(group_session_scope=GroupSessionScope.GROUP_SENDER)
        key = resolve_feishu_session_key(chat_id="c1", sender_id="u1", chat_type="group", config=cfg)
        assert "sender:u1" in key

    def test_group_topic_scope(self) -> None:
        cfg = FeishuRoutingConfig(group_session_scope=GroupSessionScope.GROUP_TOPIC)
        key = resolve_feishu_session_key(chat_id="c1", root_id="root1", chat_type="group", config=cfg)
        assert "topic:root1" in key

    def test_group_topic_sender_scope(self) -> None:
        cfg = FeishuRoutingConfig(group_session_scope=GroupSessionScope.GROUP_TOPIC_SENDER)
        key = resolve_feishu_session_key(chat_id="c1", sender_id="u1", root_id="root1", chat_type="group", config=cfg)
        assert "topic:root1" in key
        assert "sender:u1" in key

    def test_sender_allowed_no_restriction(self) -> None:
        cfg = FeishuRoutingConfig()
        assert is_sender_allowed_in_group("u1", "g1", cfg) is True

    def test_sender_allowed_global(self) -> None:
        cfg = FeishuRoutingConfig(group_sender_allow_from=["u1", "u2"])
        assert is_sender_allowed_in_group("u1", "g1", cfg) is True
        assert is_sender_allowed_in_group("u3", "g1", cfg) is False

    def test_sender_allowed_per_group_override(self) -> None:
        cfg = FeishuRoutingConfig(
            group_sender_allow_from=["u1"],
            groups={"g1": {"allowFrom": ["u2"]}},
        )
        assert is_sender_allowed_in_group("u2", "g1", cfg) is True
        assert is_sender_allowed_in_group("u1", "g1", cfg) is False
        # Different group uses global
        assert is_sender_allowed_in_group("u1", "g2", cfg) is True

    def test_reply_params_disabled(self) -> None:
        params = resolve_reply_params(chat_id="c1", root_id="r1")
        assert "reply_in_thread" not in params

    def test_reply_params_enabled(self) -> None:
        cfg = FeishuRoutingConfig(reply_in_thread=ReplyInThread.ENABLED)
        params = resolve_reply_params(chat_id="c1", root_id="r1", config=cfg)
        assert params["reply_in_thread"] is True
        assert params["root_id"] == "r1"


class TestFeishuMessages:
    def test_resolve_media_type(self) -> None:
        assert resolve_media_type("image") == "image"
        assert resolve_media_type("audio") == "audio"
        assert resolve_media_type("media") == "video"
        assert resolve_media_type("file") == "file"
        assert resolve_media_type("sticker") == "image"

    def test_resolve_send_msg_type(self) -> None:
        assert resolve_send_msg_type("voice.opus") == "audio"
        assert resolve_send_msg_type("video.mp4") == "media"
        assert resolve_send_msg_type("photo.png") == "image"
        assert resolve_send_msg_type("doc.pdf") == "file"

    def test_parse_share_chat(self) -> None:
        result = parse_share_chat({"chat_id": "oc_123", "summary": "Team Chat"})
        assert "Team Chat" in result

    def test_parse_merge_forward_empty(self) -> None:
        result = parse_merge_forward({"messages": []})
        assert "empty" in result.lower()

    def test_parse_merge_forward(self) -> None:
        result = parse_merge_forward({
            "messages": [
                {"sender_name": "Alice", "message_type": "text", "content": {"text": "Hello"}},
                {"sender_name": "Bob", "message_type": "text", "content": {"text": "Hi"}},
            ]
        })
        assert "Alice" in result
        assert "Bob" in result

    def test_parse_rich_text(self) -> None:
        content = {
            "post": {
                "zh_cn": {
                    "title": "Test Title",
                    "content": [
                        [{"tag": "text", "text": "Hello "}, {"tag": "a", "text": "link", "href": "https://example.com"}],
                        [{"tag": "code", "text": "x = 1"}],
                    ],
                }
            }
        }
        result = parse_rich_text(content)
        assert "Test Title" in result
        assert "Hello" in result
        assert "[link]" in result
        assert "`x = 1`" in result

    def test_parse_text_message(self) -> None:
        body = {
            "event": {
                "message": {
                    "message_id": "msg_1",
                    "message_type": "text",
                    "content": '{"text": "Hello"}',
                    "chat_id": "c1",
                    "chat_type": "p2p",
                },
                "sender": {"sender_id": {"open_id": "ou_1", "name": "User"}},
            }
        }
        msg = parse_feishu_message(body)
        assert "Hello" in msg.text
        assert msg.message_id == "msg_1"
        assert msg.sender_id == "ou_1"


class TestProbeCache:
    def test_put_and_get(self) -> None:
        cache = ProbeCache(ttl_s=10)
        cache.put("acc1", {"bot_name": "Test"})
        result = cache.get("acc1")
        assert result is not None
        assert result["bot_name"] == "Test"

    def test_expired(self) -> None:
        cache = ProbeCache(ttl_s=0.01)
        cache.put("acc1", {"bot_name": "Test"})
        import time
        time.sleep(0.02)
        assert cache.get("acc1") is None

    def test_failure_not_cached(self) -> None:
        cache = ProbeCache()
        cache.put("acc1", {}, success=False)
        assert cache.get("acc1") is None

    def test_invalidate(self) -> None:
        cache = ProbeCache()
        cache.put("acc1", {"bot_name": "Test"})
        cache.invalidate("acc1")
        assert cache.get("acc1") is None


class TestTypingBackoff:
    def test_initially_allowed(self) -> None:
        tb = TypingBackoff()
        assert tb.should_send("c1") is True

    def test_suppressed_after_failures(self) -> None:
        tb = TypingBackoff(max_consecutive=2, base_delay_s=100)
        tb.record_failure("c1")
        tb.record_failure("c1")
        assert tb.should_send("c1") is False

    def test_rate_limit_code(self) -> None:
        tb = TypingBackoff(base_delay_s=100)
        tb.record_failure("c1", error_code=429)
        assert tb.should_send("c1") is False

    def test_success_resets(self) -> None:
        tb = TypingBackoff(max_consecutive=2, base_delay_s=100)
        tb.record_failure("c1")
        tb.record_success("c1")
        tb.record_failure("c1")
        assert tb.should_send("c1") is True

    def test_reset(self) -> None:
        tb = TypingBackoff(max_consecutive=1, base_delay_s=100)
        tb.record_failure("c1")
        tb.reset("c1")
        assert tb.should_send("c1") is True


class TestWebhookRateLimiter:
    def test_allows_initial(self) -> None:
        rl = WebhookRateLimiter(max_requests=5)
        assert rl.check("key1") is True

    def test_blocks_over_limit(self) -> None:
        rl = WebhookRateLimiter(max_requests=3, window_s=60)
        for _ in range(3):
            rl.check("key1")
        assert rl.check("key1") is False

    def test_different_keys(self) -> None:
        rl = WebhookRateLimiter(max_requests=2, window_s=60)
        rl.check("key1")
        rl.check("key1")
        assert rl.check("key1") is False
        assert rl.check("key2") is True

    def test_max_keys_cap(self) -> None:
        rl = WebhookRateLimiter(max_keys=3, max_requests=100)
        rl.check("k1")
        rl.check("k2")
        rl.check("k3")
        assert rl.check("k4") is False

    def test_tracked_keys(self) -> None:
        rl = WebhookRateLimiter()
        rl.check("k1")
        rl.check("k2")
        assert rl.tracked_keys == 2
