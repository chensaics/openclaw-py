"""Tests for Phase 27 — Channel Plugin SDK: adapters, draft streaming, ack reactions,
model overrides, mention gating, status/health checks."""

from __future__ import annotations

import pytest

from pyclaw.channels.plugin_sdk.adapters import (
    ALL_ADAPTER_PROTOCOLS,
    ChannelIdentity,
    InboundTurn,
    OutboundPayload,
    SendResult,
    detect_capabilities,
    has_capability,
)
from pyclaw.channels.plugin_sdk.draft_stream import (
    DraftConfig,
    DraftState,
    DraftStream,
    DraftStreamManager,
)
from pyclaw.channels.plugin_sdk.ack_reactions import (
    AckReactionManager,
    ReactionConfig,
    ReactionScope,
    StatusType,
    get_status_emoji,
    should_clear_reaction,
    should_react,
)
from pyclaw.channels.plugin_sdk.model_overrides import (
    CapabilitySchema,
    ChannelModelConfig,
    ModelOverride,
    ModelOverrideResolver,
)
from pyclaw.channels.plugin_sdk.mention_gating import (
    MentionConfig,
    MentionDetector,
    MentionResult,
)
from pyclaw.channels.plugin_sdk.status_issues import (
    ChannelConfigSchema,
    ChannelHealthChecker,
    ChannelHealthReport,
    ChannelIssue,
    ConfigField,
    IssueSeverity,
    MediaLimits,
    check_api_key,
    check_webhook_url,
)


# ===== Adapter Protocols =====

class TestAdapterProtocols:
    def test_protocol_count(self) -> None:
        assert len(ALL_ADAPTER_PROTOCOLS) >= 20

    def test_detect_no_capabilities(self) -> None:
        class Bare:
            pass
        caps = detect_capabilities(Bare())
        assert caps == []

    def test_detect_config_capability(self) -> None:
        class WithConfig:
            def get_config_schema(self) -> dict:
                return {}
            def validate_config(self, config: dict) -> list[str]:
                return []
        caps = detect_capabilities(WithConfig())
        assert "config" in caps

    def test_has_capability(self) -> None:
        class WithStatus:
            async def get_status(self) -> dict:
                return {}
            async def probe(self) -> bool:
                return True
            def get_issues(self) -> list[str]:
                return []
        assert has_capability(WithStatus(), "status")
        assert not has_capability(WithStatus(), "streaming")

    def test_inbound_turn(self) -> None:
        turn = InboundTurn(text="hello", sender_id="u1", chat_id="c1", is_group=True)
        assert turn.text == "hello"
        assert turn.is_group

    def test_outbound_payload(self) -> None:
        payload = OutboundPayload(chat_id="c1", text="reply")
        assert payload.chat_id == "c1"


# ===== Draft Streaming =====

class TestDraftStream:
    @pytest.mark.asyncio
    async def test_lifecycle(self) -> None:
        updates: list[str] = []

        async def on_update(draft_id: str, text: str) -> bool:
            updates.append(text)
            return True

        async def on_finalize(draft_id: str, text: str) -> str:
            return "msg-123"

        stream = DraftStream("d1", "c1", on_update=on_update, on_finalize=on_finalize)
        assert stream.state == DraftState.IDLE

        stream.start()
        assert stream.state == DraftState.STREAMING

        await stream.feed("Hello world, this is a test message.")
        assert stream.update_count >= 1

        msg_id = await stream.finalize("Final text")
        assert msg_id == "msg-123"
        assert stream.state == DraftState.IDLE

    @pytest.mark.asyncio
    async def test_stop(self) -> None:
        stream = DraftStream("d1", "c1")
        stream.start()
        stream.stop()
        assert stream.state == DraftState.STOPPED

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        stream = DraftStream("d1", "c1")
        stream.start()
        await stream.feed("Some text that should be cleared")
        stream.clear()
        assert stream.current_text == ""
        assert stream.state == DraftState.IDLE

    @pytest.mark.asyncio
    async def test_feed_when_not_streaming(self) -> None:
        stream = DraftStream("d1", "c1")
        await stream.feed("text")  # Should not raise
        assert stream.update_count == 0


class TestDraftStreamManager:
    def test_create_and_get(self) -> None:
        mgr = DraftStreamManager()
        stream = mgr.create("d1", "c1")
        assert mgr.get("d1") is stream

    def test_remove(self) -> None:
        mgr = DraftStreamManager()
        mgr.create("d1", "c1")
        assert mgr.remove("d1") is True
        assert mgr.get("d1") is None

    def test_stop_all(self) -> None:
        mgr = DraftStreamManager()
        s1 = mgr.create("d1", "c1")
        s2 = mgr.create("d2", "c2")
        s1.start()
        s2.start()
        count = mgr.stop_all()
        assert count == 2

    def test_active_count(self) -> None:
        mgr = DraftStreamManager()
        s1 = mgr.create("d1", "c1")
        s2 = mgr.create("d2", "c2")
        s1.start()
        assert mgr.active_count == 1
        s2.start()
        assert mgr.active_count == 2

    def test_list_active(self) -> None:
        mgr = DraftStreamManager()
        s1 = mgr.create("d1", "c1")
        s1.start()
        assert "d1" in mgr.list_active()


# ===== Ack Reactions =====

class TestAckReactions:
    def test_should_react_all(self) -> None:
        config = ReactionConfig(scope=ReactionScope.ALL)
        assert should_react(config, is_dm=True)
        assert should_react(config, is_group=True)

    def test_should_react_off(self) -> None:
        config = ReactionConfig(scope=ReactionScope.OFF)
        assert not should_react(config, is_dm=True)

    def test_should_react_direct_only(self) -> None:
        config = ReactionConfig(scope=ReactionScope.DIRECT)
        assert should_react(config, is_dm=True)
        assert not should_react(config, is_group=True)

    def test_should_react_group_mentions(self) -> None:
        config = ReactionConfig(scope=ReactionScope.GROUP_MENTIONS)
        assert not should_react(config, is_group=True, is_mention=False)
        assert should_react(config, is_group=True, is_mention=True)

    def test_get_emoji(self) -> None:
        config = ReactionConfig()
        assert get_status_emoji(config, StatusType.THINKING) == "🤔"
        assert get_status_emoji(config, StatusType.ERROR) == "❌"
        assert get_status_emoji(config, StatusType.DONE) == "✅"

    def test_clear_on_done(self) -> None:
        config = ReactionConfig(clear_on_done=True)
        assert should_clear_reaction(config, StatusType.DONE)
        assert not should_clear_reaction(config, StatusType.THINKING)

    def test_manager_track(self) -> None:
        mgr = AckReactionManager()
        state = mgr.track("m1", "c1")
        assert state.message_id == "m1"
        assert mgr.tracked_count == 1

    def test_manager_update_status(self) -> None:
        mgr = AckReactionManager()
        mgr.track("m1", "c1")
        state = mgr.update_status("m1", StatusType.THINKING)
        assert state is not None
        assert state.current_emoji == "🤔"

    def test_manager_update_done_clears(self) -> None:
        mgr = AckReactionManager(ReactionConfig(clear_on_done=True))
        mgr.track("m1", "c1")
        mgr.update_status("m1", StatusType.THINKING)
        state = mgr.update_status("m1", StatusType.DONE)
        assert state is not None
        assert state.current_emoji == ""
        assert not state.applied

    def test_manager_untrack(self) -> None:
        mgr = AckReactionManager()
        mgr.track("m1", "c1")
        mgr.untrack("m1")
        assert mgr.tracked_count == 0


# ===== Model Overrides =====

class TestModelOverrides:
    def test_no_config(self) -> None:
        resolver = ModelOverrideResolver()
        assert resolver.resolve("ch1") is None

    def test_channel_default(self) -> None:
        resolver = ModelOverrideResolver()
        resolver.set_channel_config("ch1", ChannelModelConfig(default_model="gpt-4o"))
        result = resolver.resolve("ch1")
        assert result is not None
        assert result.model == "gpt-4o"
        assert result.reason == "channel:ch1"

    def test_group_override(self) -> None:
        resolver = ModelOverrideResolver()
        resolver.set_channel_config("ch1", ChannelModelConfig(
            default_model="gpt-4o",
            group_overrides={"g1": ModelOverride(model="claude-3", think_level="high")},
        ))
        result = resolver.resolve("ch1", group_id="g1")
        assert result is not None
        assert result.model == "claude-3"
        assert result.think_level == "high"

    def test_group_priority(self) -> None:
        resolver = ModelOverrideResolver()
        resolver.set_channel_config("ch1", ChannelModelConfig(
            default_model="default",
            group_overrides={"g1": ModelOverride(model="override")},
        ))
        result = resolver.resolve("ch1", group_id="g1")
        assert result is not None
        assert result.model == "override"

    def test_allowed_models(self) -> None:
        resolver = ModelOverrideResolver()
        resolver.set_channel_config("ch1", ChannelModelConfig(
            allowed_models=["gpt-4o", "claude-3"],
        ))
        assert resolver.is_model_allowed("ch1", "gpt-4o")
        assert not resolver.is_model_allowed("ch1", "llama-3")

    def test_blocked_models(self) -> None:
        resolver = ModelOverrideResolver()
        resolver.set_channel_config("ch1", ChannelModelConfig(
            blocked_models=["dangerous-model"],
        ))
        assert not resolver.is_model_allowed("ch1", "dangerous-model")
        assert resolver.is_model_allowed("ch1", "gpt-4o")

    def test_list_allowed(self) -> None:
        resolver = ModelOverrideResolver()
        resolver.set_channel_config("ch1", ChannelModelConfig(
            allowed_models=["a", "b"],
        ))
        assert resolver.list_allowed_models("ch1") == ["a", "b"]
        assert resolver.list_allowed_models("unknown") is None

    def test_capability_schema(self) -> None:
        schema = CapabilitySchema(supports_vision=True, max_message_length=2048)
        assert schema.supports_vision
        assert schema.max_message_length == 2048


# ===== Mention Gating =====

class TestMentionDetector:
    def test_dm_always_mentioned(self) -> None:
        detector = MentionDetector(MentionConfig(bot_names=["Bot"]))
        result = detector.detect("Hello", is_group=False)
        assert result.is_mentioned
        assert result.mention_type == "direct"

    def test_group_with_mention(self) -> None:
        detector = MentionDetector(MentionConfig(bot_names=["MyBot"]))
        result = detector.detect("@MyBot hello", is_group=True)
        assert result.is_mentioned
        assert "hello" in result.cleaned_text

    def test_group_without_mention(self) -> None:
        detector = MentionDetector(MentionConfig(
            bot_names=["Bot"],
            require_mention_in_groups=True,
        ))
        result = detector.detect("hello everyone", is_group=True)
        assert not result.is_mentioned

    def test_command_bypass(self) -> None:
        detector = MentionDetector(MentionConfig(
            bot_names=["Bot"],
            bypass_commands=True,
        ))
        result = detector.detect("/help", is_group=True)
        assert result.is_mentioned
        assert result.is_command

    def test_no_command_bypass(self) -> None:
        detector = MentionDetector(MentionConfig(
            bot_names=["Bot"],
            bypass_commands=False,
            require_mention_in_groups=True,
        ))
        result = detector.detect("/help", is_group=True)
        assert not result.is_mentioned

    def test_user_id_mention(self) -> None:
        detector = MentionDetector(MentionConfig(
            bot_user_id="U12345",
        ))
        result = detector.detect("Hey <@U12345> do this", is_group=True)
        assert result.is_mentioned

    def test_case_insensitive(self) -> None:
        detector = MentionDetector(MentionConfig(
            bot_names=["MyBot"],
            case_sensitive=False,
        ))
        result = detector.detect("@mybot hello", is_group=True)
        assert result.is_mentioned

    def test_should_process(self) -> None:
        detector = MentionDetector(MentionConfig(bot_names=["Bot"]))
        assert detector.should_process("hello", is_group=False)
        assert not detector.should_process("hello", is_group=True)
        assert detector.should_process("@Bot hello", is_group=True)

    def test_strip_mention(self) -> None:
        detector = MentionDetector(MentionConfig(bot_names=["Bot"]))
        assert detector.strip_mention("@Bot hello world") == "hello world"

    def test_add_bot_name(self) -> None:
        detector = MentionDetector(MentionConfig(bot_names=["Bot"]))
        detector.add_bot_name("Assistant")
        result = detector.detect("@Assistant help", is_group=True)
        assert result.is_mentioned

    def test_no_mention_required(self) -> None:
        detector = MentionDetector(MentionConfig(
            require_mention_in_groups=False,
        ))
        assert detector.should_process("anything", is_group=True)


# ===== Status / Health Checks =====

class TestChannelIssue:
    def test_create_issue(self) -> None:
        issue = ChannelIssue(
            code="missing-token",
            message="Bot token is missing",
            severity=IssueSeverity.ERROR,
            category="auth",
        )
        assert issue.severity == IssueSeverity.ERROR

    def test_media_limits(self) -> None:
        limits = MediaLimits(max_file_size_mb=100)
        assert limits.max_file_size_mb == 100
        assert "jpg" in limits.supported_image_types


class TestConfigSchema:
    def test_to_json_schema(self) -> None:
        schema = ChannelConfigSchema(
            channel_type="telegram",
            display_name="Telegram",
            fields=[
                ConfigField(name="bot_token", field_type="secret", required=True, description="Bot token"),
                ConfigField(name="parse_mode", field_type="select", options=["Markdown", "HTML"]),
            ],
        )
        js = schema.to_json_schema()
        assert js["type"] == "object"
        assert "bot_token" in js["properties"]
        assert js["properties"]["parse_mode"]["enum"] == ["Markdown", "HTML"]
        assert "bot_token" in js["required"]

    def test_empty_schema(self) -> None:
        schema = ChannelConfigSchema(channel_type="test", display_name="Test")
        js = schema.to_json_schema()
        assert js["type"] == "object"
        assert js["properties"] == {}


class TestHealthChecker:
    def test_run_checks(self) -> None:
        checker = ChannelHealthChecker()
        checker.add_check("api_key", check_api_key)
        checker.add_check("webhook", check_webhook_url)
        assert checker.check_count == 2

        report = checker.run_checks("ch1", "telegram", {"bot_token": "abc"})
        assert report.is_healthy

    def test_missing_auth(self) -> None:
        checker = ChannelHealthChecker()
        checker.add_check("api_key", check_api_key)
        report = checker.run_checks("ch1", "telegram", {"api_key": ""})
        assert not report.is_healthy
        assert len(report.error_issues) == 1

    def test_insecure_webhook(self) -> None:
        checker = ChannelHealthChecker()
        checker.add_check("webhook", check_webhook_url)
        report = checker.run_checks("ch1", "slack", {"webhook_url": "http://example.com"})
        assert report.is_healthy  # Warning, not error
        assert len(report.warning_issues) == 1

    def test_check_error_handling(self) -> None:
        def bad_check(channel_id: str, config: dict) -> list:
            raise RuntimeError("Check failed")

        checker = ChannelHealthChecker()
        checker.add_check("bad", bad_check)
        report = checker.run_checks("ch1", "test", {})
        assert len(report.issues) == 1
        assert "failed" in report.issues[0].message

    def test_last_report(self) -> None:
        checker = ChannelHealthChecker()
        checker.run_checks("ch1", "test", {})
        report = checker.get_last_report("ch1")
        assert report is not None
        assert report.channel_id == "ch1"

    def test_health_report_properties(self) -> None:
        report = ChannelHealthReport(
            channel_id="ch1",
            channel_type="test",
            issues=[
                ChannelIssue(code="e1", message="err", severity=IssueSeverity.ERROR),
                ChannelIssue(code="w1", message="warn", severity=IssueSeverity.WARNING),
                ChannelIssue(code="i1", message="info", severity=IssueSeverity.INFO),
            ],
        )
        assert len(report.error_issues) == 1
        assert len(report.warning_issues) == 1
